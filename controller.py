import functools
import os
import tkinter as tk
import threading
from collections import defaultdict, ChainMap
from functools import reduce
from pprint import pprint
from tkinter import filedialog, ttk
from tkinter import messagebox
from tkinter.font import Font

import PIL
import pyperclip
import bisect

import traceback

from view.colors import history_color, not_visited_color, visited_color, ooc_color, text_color, uncanonical_color
from view.display import Display
from view.dialogs import GenerationSettingsDialog, InfoDialog, VisualizationSettingsDialog, \
    NodeChapterDialog, MultimediaDialog, NodeInfoDialog, SearchDialog, \
    PreferencesDialog, AIMemory, CreateMemory, NodeMemory, ChatSettingsDialog, CreateSummary, Summaries
from model import TreeModel
from util.util import clip_num, metadata
from util.util_tree import depth, height, flatten_tree, stochastic_transition, node_ancestry, subtree_list, node_index, \
    nearest_common_ancestor


def gated_call(f, condition):
    def _gated_call(*args, _f=f, _cond=condition, **kwargs):
        if _cond():
            # print('cond')
            _f(*args, **kwargs)
        # print("no cond")
    return _gated_call


def no_junk_args(f):
    return lambda event=None, *args, _f=f, **kwargs: _f(*args, **kwargs)


class Controller:

    def __init__(self, root):
        self.callbacks = self.build_callbacks()

        self.root = root
        self.state = TreeModel(self.root)
        self.display = Display(self.root, self.callbacks, self.state, self)

        self.register_model_callbacks()
        self.setup_key_bindings()
        self.build_menus()
        self.ancestor_end_indices = None

        # move to preferences dict in state
        self.canonical_only = False
        self.display_canonical = True


    #################################
    #   Hooks
    #################################

    def build_callbacks(self):
        attrs = [getattr(self, f) for f in dir(self)]
        callbacks = [f for f in attrs if callable(f) and hasattr(f, "meta") and "name" in f.meta]

        return {
            f.meta["name"]: {**f.meta, "callback": no_junk_args(f)}
            for f in callbacks
        }

    def register_model_callbacks(self):
        # When the tree is updated, refresh the navtree, nav selection, and textbox
        self.state.register_callback(self.state.tree_updated, self.update_nav_tree)
        self.state.register_callback(self.state.tree_updated, self.update_nav_tree_selected)
        self.state.register_callback(self.state.tree_updated, self.update_chapter_nav_tree)
        self.state.register_callback(self.state.tree_updated, self.update_chapter_nav_tree_selected)
        self.state.register_callback(self.state.tree_updated, self.save_edits)
        self.state.register_callback(self.state.tree_updated, self.refresh_textbox)
        self.state.register_callback(self.state.tree_updated, self.refresh_visualization)
        self.state.register_callback(self.state.tree_updated, self.refresh_display)
        # TODO autosaving takes too long for a big tree
        #self.state.register_callback(self.state.tree_updated, lambda: self.save_tree(popup=False))

        # Before the selection is updated, save edits
        self.state.register_callback(self.state.pre_selection_updated, self.save_edits)

        # When the selection is updated, refresh the nav selection and textbox
        self.state.register_callback(self.state.selection_updated, self.update_nav_tree_selected)
        self.state.register_callback(self.state.selection_updated, self.update_chapter_nav_tree_selected)
        self.state.register_callback(self.state.selection_updated, self.refresh_textbox)
        self.state.register_callback(self.state.selection_updated, self.refresh_vis_selection)
        self.state.register_callback(self.state.selection_updated, self.refresh_notes)
        self.state.register_callback(self.state.selection_updated, self.refresh_counterfactual_meta)
        self.state.register_callback(self.state.selection_updated, self.refresh_display)
        self.state.register_callback(self.state.io_update, self.update_dropdown)


    def setup_key_bindings(self):
        attrs = [getattr(self, f) for f in dir(self)]
        funcs_with_keys = [f for f in attrs if callable(f) and hasattr(f, "meta") and "keys" in f.meta]

        def in_edit():
            return self.display.mode in ["Edit", "Child Edit"] \
                   or (self.display.mode == "Visualize" and self.display.vis.textbox) \
                   or self.has_focus(self.display.input_box)

        valid_keys_outside_edit = ["Control", "Alt", "Escape", "Delete"]
        for f in funcs_with_keys:
            for tk_key in f.meta["keys"]:
                inside_edit = any(v in tk_key for v in valid_keys_outside_edit)
                self.root.bind(
                    tk_key, no_junk_args(f if inside_edit else gated_call(f, lambda: not in_edit()))
                )

        # Numbers to select children
        for i in range(1, 11):
            i = i % 10
            f = lambda _i=i: self.state.select_child(_i-1)
            self.root.bind(
                f"<Key-{i}>", no_junk_args(gated_call(f, lambda: not in_edit()))
            )

    def build_menus(self):
        # Tuple of 4 things: Name, Hotkey display text, tkinter key to bind to, function to call (without arguments)
        menu_list = {
            "View": [
                ('Toggle visualize mode', 'J', None, no_junk_args(self.toggle_visualization_mode)),
                ('Visualization settings', 'Ctrl+U', None, no_junk_args(self.visualization_settings_dialog)),
                ('Collapse node', 'Ctrl-?', None, no_junk_args(self.collapse_node)),
                ('Collapse subtree', 'Ctrl-minus', None, no_junk_args(self.collapse_subtree)),
                ('Collapse all except subtree', 'Ctrl-:', None, no_junk_args(self.collapse_all_except_subtree)),
                ('Expand children', 'Ctrl-\"', None, no_junk_args(self.expand_children)),
                ('Expand subtree', 'Ctrl-+', None, no_junk_args(self.expand_subtree)),
                ('Center view', 'L, Ctrl-L', None, no_junk_args(self.center_view)),
                ('Reset zoom', 'Ctrl-0', None, no_junk_args(self.reset_zoom)),
            ],
            "Edit": [
                ('Edit mode', 'Ctrl+E', None, no_junk_args(self.toggle_edit_mode)),
                ("Create parent", 'Alt-Left', None, no_junk_args(self.create_parent)),
                ("Change parent", 'Shift-P', None, no_junk_args(self.change_parent)),
                ("New Child", 'H, Ctrl+H, Alt+Right', None, no_junk_args(self.create_child)),
                ("New Sibling", 'Alt+Down', None, no_junk_args(self.create_sibling)),
                ("Merge with parent", 'Shift+Left', None, no_junk_args(self.merge_with_parent)),
                ("Merge with children", 'Shift+Right', None, no_junk_args(self.merge_with_children)),
                ("Move up", 'Shift+Up', None, no_junk_args(self.move_up)),
                ("Move up", 'Shift+Down', None, no_junk_args(self.move_down)),
                ('Prepend newline', 'N, Ctrl+N', None, no_junk_args(self.prepend_newline)),
                ('Prepend space', 'Ctrl+Space', None, no_junk_args(self.prepend_space)),
                ('Copy', 'Ctrl+C', None, no_junk_args(self.copy_text)),
                ('Delete', 'Backspace', None, no_junk_args(self.delete_node)),
                ('Delete and reassign children', '', None, no_junk_args(self.delete_node_reassign_children)),
            ],
            "Navigate": [
                ('Return to root', 'R', None, no_junk_args(self.return_to_root)),
                ('Save checkpoint', 'Ctrl+T', None, no_junk_args(self.save_checkpoint)),
                ('Go to checkpoint', 'T', None, no_junk_args(self.goto_checkpoint)),
                ("Bookmark", "B", None, no_junk_args(self.bookmark)),
                ("Next Bookmark", "D", None, no_junk_args(self.next_bookmark)),
                ("Prev Bookmark", "A", None, no_junk_args(self.prev_bookmark)),
                ("Stochastic walk", "W", None, no_junk_args(self.walk)),
                ("Edit chapter", "Ctrl+Y", None, no_junk_args(self.chapter_dialog)),
                ("Search", "Ctrl+F", None, no_junk_args(self.search)),

            ],
            "Generation": [
                ('Generation settings', 'Ctrl+P', None, no_junk_args(self.generation_settings_dialog)),
                ('Chat settings', None, None, no_junk_args(self.chat_settings)),
                ('Generate', 'G, Ctrl+G', None, no_junk_args(self.generate)),
                ('View summaries', '', None, no_junk_args(self.view_summaries)),

            ],
            "Memory": [
                ('AI Memory', 'Ctrl+Shift+M', None, no_junk_args(self.ai_memory)),
                ('Create memory', 'Ctrl+M', None, no_junk_args(self.add_memory)),
                ('Node memory', 'Alt+M', None, no_junk_args(self.node_memory)),
            ],
            "Flags": [
                ("Mark node visited", None, None, lambda: self.set_visited(True)),
                ("Mark node unvisited", None, None, lambda: self.set_visited(False)),
                ("Mark subtree visited", None, None, lambda: self.set_subtree_visited(True)),
                ("Mark subtree unvisited", None, None, lambda: self.set_subtree_visited(False)),
                ("Mark all visited", None, None, lambda: self.set_all_visited(True)),
                ("Mark all unvisited", None, None, lambda: self.set_all_visited(False)),
                ("Mark node as prompt", None, None, lambda: self.set_source('prompt')),
                ("Mark node as AI completion", None, None, lambda: self.set_source('AI')),
                ("Mark subtree as prompt", None, None, lambda: self.set_subtree_source('prompt')),
                ("Mark subtree as AI completion", None, None, lambda: self.set_subtree_source('AI')),
                ("Mark all as prompt", None, None, lambda: self.set_all_source('prompt')),
                ("Mark all as AI completion", None, None, lambda: self.set_all_source('AI')),

            ],
            "Info": [
                ("Tree statistics", "I", None, no_junk_args(self.info_dialog)),
                ('Multimedia', 'U', None, no_junk_args(self.multimedia_dialog)),
                ('Node metadata', 'Ctrl+Shift+N', None, no_junk_args(self.node_info_dialogue)),
                ('Preferences', '', None, no_junk_args(self.preferences))
            ],
        }
        return menu_list



    #################################
    #   Navigation
    #################################

    # @metadata(name=, keys=, display_key=)
    @metadata(name="Next", keys=["<period>", "<Return>", "<Control-period>"], display_key=">")
    def next(self):
        if self.state.preferences["canonical_only"]:
            self.state.next_canonical()
        else:
            #self.state.traverse_tree(1)
            self.select_node(node=self.state.next(1))
    # next.meta = dict(name="Next", keys=["<period>", "<Return>"], display_key=">")
    # .meta = dict(name=, keys=, display_key=)

    @metadata(name="Prev", keys=["<comma>", "<Control-comma>"], display_key="<",)
    def prev(self):
        if self.state.preferences["canonical_only"]:
            self.state.prev_canonical()
        else:
            #self.state.traverse_tree(-1)
            self.select_node(node=self.state.next(-1))

    @metadata(name="Go to parent", keys=["<Left>", "<Control-Left>"], display_key="←")
    def parent(self):
        #self.state.select_parent()
        self.select_node(node=self.state.parent())

    @metadata(name="Go to child", keys=["<Right>", "<Control-Right>"], display_key="→")
    def child(self):
        child_id = self.state.child(0)
        if child_id is not None:
            self.select_node(node=self.state.tree_node_dict[child_id])

    @metadata(name="Go to next sibling", keys=["<Down>", "<Control-Down>"], display_key="↓")
    def next_sibling(self):
        #self.state.select_sibling(1)
        self.select_node(node=self.state.sibling(1))

    @metadata(name="Go to previous Sibling", keys=["<Up>", "<Control-Up>"], display_key="↑")
    def prev_sibling(self):
        #self.state.select_sibling(-1)
        self.select_node(node=self.state.sibling(-1))

    @metadata(name="Walk", keys=["<Key-w>", "<Control-w>"], display_key="w")
    def walk(self, canonical_only=False):
        filter_set = self.state.calc_canonical_set() if canonical_only else None
        if 'children' in self.state.selected_node and len(self.state.selected_node['children']) > 0:
            chosen_child = stochastic_transition(self.state.selected_node, mode='descendents', filter_set=filter_set)
            #self.state.select_node(chosen_child['id'])
            self.select_node(node=chosen_child)

    @metadata(name="Return to root", keys=["<Key-r>", "<Control-r>"], display_key="r")
    def return_to_root(self):
        #self.state.select_node(self.state.tree_raw_data["root"]["id"])
        self.select_node(node=self.state.tree_raw_data["root"])

    @metadata(name="Save checkpoint", keys=["<Control-t>"], display_key="ctrl-t")
    def save_checkpoint(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.checkpoint = node['id']
        self.state.tree_updated(edit=[node['id']])

    @metadata(name="Go to checkpoint", keys=["<Key-t>"], display_key="t")
    def goto_checkpoint(self):
        if self.state.checkpoint:
            #self.state.select_node(self.state.checkpoint)
            self.select_node(node=self.state.tree_node_dict[self.state.checkpoint])

    @metadata(name="Nav Select")
    def nav_select(self, *, node_id):
        if not node_id or node_id == self.state.selected_node_id:
            return
        if self.change_parent.meta["click_mode"]:
            self.change_parent(node=self.state.tree_node_dict[node_id])
        # TODO This causes infinite recursion from the vis node. Need to change how updating open status works
        # Update the open state of the node based on the nav bar
        # node = self.state.tree_node_dict[node_id]
        # node["open"] = self.display.nav_tree.item(node["id"], "open")
        #self.state.select_node(node_id)
        self.select_node(node=self.state.tree_node_dict[node_id])

    @metadata(name="Bookmark", keys=["<Key-b>", "<Control-b>"], display_key="b")
    def bookmark(self, node=None):
        if node is None:
            node = self.state.selected_node
        node["bookmark"] = not node.get("bookmark", False)
        self.state.tree_updated(edit=[node['id']])

    @metadata(name="Toggle canonical", keys=["<Control-Shift-KeyPress-C>"], display_key="ctrl+shift+C")
    def toggle_canonical(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.toggle_canonical(node=node)
        self.state.tree_updated(edit=[n['id'] for n in node_ancestry(node, self.state.tree_node_dict)])

    @metadata(name="Go to next bookmark", keys=["<Key-d>", "<Control-d>"])
    def next_bookmark(self):
        book_indices = {idx: d for idx, d in enumerate(self.state.nodes) if d.get("bookmark", False)}
        if len(book_indices) < 1:
            return
        try:
            go_to_book = next(i for i, idx in enumerate(book_indices.keys()) if idx > self.state.tree_traversal_idx)
        except StopIteration:
            go_to_book = 0
        #self.state.select_node(list(book_indices.values())[go_to_book]["id"])
        self.select_node(list(book_indices.values())[go_to_book])

    @metadata(name="Go to prev bookmark", keys=["<Key-a>", "<Control-a>"])
    def prev_bookmark(self):
        book_indices = {i: d for i, d in enumerate(self.state.nodes) if d.get("bookmark", False)}
        if len(book_indices) < 1:
            return
        earlier_books = list(i for i, idx in enumerate(book_indices.keys()) if idx < self.state.tree_traversal_idx)
        go_to_book = earlier_books[-1] if len(earlier_books) > 0 else -1
        #self.state.select_node(list(book_indices.values())[go_to_book]["id"])
        self.select_node(list(book_indices.values())[go_to_book])

    @metadata(name="Center view", keys=["<Key-l>", "<Control-l>"])
    def center_view(self):
        #self.display.vis.center_view_on_canvas_coords(*self.display.vis.node_coords[self.state.selected_node_id])
        self.display.vis.center_view_on_node(self.state.selected_node)

    @metadata(name="Select node")
    def select_node(self, node):
        if self.state.preferences['coloring'] == 'read':
            old_node = self.state.selected_node
            self.state.select_node(node['id'])
            nca_node, index = nearest_common_ancestor(old_node, node, self.state.tree_node_dict)
            nca_end_index = self.ancestor_end_indices[index]
            self.display.textbox.tag_delete("old")
            self.display.textbox.tag_add("old",
                                         "1.0",
                                         f"1.0 + {nca_end_index} chars")
            self.display.textbox.tag_config("old", foreground=history_color())
            #traceback.print_stack()
            print('done')
        else:
            self.state.select_node(node['id'])



    #################################
    #   Node operations
    #################################

    @metadata(name="New Child", keys=["<h>", "<Control-h>", "<Alt-Right>"], display_key="h",)
    def create_child(self, node=None, update_selection=True, toggle_edit=True):
        if node is None:
            node = self.state.selected_node
        child = self.state.create_child(parent=node, update_selection=update_selection)
        if self.display.mode == "Read" and toggle_edit:
            self.toggle_edit_mode()
        return child

    @metadata(name="New Sibling", keys=["<Alt-Down>"], display_key="alt-down")
    def create_sibling(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.create_sibling(node=node)
        if self.display.mode == "Read":
            self.toggle_edit_mode()

    @metadata(name="New Parent", keys=["<Alt-Left>"], display_key="alt-left")
    def create_parent(self, node=None):
        if node is None:
            node = self.state.selected_node
        return self.state.create_parent(node=node)

    @metadata(name="Change Parent", keys=["<Shift-P>"], display_key="shift-p", selected_node=None, click_mode=False)
    def change_parent(self, node=None, click_mode=False):
        if node is None:
            node = self.state.selected_node
        if self.change_parent.meta["selected_node"] is None:
            self.display.change_cursor("fleur")
            self.change_parent.meta["selected_node"] = node
            self.change_parent.meta["click_mode"] = click_mode
        else:
            self.display.change_cursor("arrow")
            self.state.change_parent(node=self.change_parent.meta["selected_node"], new_parent_id=node["id"])
            self.change_parent.meta["selected_node"] = None
            self.change_parent.meta["click_mode"] = False

    @metadata(name="Merge with Parent", keys=["<Shift-Left>"], display_key="shift-left",)
    def merge_parent(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.merge_with_parent(node=node)

    @metadata(name="Merge with children", keys=["<Shift-Right>"], display_key="shift-right")
    def merge_children(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.merge_with_children(node=node)

    @metadata(name="Move up", keys=["<Shift-Up>"], display_key="shift-up")
    def move_up(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.shift(node, -1)

    @metadata(name="Move down", keys=["<Shift-Down>"], display_key="shift-down")
    def move_down(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.shift(node, 1)

    @metadata(name="Generate", keys=["<g>", "<Control-g>"], display_key="g")
    def generate(self, node=None, **kwargs):
        if node is None:
            node = self.state.selected_node
        try:
            node["open"] = True
            self.display.nav_tree.item(node, open=True)
        except Exception as e:
            print(str(e))
        self.state.generate_continuation(node=node, **kwargs)

    @metadata(name="Delete", keys=["<BackSpace>", "<Control-BackSpace>"], display_key="«")
    def delete_node(self, node=None, reassign_children=False):
        if node is None:
            node = self.state.selected_node
        if not node or "parent_id" not in node:
            return
        result = messagebox.askquestion("Delete", "Delete Node?", icon='warning')
        if result != 'yes':
            return
        self.state.delete_node(node=node, reassign_children=reassign_children)

    @metadata(name="Delete and reassign children")
    def delete_node_reassign_children(self, node=None):
        self.delete_node(node=node, reassign_children=True)

    @metadata(name="Enter text", keys=["<Control-bar>"], display_key="Ctrl-Return")
    def enter_text(self):
        self.display.vis.delete_textbox()

    @metadata(name="Escape textbox", keys=["<Escape>"], display_key="Escape")
    def escape(self):
        self.display.vis.delete_textbox(save=False)
        if self.display.in_edit_mode:
            self.display.set_mode("Read")
            self.refresh_textbox()
        if self.change_parent.meta["selected_node"]:
            self.display.change_cursor("arrow")
            self.change_parent.meta["selected_node"] = None

    @metadata(name="Edit history", keys=[], display_key="", persistent_id=None)
    def edit_history(self, index):
        if self.display.mode == "Read":
            _, selected_ancestor = self.index_to_ancestor(index)
            self.state.select_node(selected_ancestor["id"])
            self.toggle_edit_mode()

    @metadata(name="Goto history", keys=[], display_key="")
    def goto_history(self, index):
        if self.display.mode == "Read":
            _, selected_ancestor = self.index_to_ancestor(index)
            self.nav_select(node_id=selected_ancestor["id"])

    @metadata(name="Split node", keys=[], display_key="")
    def split_node(self, index, change_selection=True):
        if self.display.mode == "Read":
            ancestor_index, selected_ancestor = self.index_to_ancestor(index)
            negative_offset = self.ancestor_end_indices[ancestor_index] - index
            split_index = len(selected_ancestor['text']) - negative_offset
            new_parent, _ = self.state.split_node(selected_ancestor, split_index)
            if change_selection:
                self.nav_select(node_id=new_parent["id"])
            # TODO deal with metadata

    def index_to_ancestor(self, index):
        ancestor_index = bisect.bisect_left(self.ancestor_end_indices, index)
        return ancestor_index, node_ancestry(self.state.selected_node, self.state.tree_node_dict)[ancestor_index]

    #################################
    #   Token manipulation
    #################################

    @metadata(name="Select token", keys=[], display_key="", selected_node=None, token_index=None)
    def select_token(self, index):
        if self.display.mode == "Read":
            self.display.textbox.tag_remove("selected", "1.0", 'end')
            ancestor_index, selected_node = self.index_to_ancestor(index)
            negative_offset = self.ancestor_end_indices[ancestor_index] - index
            offset = len(selected_node['text']) - negative_offset

            # TODO new token offsets if changed
            if "meta" in selected_node and "generation" in selected_node["meta"] and not selected_node['meta']['modified']:
                self.change_token.meta["counterfactual_index"] = 0
                self.change_token.meta["prev_token"] = None
                #token_offsets = [n - len(selected_node['meta']['generation']['prompt'])
                 #                for n in selected_node['meta']['generation']["logprobs"]["text_offset"]]
                token_offsets = selected_node['meta']['generation']["logprobs"]["text_offset"]

                token_index = bisect.bisect_left(token_offsets, offset) - 1
                start_position = token_offsets[token_index]
                token = selected_node['meta']['generation']["logprobs"]["tokens"][token_index]

                counterfactuals = selected_node['meta']['generation']["logprobs"]["top_logprobs"][token_index]
                sorted_counterfactuals = dict(sorted(counterfactuals.items(), key=lambda item: item[1], reverse=True))



                #print('start position: ', self.ancestor_end_indices[ancestor_index - 1] + start_position)
                self.display.textbox.tag_add("selected", f"1.0 + {self.ancestor_end_indices[ancestor_index - 1] + start_position} chars",
                                             f"1.0 + {self.ancestor_end_indices[ancestor_index - 1] + start_position + len(token)} chars")

                #self.change_token(selected_node, token_index)
                self.select_token.meta["selected_node"] = selected_node
                self.select_token.meta["token_index"] = token_index

    @metadata(name="Change token", keys=[], display_key="", counterfactual_index=0, prev_token=None, temp_token_offsets=None)
    def change_token(self, node=None, token_index=None, traverse=1):
        if not self.select_token.meta["selected_node"]:
            return
        elif not node:
            node = self.select_token.meta["selected_node"]
            token_index = self.select_token.meta["token_index"]

        if not self.change_token.meta['temp_token_offsets']:
            #token_offsets = [n - len(node['meta']['generation']['prompt'])
            #                 for n in node['meta']['generation']["logprobs"]["text_offset"]]
            token_offsets = node['meta']['generation']["logprobs"]["text_offset"]
            self.change_token.meta['temp_token_offsets'] = token_offsets
        else:
            token_offsets = self.change_token.meta['temp_token_offsets']

        start_position = token_offsets[token_index]
        token = node['meta']['generation']["logprobs"]["tokens"][token_index]
        counterfactuals = node['meta']['generation']["logprobs"]["top_logprobs"][token_index].copy()
        original_token = (token, counterfactuals.pop(token, None))
        index = node_index(node, self.state.tree_node_dict)
        sorted_counterfactuals = list(sorted(counterfactuals.items(), key=lambda item: item[1], reverse=True))
        sorted_counterfactuals.insert(0, original_token)

        self.change_token.meta["counterfactual_index"] += traverse
        if self.change_token.meta["counterfactual_index"] < 0 or self.change_token.meta["counterfactual_index"] > len(sorted_counterfactuals) - 1:
            self.change_token.meta["counterfactual_index"] -= traverse
            return

        new_token = sorted_counterfactuals[self.change_token.meta["counterfactual_index"]][0]
        if not self.change_token.meta['prev_token']:
            self.change_token.meta['prev_token'] = token

        token_start = self.ancestor_end_indices[index - 1] + start_position

        self.display.textbox.config(state="normal")
        self.display.textbox.delete(f"1.0 + {token_start} chars",
                                    f"1.0 + {token_start + len(self.change_token.meta['prev_token'])} chars")
        self.display.textbox.insert(f"1.0 + {token_start} chars", new_token)
        self.display.textbox.config(state="disabled")

        self.display.textbox.tag_add("modified",
                                     f"1.0 + {token_start} chars",
                                     f"1.0 + {token_start + len(new_token)} chars")


        #update temp token offsets
        diff = len(new_token) - len(self.change_token.meta['prev_token'])
        for index, offset in enumerate(self.change_token.meta['temp_token_offsets'][token_index + 1:]):
            self.change_token.meta['temp_token_offsets'][index + token_index + 1] += diff
        self.change_token.meta['prev_token'] = new_token

    @metadata(name="Next token", keys=["<Alt-period>"], display_key="", counterfactual_index=0, prev_token=None)
    def next_token(self, node=None, token_index=None):
        self.change_token(node, token_index, traverse=1)

    @metadata(name="Prev token", keys=["<Alt-comma>"], display_key="", counterfactual_index=0, prev_token=None)
    def prev_token(self, node=None, token_index=None):
        self.change_token(node, token_index, traverse=-1)

    @metadata(name="Apply counterfactual", keys=["<Alt-Return>"], display_key="", counterfactual_index=0, prev_token=None)
    def apply_counterfactual_changes(self):
        # TODO apply to non selected nodes
        index = node_index(self.state.selected_node, self.state.tree_node_dict)

        new_text = self.display.textbox.get(f"1.0 + {self.ancestor_end_indices[index - 1]} chars", "end-1c")
        self.state.update_text(node=self.state.selected_node, text=new_text, modified_flag=False)
        self.display.textbox.tag_remove("modified", "1.0", 'end-1c')

        # TODO don't do this if no meta
        self.state.selected_node['meta']['generation']["logprobs"]["text_offset"] = self.change_token.meta['temp_token_offsets']
        self.refresh_counterfactual_meta()


    @metadata(name="Refresh counterfactual")
    def refresh_counterfactual_meta(self):
        self.change_token.meta['prev_token'] = None
        self.change_token.meta['temp_token_offsets'] = None


    #################################
    #   State
    #################################


    # Enters edit mode or exits either edit mode
    @metadata(name="Edit", keys=["<e>", "<Control-e>"], display_key="e")
    def toggle_edit_mode(self, to_edit_mode=None):
        if self.display.mode != "Visualize":
            self.save_edits()
            to_edit_mode = to_edit_mode if to_edit_mode is not None else not self.display.in_edit_mode
            if to_edit_mode:
                self.display.set_mode("Edit")
            else:
                if self.edit_history.meta["persistent_id"] is not None:
                    self.state.select_node(self.edit_history.meta["persistent_id"])
                    self.edit_history.meta["persistent_id"] = None
                self.display.set_mode("Read")
            self.refresh_textbox()
        else:
            if self.display.vis.textbox is None:
                self.display.vis.textbox_events[self.state.selected_node['id']]()
            else:
                self.display.vis.delete_textbox()


    @metadata(name="Child Edit", keys=[], display_key="c")
    def toggle_child_edit_mode(self, to_edit_mode=None):
        self.save_edits()
        to_edit_mode = to_edit_mode if to_edit_mode is not None else not self.display.mode == "Multi Edit"
        self.display.set_mode("Multi Edit" if to_edit_mode else "Read")
        self.refresh_textbox()


    @metadata(name="Visualize", keys=["<Key-j>", "<Control-j>"], display_key="j")
    def toggle_visualization_mode(self):
        self.save_edits()
        self.display.set_mode("Visualize" if self.display.mode != "Visualize" else "Read")
        self.refresh_visualization()
        self.refresh_textbox()


    #################################
    #   Edit
    #################################


    @metadata(name="Merge with parent")
    def merge_with_parent(self, node=None):
        self.state.merge_with_parent()


    @metadata(name="Merge with children")
    def merge_with_children(self):
        self.state.merge_with_children()

    @metadata(name="Copy")
    def copy_text(self):
        pyperclip.copy(self.display.textbox.get("1.0", "end-1c"))


    @metadata(name="Prepend newline", keys=["n", "<Control-n>"], display_key="n")
    def prepend_newline(self):
        self.save_edits()
        if self.state.selected_node:
            text = self.state.selected_node["text"]
            if text.startswith("\n"):
                text = text[1:]
            else:
                if text.startswith(' '):
                    text = text[1:]
                text = "\n" + text

            self.state.update_text(self.state.selected_node, text)


    @metadata(name="Prepend space", keys=["<Control-space>"], display_key="ctrl-space")
    def prepend_space(self):
        self.save_edits()
        if self.state.selected_node:
            text = self.state.selected_node["text"]
            if text.startswith(" "):
                text = text[1:]
            else:
                text = " " + text
            self.state.update_text(self.state.selected_node, text)


    #################################
    #   Collapsing
    #################################

    @metadata(name="Expand subtree", keys=["<Control-plus>"], display_key="Ctrl-plus")
    def expand_subtree(self):
        pass

    @metadata(name="Collapse subtree", keys=["<Control-minus>"], display_key="Ctrl-minus")
    def collapse_subtree(self):
        pass

    @metadata(name="Expand children", keys=["<Control-quotedbl>"], display_key="Ctrl-\"")
    def expand_children(self):
        pass

    @metadata(name="Collapse node", keys=["<Control-question>"], display_key="Ctrl-?")
    def collapse_node(self):
        pass

    @metadata(name="Collapse all except subtree", keys=["<Control-colon>"], display_key="Ctrl-:")
    def collapse_all_except_subtree(self):
        pass


    #################################
    #   View
    #################################

    def set_visited(self, status=True):
        self.state.selected_node["visited"] = status
        self.update_nav_tree()
        self.update_nav_tree_selected()


    def set_subtree_visited(self, status=True):
        for d in flatten_tree(self.state.selected_node):
            d["visited"] = status
        self.update_nav_tree()
        self.update_nav_tree_selected()

    def set_all_visited(self, status=True):
        for d in self.state.nodes:
            d["visited"] = status
        self.update_nav_tree()
        self.update_nav_tree_selected()

    def set_source(self, source='AI', node=None, refresh=True):
        if not node:
            node = self.state.selected_node
        if not 'meta' in node:
            node['meta'] = {}
        node['meta']['source'] = source
        if refresh:
            self.refresh_textbox()
            self.update_nav_tree()
            self.update_nav_tree_selected()

    def set_subtree_source(self, source='AI', node=None):
        if not node:
            node = self.state.selected_node
        for d in flatten_tree(node):
            self.set_source(source=source, node=d, refresh=False)
        self.refresh_textbox()
        self.update_nav_tree()
        self.update_nav_tree_selected()

    def set_all_source(self, source='AI'):
        for d in self.state.nodes:
            self.set_source(source=source, node=d, refresh=False)
        self.refresh_textbox()
        self.update_nav_tree()
        self.update_nav_tree_selected()

    @metadata(name="Toggle prompt", keys=["<Control-Shift-KeyPress-A>"], display_key="")
    def toggle_source(self, node=None):
        if not node:
            node = self.state.selected_node
        if 'meta' in node and 'source' in node['meta'] and node['meta']['source'] == 'AI':
            self.set_source(source='prompt', node=node)
        else:
            self.set_source(source='AI', node=node)



    # @metadata(name="Darkmode", keys=["<Control-Shift-KeyPress-D>"], display_key="Ctrl-Shift-D")
    # def toggle_darkmode(self):
    #     global darkmode
    #     darkmode = not darkmode
    #     print("c",darkmode)
    #     self.display.frame.pack_forget()
    #     self.display.frame.destroy()
    #     self.display = Display(self.root, self.callbacks, self.state)
    #     self.refresh_textbox()
    #     self.update_nav_tree()


    #################################
    #   I/O
    #################################


    @metadata(name="Open", keys=["<o>", "<Control-o>"], display_key="o")
    def open_tree(self):
        options = {
            'initialdir': os.getcwd() + '/data',
            'parent': self.root, 'title': "Open a json tree",
            'filetypes': [('json files', '.json')]
        }
        filename = filedialog.askopenfilename(**options)
        if not filename:
            return
        self.state.open_tree(filename)

    # TODO repeated code
    @metadata(name="Import JSON as subtree", keys=["<Control-Shift-KeyPress-O>"], display_key="ctrl+shift+o")
    def import_tree(self):
        options = {
            'initialdir': os.getcwd() + '/data',
            'parent': self.root, 'title': "Import a json tree",
            'filetypes': [('json files', '.json')]
        }
        filename = filedialog.askopenfilename(**options)
        if not filename:
            return
        self.state.import_tree(filename)

    @metadata(name="Save", keys=["<s>", "<Control-s>"], display_key="s")
    def save_tree(self, popup=True):
        try:
            self.state.delete_counterfactuals()
            self.save_edits()
            self.state.save_tree(backup=popup)
            if popup:
                messagebox.showinfo(title=None, message="Saved!")
        except Exception as e:
            messagebox.showerror(title="Error", message=f"Failed to Save!\n{str(e)}")

    @metadata(name="Save as sibling", keys=["<Alt-e>"], display_key="alt-e")
    def save_as_sibling(self):
        # TODO fails on root node
        if self.display.mode == "Edit":
            new_text = self.display.textbox.get("1.0", 'end-1c')
            new_active_text = self.display.secondary_textbox.get("1.0", 'end-1c')
            self.escape()
            sibling = self.state.create_sibling()
            self.nav_select(node_id=sibling['id'])
            self.state.update_text(sibling, new_text, new_active_text)


    @metadata(name="Export to text", keys=["<Control-Shift-KeyPress-X>"], display_key="Ctrl-Shift-X")
    def export_text(self):
        try:
            filename = self.state.tree_filename if self.state.tree_filename \
                else os.path.join(os.getcwd() + '/data/text', "export.txt")
            filename = filedialog.asksaveasfilename(
                initialfile=os.path.splitext(os.path.basename(filename))[0],
                initialdir=os.path.dirname(filename),
                defaultextension='.txt')
            self.state.export_history(self.state.selected_node, filename)
            messagebox.showinfo(title=None, message="Exported!")
        except Exception as e:
            messagebox.showerror(title="Error", message=f"Failed to Export!\n{str(e)}")


    @metadata(name="Clear chapters")
    def clear_chapters(self):
        result = messagebox.askquestion("Clear chapters", "Delete all chapters?", icon='warning')
        if result != 'yes':
            return
        self.state.remove_all_chapters()

    @metadata(name="Save As...")
    def save_tree_as(self):
        filename = self.state.tree_filename if self.state.tree_filename \
            else os.path.join(os.getcwd() + '/data', "new_tree.json")
        filename = filedialog.asksaveasfilename(
            initialfile=os.path.splitext(os.path.basename(filename))[0],
            initialdir=os.path.dirname(filename),
            defaultextension='.json')
        if filename:
            self.state.tree_filename = filename
            self.save_tree()
            return


    @metadata(name="Generation Settings", keys=["<Control-p>"], display_key="ctrl-p")
    def generation_settings_dialog(self):
        dialog = GenerationSettingsDialog(self.display.frame, self.state.generation_settings)
        if dialog.result:
            print("Settings saved")
            pprint(self.state.generation_settings)
            #self.save_tree(popup=False)
            self.refresh_textbox()


    @metadata(name="Visualization Settings", keys=["<Control-u>"], display_key="ctrl-u")
    def visualization_settings_dialog(self):
        dialog = VisualizationSettingsDialog(self.display.frame, self.state.visualization_settings)
        if dialog.result:
            print("Settings saved")
            pprint(self.state.visualization_settings)
            self.refresh_visualization()
            # self.save_tree(popup=False)

    @metadata(name="Show Info", keys=["<i>", "<Control-i>"], display_key="i")
    def info_dialog(self):
        all_text = "".join([d["text"] for d in self.state.tree_node_dict.values()])

        data = {
            "Total characters": f'{len(all_text):,}',
            "Total words": f'{len(all_text.split()):,}',
            "Total pages": f'{len(all_text) / 3000:,.1f}',
            "": "",
            "Total nodes": f'{len(self.state.tree_node_dict):,}',
            "Max depth": height(self.state.tree_raw_data["root"]),
            "Max width": max([len(d["children"]) for d in self.state.tree_node_dict.values()])

        }
        dialog = InfoDialog(self.display.frame, data)

    # @metadata(name="Show Chapters", keys=["<Control-t>"], display_key="ctrl-t")
    # def chapters_info_dialog(self):
    #     dialog = ChaptersInfoDialog(self.display.frame, self.state.chapters)

    @metadata(name="Chapter settings", keys=["<Control-y>"], display_key="ctrl-y")
    def chapter_dialog(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = NodeChapterDialog(parent=self.display.frame, node=node, state=self.state)

    @metadata(name="Node info", keys=["<Control-Shift-KeyPress-N>"], display_key="ctrl-shift-N")
    def node_info_dialogue(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = NodeInfoDialog(parent=self.display.frame, node=node, state=self.state)

    @metadata(name="Multimedia dialogue", keys=["<u>"], display_key="u")
    def multimedia_dialog(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = MultimediaDialog(parent=self.display.frame, node=node,
                                  refresh_event=lambda node_id=node['id']: self.state.tree_updated(edit=[node_id]))

    @metadata(name="Memory dialogue", keys=["<Control-Shift-KeyPress-M>"], display_key="Control-shift-m")
    def ai_memory(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = AIMemory(parent=self.display.frame, node=node, state=self.state)
        self.refresh_textbox()

    @metadata(name="Node memory", keys=["<Alt-m>"], display_key="Alt-m")
    def node_memory(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = NodeMemory(parent=self.display.frame, node=node, state=self.state)
        self.refresh_textbox()

    @metadata(name="Add memory", keys=["<m>", "<Control-m>"], display_key="m")
    def add_memory(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = CreateMemory(parent=self.display.frame, node=node, state=self.state, default_inheritability='delayed')
        self.refresh_textbox()

    @metadata(name="Search", keys=["<Control-f>"], display_key="ctrl-f")
    def search(self):
        dialog = SearchDialog(parent=self.display.frame, state=self.state, goto=self.nav_select)
        self.refresh_textbox()

    @metadata(name="Preferences", keys=[], display_key="")
    def preferences(self):
        print(self.state.preferences)
        dialog = PreferencesDialog(parent=self.display.frame, orig_params=self.state.preferences)
        self.refresh_textbox()
        self.refresh_display()
        self.update_dropdown()

    # @metadata(name="Semantic search memory", keys=["<Control-Shift-KeyPress-M>"], display_key="ctrl-alt-m")
    # def ancestry_semantic_search(self, node=None):
    #     if node is None:
    #         node = self.state.selected_node
    #     results = self.state.semantic_search_memory(node)
    #     print(results)
    #     for entry in results['data']:
    #         print(entry['score'])

    @metadata(name="Toggle input box", keys=["<Tab>"], display_key="")
    def toggle_input_box(self):
        if self.display.mode == "Read":
            if not self.state.preferences['input_box']:
                self.display.build_input_box()
                self.state.preferences['input_box'] = True
                self.update_dropdown()
                self.display.input_box.focus()
            else:
                self.display.destroy_input_box()
                self.state.preferences['input_box'] = False

    def update_dropdown(self):
        if self.display.mode_var:
            self.display.mode_var.set(self.state.preferences['gpt_mode'])

    @metadata(name="Update mode", keys=[], display_key="")
    def update_mode(self, *args):
        self.state.preferences['gpt_mode'] = self.display.mode_var.get()

    @metadata(name="Submit", keys=[], display_key="")
    def submit(self):
        input_text = self.display.input_box.get("1.0", 'end-1c')
        if input_text and not self.state.preferences['gpt_mode'] == 'antisummary':
            new_text = self.state.submit_modifications(input_text)
            new_child = self.create_child(toggle_edit=False)
            new_child['text'] = new_text
            self.state.tree_updated(add=[new_child['id']])
        self.display.input_box.delete("1.0", "end")
        if input_text and self.state.preferences['gpt_mode'] == 'antisummary':
            self.generate(summary=input_text)
        elif self.state.preferences['auto_response']:
            self.generate()

    @metadata(name="Debug", keys=["<Control-Shift-KeyPress-D>"], display_key="")
    def debug(self):
        dialog = CreateSummary(parent=self.display.frame, root_node=self.state.ancestry()[1], state=self.state)


    @metadata(name="Insert summary")
    def insert_summary(self, index):
        ancestor_index, selected_ancestor = self.index_to_ancestor(index)
        negative_offset = self.ancestor_end_indices[ancestor_index] - index
        offset = len(selected_ancestor['text']) - negative_offset
        dialog = CreateSummary(parent=self.display.frame, root_node=selected_ancestor, state=self.state, position=offset)

    def view_summaries(self):
        dialog = Summaries(parent=self.display.frame, node=self.state.selected_node, state=self.state)

    def test_counterfactual(self):
        threading.Thread(target=self.report_counterfactual(context_breaker='\n----\n\nWow. This is getting',
                                                           target=' scary')).start()
        threading.Thread(target=self.report_counterfactual(context_breaker='\n----\n\nWow. This is getting',
                                                           target=' sexy')).start()
        threading.Thread(target=self.report_counterfactual(context_breaker='\n----\n\nWow. This is getting',
                                                           target=' weird')).start()
        threading.Thread(target=self.report_counterfactual(context_breaker='\n----\n\nWow. This is getting',
                                                           target=' interesting')).start()


    def report_counterfactual(self, context_breaker, target):
        print(f'{target}: ',
              self.state.score_counterfactual(context_breaker=context_breaker, target=target, engine='davinci'))

    @metadata(name="Autocomplete", keys=["<Alt_L>"], display_key="", in_autocomplete=False, autocomplete_range=None,
              possible_tokens=None, token_index=None)
    def autocomplete(self):

        # TODO determine whether in edit mode, input box, or vis textbox
        if self.has_focus(self.display.input_box):
            self.display.input_box.tag_config('autocomplete', background="blue")
            if not self.autocomplete.meta["in_autocomplete"]:
                self.autocomplete.meta["possible_tokens"] = self.state.autocomplete_generate(self.display.input_box.get("1.0", "end-1c"), engine='curie')
                self.autocomplete.meta["token_index"] = 0
                self.autocomplete.meta["in_autocomplete"] = True
                self.insert_autocomplete()
            else:
                self.scroll_autocomplete(1)


    def insert_autocomplete(self):
        insert = self.display.input_box.index(tk.INSERT)
        suggested_token = self.autocomplete.meta["possible_tokens"][self.autocomplete.meta["token_index"]][0]
        self.autocomplete.meta["autocomplete_range"] = (insert, f'insert + {str(len(suggested_token))} chars')
        self.display.input_box.insert(tk.INSERT, suggested_token, "autocomplete")
        self.display.input_box.mark_set(tk.INSERT, insert)

    # TODO <Right> doesn't work
    @metadata(name="Apply Autocomplete", keys=["<Alt_R>", "<Right>"], display_key="")
    def apply_autocomplete(self):
        if self.has_focus(self.display.input_box) and self.autocomplete.meta["in_autocomplete"]:
            self.display.input_box.tag_delete("autocomplete")
            self.display.input_box.mark_set(tk.INSERT, self.autocomplete.meta["autocomplete_range"][1])
            self.exit_autocomplete()

    @metadata(name="Rewind Autocomplete", keys=["<Control_L>"], display_key="")
    def rewind_autocomplete(self):
        if self.has_focus(self.display.input_box) and self.autocomplete.meta["in_autocomplete"]:
            self.scroll_autocomplete(-1)

    def scroll_autocomplete(self, step=1):
        new_index = self.autocomplete.meta["token_index"] + step
        if 0 <= new_index < 100:
            self.autocomplete.meta["token_index"] = new_index
            self.display.input_box.delete(*self.autocomplete.meta["autocomplete_range"])
            self.insert_autocomplete()


    @metadata(name="Key Pressed", keys=[], display_key="")
    def key_pressed(self, char):
        if char and self.autocomplete.meta["in_autocomplete"]:
            self.display.input_box.delete(*self.autocomplete.meta["autocomplete_range"])
            self.exit_autocomplete()

    def exit_autocomplete(self):
        self.autocomplete.meta["autocomplete_range"] = None
        self.autocomplete.meta["in_autocomplete"] = False
        self.autocomplete.meta["token_index"] = None
        self.autocomplete.meta["possible_tokens"] = None

    @metadata(name="Chat settings", keys=[], display_key="")
    def chat_settings(self):
        dialog = ChatSettingsDialog(parent=self.display.frame, orig_params=self.state.chat_preferences)
        #self.refresh_textbox()

    def has_focus(self, widget):
        return self.display.textbox.focus_displayof() == widget

    #################################
    #   Story frame TODO call set text, do this in display?
    #################################

    @metadata(name="Save Edits")
    def save_edits(self, **kwargs):
        if not self.state.selected_node_id:
            return

        if self.display.mode == "Edit":
            new_text = self.display.textbox.get("1.0", 'end-1c')
            new_active_text = self.display.secondary_textbox.get("1.0", 'end-1c')
            self.state.update_text(self.state.selected_node, new_text, new_active_text)

        elif self.display.mode == "Multi Edit":
            nodes = [self.state.selected_node, *self.state.selected_node["children"]]
            new_texts = [textbox.get("1.0", 'end-1c') for textbox in self.display.multi_textboxes]
            # This needs to be idempotent because it risks calling itself recursively
            if any([node["text"] != new_text for node, new_text in zip(nodes, new_texts)]):
                for node, new_text in zip(nodes, new_texts):
                    node["text"] = new_text
                # TODO modified set
                self.state.tree_updated()

        elif self.display.mode == "Visualize":
            if self.display.vis.textbox:
                new_text = self.display.vis.textbox.get("1.0", 'end-1c')
                self.state.update_text(self.state.node(self.display.vis.editing_node_id), new_text)

        else:
            return

    def refresh_display(self, **kwargs):
        if self.state.preferences['input_box'] and not self.display.input_box:
            self.display.build_input_box()
        elif not self.state.preferences['input_box'] and self.display.input_box:
            self.display.destroy_input_box()

    HISTORY_COLOR = history_color()
    # @metadata(last_text="", last_scroll_height=0, last_num_lines=0)
    def refresh_textbox(self, **kwargs):
        if not self.state.tree_raw_data or not self.state.selected_node:
            return

        self.display.textbox.configure(font=Font(family="Georgia", size=self.state.preferences['font_size']),
                                       spacing1=self.state.preferences['paragraph_spacing'],
                                       spacing2=self.state.preferences['line_spacing'])

        # Fill textbox with text history, disable editing
        if self.display.mode == "Read":
            self.display.textbox.configure(state="normal")
            self.display.textbox.delete("1.0", "end")

            if self.state.preferences['coloring'] == 'edit':
                self.display.textbox.tag_config('ooc_history', foreground=ooc_color())
                self.display.textbox.tag_config('history', foreground=history_color())
            else:
                self.display.textbox.tag_config('ooc_history', foreground=text_color())
                self.display.textbox.tag_config('history', foreground=text_color())

            # TODO bad color for lightmode
            self.display.textbox.tag_config("selected", background="black", foreground=text_color())
            self.display.textbox.tag_config("modified", background="blue", foreground=text_color())
            ancestry, indices = self.state.node_ancestry_text()
            self.ancestor_end_indices = indices
            history = ''
            for node_text in ancestry[:-1]:
                # "end" includes the automatically inserted new line
                history += node_text
                #self.display.textbox.insert("end-1c", node_text, "history")
            selected_text = self.state.selected_node["text"]
            prompt_length = self.state.generation_settings['prompt_length'] - len(selected_text)

            in_context = history[-prompt_length:]
            if prompt_length < len(history):
                out_context = history[:len(history)-prompt_length]
                self.display.textbox.insert("end-1c", out_context, "ooc_history")
            self.display.textbox.insert("end-1c", in_context, "history")

            end = self.display.textbox.index(tk.END)
            #self.display.textbox.see(tk.END)

            self.display.textbox.insert("end-1c", selected_text)
            #self.display.textbox.see(end)
            self.display.textbox.insert("end-1c", self.state.selected_node.get("active_text", ""))

            # TODO Not quite right. We may need to compare the actual text content? Hmm...
            # num_lines = int(self.display.textbox.index('end-1c').split('.')[0])
            # while num_lines < self.refresh_textbox.meta["last_num_lines"]:
            #     self.display.textbox.insert("end-1c", "\n")
            #     num_lines = int(self.display.textbox.index('end-1c').split('.')[0])
            # self.refresh_textbox.meta["last_num_lines"] = num_lines

            self.tag_prompts()
            self.display.textbox.configure(state="disabled")

            # makes text copyable
            self.display.textbox.bind("<Button>", lambda event: self.display.textbox.focus_set())
            self.display.textbox.see(tk.END)



        # Textbox to edit mode, fill with single node
        elif self.display.mode == "Edit":
            self.display.textbox.configure(state="normal")
            self.display.textbox.delete("1.0", "end")
            self.display.textbox.insert("1.0", self.state.selected_node["text"])
            self.display.textbox.see(tk.END)

            self.display.secondary_textbox.delete("1.0", "end")
            self.display.secondary_textbox.insert("1.0", self.state.selected_node.get("active_text", ""))
            self.display.textbox.focus()


        elif self.display.mode == "Multi Edit":
            children = self.state.selected_node["children"]
            self.display.start_multi_edit(len(children) + 1)
            for node, textbox in zip([self.state.selected_node, *children], self.display.multi_textboxes):
                textbox.configure(state="normal")
                textbox.delete("1.0", "end")
                textbox.insert("1.0", node["text"])
                num_lines = max(node["text"].count("\n"), int(textbox.index('end').split('.')[0]))
                textbox.configure(height=max(3, num_lines+2))

            # Make the first text box history colors
            self.display.multi_textboxes[0].configure(foreground=self.HISTORY_COLOR)

    # TODO nodes with mixed prompt/continuation
    def tag_prompts(self):
        if self.state.preferences['bold_prompt']:
            self.display.textbox.tag_config('prompt', font=('Georgia', self.state.preferences['font_size'], 'bold'))
        else:
            self.display.textbox.tag_config('prompt', font=('Georgia', self.state.preferences['font_size']))
        self.display.textbox.tag_remove("prompt", "1.0", 'end')
        ancestry_text, indices = self.state.node_ancestry_text()
        start_index = 0
        for i, ancestor in enumerate(node_ancestry(self.state.selected_node, self.state.tree_node_dict)):
            if not ('meta' in ancestor and 'source' in ancestor['meta'] and ancestor['meta']['source'] == 'AI'):
                self.display.textbox.tag_add("prompt", f"1.0 + {start_index} chars", f"1.0 + {indices[i]} chars")
            start_index = indices[i]


    def refresh_visualization(self, center=False, **kwargs):
        if self.display.mode != "Visualize":
            return
        self.display.vis.draw(self.state.tree_raw_data["root"], self.state.selected_node, center_on_selection=False)
        if center:
            #self.display.vis.center_view_on_canvas_coords(*self.display.vis.node_coords[self.state.selected_node_id])
            self.display.vis.center_view_on_node(self.state.selected_node)


    def refresh_vis_selection(self):
        if self.display.mode != "Visualize":
            return
        self.display.vis.refresh_selection(self.state.tree_raw_data["root"], self.state.selected_node)
        # TODO Without redrawing, the new open state won't be reflected
        # self.display.vis.draw(self.state.tree_raw_data["root"], self.state.selected_node)
        # self.display.vis.center_view_on_canvas_coords(*self.display.vis.node_coords[self.state.selected_node_id])

    @metadata(name="Reset zoom", keys=["<Control-0>"], display_key="Ctrl-0")
    def reset_zoom(self):
        self.display.vis.reset_zoom()


    def refresh_notes(self):
        if not self.state.tree_raw_data or not self.state.selected_node or not self.state.preferences['side_pane']:
            return

        self.display.notes_textbox.configure(state="normal")
        self.display.notes_textbox.delete("1.0", "end")

        notes = self.state.selected_node.get("notes", None)
        # active note = last active else first note
        if notes:
            # text = active['text']
            # title = active['title']
            # scope
            # root
            pass


        note = notes[0] if notes else ""
        #print('note: ', note)
        self.display.notes_textbox.insert("end-1c", note)

    # TODO When to call this?
    def save_notes(self):
        new_note_text = self.display.notes_textbox.get("1.0", 'end-1c')
        self.state.update_note(self.state.selected_node, new_note_text)

    #################################
    #   Navtree
    #################################

    def nav_tree_name(self, node):
        text = node['text'].strip()[:20].replace('\n', ' ')
        text = text if text else "EMPTY"
        text = text + "..." if len(node['text']) > 20 else text
        if 'chapter_id' in node:
            text = f"{text} | {self.state.chapter_title(node)}"
        return node.get("name", text)

    def build_nav_tree(self):
        self.display.nav_tree.delete(*self.display.nav_tree.get_children())
        for id in self.state.tree_node_dict:
            node = self.state.tree_node_dict[id]
            if id == self.state.checkpoint:
                image = self.display.marker_icon
            elif 'multimedia' in node and len(node['multimedia']) > 0:
                image = self.display.media_icon
            else:
                image = self.display.bookmark_icon if node.get("bookmark", False) else None
            tags = ["visited"] if node.get("visited", False) else ["not visited"]
            if node['id'] in self.state.calc_canonical_set():
                tags.append("canonical")
            else:
                tags.append("uncanonical")
            if not image:
                image = self.display.empty_icon
            self.display.nav_tree.insert(
                parent=node.get("parent_id", ""),
                index="end",
                iid=node["id"],
                text=self.nav_tree_name(node),
                open=node.get("open", False),
                tags=tags,
                **dict(image=image) if image else {}
            )
        self.display.nav_tree.tag_configure("not visited", background=not_visited_color())
        self.display.nav_tree.tag_configure("visited", background=visited_color())
        self.display.nav_tree.tag_configure("canonical", foreground=text_color())
        self.display.nav_tree.tag_configure("uncanonical", foreground=uncanonical_color())

    # TODO Probably move this to display
    # (Re)build the nav tree
    def update_nav_tree(self, **kwargs):
        # Save the state of opened nodes
        # open_nodes = [
        #     node_id for node_id in treeview_all_nodes(self.display.nav_tree)
        #     if self.display.nav_tree.item(node_id, "open")
        # ]
        if not self.display.nav_tree.get_children() or kwargs.get('rebuild', False):
            self.build_nav_tree()

        if 'edit' not in kwargs and 'add' not in kwargs and 'delete' not in kwargs:
            return
        else:
            delete_items = [i for i in kwargs['delete']] if 'delete' in kwargs else []
            edit_items = [i for i in kwargs['edit']] if 'edit' in kwargs else []
            add_items = [i for i in kwargs['add'] if i in self.state.tree_node_dict] if 'add' in kwargs else []

        self.display.nav_tree.delete(*delete_items)

        for id in add_items + edit_items:
            node = self.state.tree_node_dict[id]
            if id == self.state.checkpoint:
                image = self.display.marker_icon
            elif 'multimedia' in node and len(node['multimedia']) > 0:
                image = self.display.media_icon
            else:
                image = self.display.bookmark_icon if node.get("bookmark", False) else None
            tags = ["visited"] if node.get("visited", False) else ["not visited"]
            if node['id'] in self.state.calc_canonical_set():
                tags.append("canonical")
            else:
                tags.append("uncanonical")
            if not image:
                image = self.display.empty_icon
            if id in add_items:
                #print('adding id', id)
                if self.display.nav_tree.exists(id):
                    self.display.nav_tree.delete(id)
                self.display.nav_tree.insert(
                    parent=node.get("parent_id", ""),
                    index="end",
                    iid=node["id"],
                    text=self.nav_tree_name(node),
                    open=node.get("open", False),
                    tags=tags,
                    **dict(image=image) if image else {}
                )
            elif id in edit_items:
                self.display.nav_tree.item(id,
                                           text=self.nav_tree_name(node),
                                           open=node.get("open", False),
                                           tags=tags,
                                           **dict(image=image) if image else {})
        #
        # self.display.nav_tree.tag_configure("not visited", background=not_visited_color())
        # self.display.nav_tree.tag_configure("visited", background=visited_color())
        # self.display.nav_tree.tag_configure("canonical", foreground=text_color())
        # self.display.nav_tree.tag_configure("uncanonical", foreground=uncanonical_color())

        # # Restore opened state
        # for node_id in open_nodes:
        #     if node_id in self.state.tree_node_dict and self.display.nav_tree.exists(node_id):
        #         self.display.nav_tree.item(node_id, open=True)


    def update_chapter_nav_tree(self, **kwargs):
        # Delete all nodes and read them from the state tree
        self.display.chapter_nav_tree.delete(*self.display.chapter_nav_tree.get_children())

        _, chapter_tree_nodes = self.state.build_chapter_trees()

        for iid, d in chapter_tree_nodes.items():
            if 'parent_id' in d:
                parent_root_node_id = self.state.chapters[d['parent_id']]['root_id']
            else:
                parent_root_node_id = ''
            self.display.chapter_nav_tree.insert(
                parent=parent_root_node_id,
                index="end",
                iid=d["chapter"]["root_id"],
                text=d["chapter"]["title"],
                tags=["visited"],
                open=True,
            )
        self.display.nav_tree.tag_configure("visited", background=visited_color())

    # Update the node in the nav bar that appears to be selected.
    # This was needed because it can get out of sync with the tree state
    def update_nav_tree_selected(self, **kwargs):
        if self.state.selected_node is None:
            return

        # Select on the nav tree and highlight
        state_selected_id = self.state.selected_node["id"]
        navbar_selected_id = self.display.nav_tree.selection()[0] if self.display.nav_tree.selection() else None

        if navbar_selected_id != state_selected_id:
            self.display.nav_tree.selection_set(state_selected_id)  # Will cause a recursive call

        # Update the open state of all nodes based on the navbar
        # TODO
        # for node in self.state.nodes:
        #     if self.display.nav_tree.exists(node["id"]):
        #         node["open"] = self.display.nav_tree.item(node["id"], "open")

        # Update tag of node based on visited status
        d = self.state.selected_node
        tags = ["visited"] if d.get("visited", False) else ["not visited"]
        if d['id'] in self.state.calc_canonical_set():
            tags.append("canonical")
        else:
            tags.append("uncanonical")
        self.display.nav_tree.item(
            state_selected_id,
            open=self.state.selected_node.get("open", False),
            tags=tags
        )

        # Scroll to node, open it's parent nodes
        self.display.nav_tree.see(self.state.selected_node_id)
        self.set_nav_scrollbars()


    def update_chapter_nav_tree_selected(self, **kwargs):
        if self.state.selected_node is None:
            return
        chapter = self.state.chapter(self.state.selected_node)
        if not chapter:
            return

        selected_chapter_root_id = chapter["root_id"]
        navbar_selected_id = self.display.chapter_nav_tree.selection()
        navbar_selected_id = navbar_selected_id[0] if navbar_selected_id else None
        if navbar_selected_id != selected_chapter_root_id:
            self.display.chapter_nav_tree.selection_set(selected_chapter_root_id)  # Will cause a recursive call

        # Scroll to node, open it's parent nodes
        self.display.chapter_nav_tree.see(selected_chapter_root_id)
        self.set_chapter_scrollbars()


    def set_nav_scrollbars(self):
        # Taking model as source of truth!!
        def collect_visible(node):
            li = [node]
            if self.display.nav_tree.item(node["id"], "open"):
                for c in node["children"]:
                    li += collect_visible(c)
            return li


        # Visible if their parents are open or they are root
        # visible_nodes = reduce(list.__add__, [
        #     d["children"] for iid, d in self.state.tree_node_dict.items()
        #     if self.display.nav_tree.item(iid, "open") or "parent_id" not in d
        # ])
        visible_nodes = collect_visible(self.state.tree_raw_data["root"])
        visible_ids = {d["id"] for d in visible_nodes}
        # Ordered by tree order
        visible_ids = [iid for iid in self.state.tree_node_dict.keys() if iid in visible_ids]

        ############
        # Vertical  # FIXME. Breaks click to navigate. Probably a race condition with the node_selected callback
        ############
        # Set the top of the vertical scroll to the index of the element in the list of visible nodes

        # self.display.nav_tree.see(self.state.selected_node_id)
        # self.set_scrollbars.meta["i"] += 1
        # if self.set_scrollbars.meta["i"] % 2 == 0:
        # vis_start, vis_end = self.display.nav_tree.yview()
        # self.display.nav_tree.yview_moveto(vis_start)  # This does work at least...
        # self.display.nav_tree.yview_moveto(vis_start + (vis_end - vis_start)/8)
        # print("t")


        # visible_index = visible_ids.index(self.state.selected_node_id) \
        #     if self.state.selected_node_id in visible_ids else 0
        # self.display.nav_tree.yview_scroll(4, "units")

        # self.display.nav_tree.see(self.state.selected_node_id)
        # visible_index = visible_ids.index(self.state.selected_node_id) \
        #     if self.state.selected_node_id in visible_ids else 0
        # self.display.nav_tree.yview(max(0, visible_index - 7))


        # Dicts are ordered
        # visible_index = visible_ids.index(self.state.selected_node_id) \
        #     if self.state.selected_node_id in visible_ids else 0
        # self.display.nav_tree.yview(max(0, visible_index - 7))

        # Other attempts...
        # total_visible = len(visible_ids)
        # print(visible_index, total_visible, visible_index/total_visible)
        # self.display.nav_tree.yview_moveto(max(0, visible_index) / total_visible)
        # print(self.display.nav_tree.item(self.state.selected_node_id, "id"))
        # self.display.nav_tree.yview(self.display.nav_tree.item(self.state.selected_node_id, "id"))
        # self.display.nav_tree.yview_moveto(0)
        # self.display.nav_tree.yview_scroll(int(visible_index), what="units")

        ############
        ## Horizontal
        ############
        # First update the horizontal scroll width based on total depth
        # Set the horizontal scroll as a fraction based on node's depth relative to the total depth
        # Special numbers are needed to account for the width of each level of recursion

        # Magic numbers
        WIDTH_PER_INDENT = 20  # Derived...
        start_width = 200
        # offset_from_selected = -15
        offset_from_selected = -25

        open_height = max([
            depth(self.state.tree_node_dict.get(iid, {}), self.state.tree_node_dict)
            for iid in visible_ids] + [0])

        total_width = start_width + open_height * WIDTH_PER_INDENT

        self.display.nav_tree.column("#0", width=total_width, minwidth=total_width)

        current_width = depth(self.state.selected_node, self.state.tree_node_dict) \
                        * WIDTH_PER_INDENT + offset_from_selected
        self.display.nav_tree.xview_moveto(clip_num(current_width / total_width, 0, 1))

        # Some other attempted methods....
        # selected_depth = depth(self.state.selected_node)
        # max_depth = depth(self.state.tree_raw_data)
        # current_level = max_depth - selected_depth
        # self.display.nav_tree.xview_moveto(0)
        # self.display.nav_tree.xview_scroll(current_level, what="units")
        # FIXME We're going by pixels
        # self.display.nav_tree.xview_moveto(clip_num(1 - (selected_depth+2)/max_depth, 0, 1))


    # TODO duplicated from above method with minor changes because the chapter tree is quite different
    # TODO this is awful, sorry jesus. Please fix
    def set_chapter_scrollbars(self):
        def collect_visible_chapters(node):
            li = [node]
            try:
                if self.display.chapter_nav_tree.item(node["chapter"]["root_id"], "open"):
                    for c in node["children"]:
                        li += collect_visible_chapters(c)
                return li
            except Exception as e:
                print("Exception in chapter tree scrollbar!", e)
                return []

        chapter_trees, chapter_trees_dict = self.state.build_chapter_trees()
        visible_nodes = [n for c in chapter_trees for n in collect_visible_chapters(c)]
        visible_ids = {d["id"] for d in visible_nodes}
        # Ordered by tree order
        visible_ids = [iid for iid in chapter_trees_dict.keys() if iid in visible_ids]

        # Magic numbers
        WIDTH_PER_INDENT = 20
        start_width = 200
        offset_from_selected = -25

        open_height = max([
                              depth(chapter_trees_dict.get(iid, {}), chapter_trees_dict)
                              for iid in visible_ids
                          ] + [0])

        total_width = start_width + open_height * WIDTH_PER_INDENT

        self.display.chapter_nav_tree.column("#0", width=total_width, minwidth=total_width)

        selected_chapter = chapter_trees_dict[self.state.selected_chapter["id"]]
        current_width = depth(selected_chapter, chapter_trees_dict) \
                        * WIDTH_PER_INDENT + offset_from_selected
        self.display.chapter_nav_tree.xview_moveto(clip_num(current_width / total_width, 0, 1))




def main():
    attrs = [getattr(Controller, f) for f in dir(Controller)]
    funcs_with_keys = [f for f in attrs if callable(f) and hasattr(f, "meta") and "keys" in f.meta]
    pprint({f.meta["name"]: f.meta["keys"] for f in funcs_with_keys})


if __name__ == "__main__":
    main()



    # # This gets programmatic updates so we'd need to be more careful
    # # example: self.display.textbox.bind("<<TextModified>>", self.display.textbox_edited)
    # def textbox_edited(self, event):
    #     # print("edited")
    #     # self.save_edits()
    #     # self.refresh_textbox()
    #     # if self.edit_mode and self.selected_node_id:
    #     #     self.selected_node["text"] = self.display.textbox.get("1.0", 'end-1c')

