import functools
import os
import tkinter as tk
import threading
from collections import defaultdict, ChainMap
import time
from functools import reduce
from pprint import pprint
from tkinter import filedialog, ttk
from tkinter import messagebox
from tkinter.font import Font
import re
import datetime

import PIL
import pyperclip
import bisect

import traceback

from view.colors import history_color, not_visited_color, visited_color, ooc_color, text_color, uncanonical_color, \
    immutable_color
from view.display import Display
from components.dialogs import *
from model import TreeModel
from util.util import clip_num, metadata, diff, split_indices, diff_linesToWords
from util.util_tree import ancestry_in_range, depth, height, flatten_tree, stochastic_transition, node_ancestry, subtree_list, \
    node_index, nearest_common_ancestor, filtered_children
from util.gpt_util import logprobs_to_probs, parse_logit_bias
from util.textbox_util import distribute_textbox_changes
from util.keybindings import tkinter_keybindings
from view.icons import Icons
from difflib import SequenceMatcher
from diff_match_patch import diff_match_patch
import json
from view.colors import edit_color, bg_color


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
        self.icons = Icons()

        self.register_model_callbacks()
        self.setup_key_bindings()
        self.build_menus()
        self.ancestor_end_indices = None
        self.nav_history = []
        self.undo_history = []


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
        self.state.register_callback(self.state.tree_updated, self.fix_selection)
        self.state.register_callback(self.state.tree_updated, self.update_nav_tree_selected)
        self.state.register_callback(self.state.tree_updated, self.update_chapter_nav_tree)
        self.state.register_callback(self.state.tree_updated, self.update_chapter_nav_tree_selected)
        # TODO save_edits causes tree_updated...
        self.state.register_callback(self.state.tree_updated, self.save_edits)
        self.state.register_callback(self.state.tree_updated, self.refresh_textbox)
        self.state.register_callback(self.state.tree_updated, self.refresh_visualization)
        self.state.register_callback(self.state.tree_updated, self.refresh_display)
        self.state.register_callback(self.state.tree_updated, self.setup_custom_key_bindings)
        self.state.register_callback(self.state.tree_updated, self.modules_tree_updated)
        # TODO autosaving takes too long for a big tree
        self.state.register_callback(self.state.tree_updated, lambda **kwargs: self.save_tree(popup=False,
                                                                                              autosave=True))

        # Before the selection is updated, save edits
        self.state.register_callback(self.state.pre_selection_updated, self.save_edits)

        # When the selection is updated, refresh the nav selection and textbox
        self.state.register_callback(self.state.selection_updated, self.fix_selection)
        self.state.register_callback(self.state.selection_updated, self.update_nav_tree_selected)
        self.state.register_callback(self.state.selection_updated, self.update_chapter_nav_tree_selected)
        self.state.register_callback(self.state.selection_updated, self.refresh_textbox)
        self.state.register_callback(self.state.selection_updated, self.refresh_alt_textbox)
        self.state.register_callback(self.state.selection_updated, self.refresh_vis_selection)
        self.state.register_callback(self.state.selection_updated, self.refresh_counterfactual_meta)
        self.state.register_callback(self.state.selection_updated, self.refresh_display)
        self.state.register_callback(self.state.selection_updated, self.modules_selection_updated)


    def bind(self, tk_key, f):
        def in_edit():
            return self.display.mode in ["Edit", "Child Edit"] \
                   or (self.display.mode == "Visualize" and self.display.vis.textbox) \
                   or self.has_focus(self.display.search_box) or self.module_textbox_has_focus() \
                   or self.state.preferences['editable'] and self.has_focus(self.display.textbox)
        
        valid_keys_outside_edit = ["Control", "Alt", "Escape", "Delete", "Command"]

        inside_edit = any(v in tk_key for v in valid_keys_outside_edit)

        self.root.bind(tk_key, no_junk_args(f if inside_edit else gated_call(f, lambda: not in_edit())))


    def setup_key_bindings(self):
        attrs = [getattr(self, f) for f in dir(self)]
        funcs_with_keys = [f for f in attrs if callable(f) and hasattr(f, "meta") and "keys" in f.meta]

        for f in funcs_with_keys:
            for tk_key in f.meta["keys"]:
                self.bind(tk_key, f)

        # Numbers to select children
        # TODO fix this
        for i in range(1, 6):
            i = i % 10
            f = lambda _i=i: self.child(idx=_i-1)
            self.bind(f"<Key-{i}>", f)

    
    def setup_custom_key_bindings(self, **kwargs):
        for tag, properties in self.state.tags.items():
            if properties['toggle_key'] != 'None':
                f = lambda _tag=tag: self.toggle_tag(_tag)
                tk_key = tkinter_keybindings(properties['toggle_key'])
                self.bind(tk_key, f)

    def build_menus(self):
        # Tuple of 4 things: Name, Hotkey display text, tkinter key to bind to, function to call (without arguments)
        menu_list = {
            "View": [
                ('Toggle side pane', 'Alt-P', None, no_junk_args(self.toggle_side)),
                ('Toggle bottom pane', 'Alt-B', None, no_junk_args(self.toggle_bottom)),
                ('Toggle visualize mode', 'J', None, no_junk_args(self.toggle_visualization_mode)),
                ('Toggle children', 'Alt-C', None, no_junk_args(self.toggle_show_children)),
                "-",
                ('Reset zoom', 'Ctrl-0', None, no_junk_args(self.reset_zoom)),
                ('Center view', 'L, Ctrl-L', None, no_junk_args(self.center_view)),
                "-",
                ('Hoist subtree', 'Alt-H', None, no_junk_args(self.hoist)),
                ('Unhoist subtree', 'Alt-Shift-H', None, no_junk_args(self.unhoist)),
                ('Unhoist all', '', None, no_junk_args(self.unhoist_all)),
                ('Collapse node', 'Ctrl-?', None, no_junk_args(self.collapse_node)),
                ('Collapse subtree', 'Ctrl-minus', None, no_junk_args(self.collapse_subtree)),
                ('Collapse all except subtree', 'Ctrl-:', None, no_junk_args(self.collapse_all_except_subtree)),
                ('Expand children', 'Ctrl-\"', None, no_junk_args(self.expand_node)),
                ('Expand subtree', 'Ctrl-+', None, no_junk_args(self.expand_subtree)),
                ('Unzip', '', None, no_junk_args(self.unzip_node)),
                ('Zip chain', '', None, no_junk_args(self.zip_chain)),
                ('Zip all', '', None, no_junk_args(self.zip_all_chains)),
                ('Unzip all', '', None, no_junk_args(self.unzip_all)),
                ('Show hidden children', '', None, no_junk_args(self.show_hidden_children)),
                ('Hide invisible children', '', None, no_junk_args(self.hide_invisible_children)),
            ],
            "Edit": [
                ('Edit node', 'Ctrl+E', None, no_junk_args(self.toggle_edit_mode)),
                ('Toggle textbox editable', 'Alt+Shift+E', None, no_junk_args(self.toggle_editable)),
                "-",
                ("New root child", 'Ctrl+Shift+H', None, no_junk_args(self.create_root_child)),
                ("Create parent", 'Alt-Left', None, no_junk_args(self.create_parent)),
                ("Change parent", 'Shift-P', None, no_junk_args(self.change_parent)),
                ("New child", 'H, Ctrl+H, Alt+Right', None, no_junk_args(self.create_child)),
                ("New sibling", 'Alt+Down', None, no_junk_args(self.create_sibling)),
                ("Merge with parent", 'Shift+Left', None, no_junk_args(self.merge_parent)),
                ("Merge with children", 'Shift+Right', None, no_junk_args(self.merge_children)),
                ("Move up", 'Shift+Up', None, no_junk_args(self.move_up)),
                ("Move down", 'Shift+Down', None, no_junk_args(self.move_down)),
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
                ("Next Bookmark", "D", None, no_junk_args(self.next_bookmark)),
                ("Prev Bookmark", "A", None, no_junk_args(self.prev_bookmark)),
                ("Stochastic walk", "W", None, no_junk_args(self.walk)),
                ("Search ancestry", "Ctrl+F", None, no_junk_args(self.search_ancestry)),
                ("Search tree", "Ctrl+Shift+F", None, no_junk_args(self.search)),
                ("Goto node by id", "Ctrl+Shift+G", None, no_junk_args(self.goto_node_dialog)),

            ],
            "Generation": [
                ('Generation settings', 'Ctrl+shift+p', None, no_junk_args(self.generation_settings_dialog)),
                ('Generate', 'G, Ctrl+G', None, no_junk_args(self.generate)),
                #('View summaries', '', None, no_junk_args(self.view_summaries)),

            ],
            "Memory": [
                ('AI Memory', 'Ctrl+Shift+M', None, no_junk_args(self.ai_memory)),
                ('Create memory', 'Ctrl+M', None, no_junk_args(self.add_memory)),
                ('Node memory', 'Alt+M', None, no_junk_args(self.node_memory)),
            ],
            "Flags": [
                ("Tag node", None, None, no_junk_args(self.tag_node)),
                ("Add tag", None, None, no_junk_args(self.add_tag)),
                ("Configure tags", None, None, no_junk_args(self.configure_tags)),
                ("Mark node visited", None, None, lambda: self.set_visited(True)),
                ("Mark node unvisited", None, None, lambda: self.set_visited(False)),
                ("Edit chapter", "Ctrl+Y", None, no_junk_args(self.chapter_dialog)),

            ],
            "Settings": [
                ('Preferences', 'Ctrl+P', None, no_junk_args(self.preferences)),
                ('Generation settings', 'Ctrl+shift+p', None, no_junk_args(self.generation_settings_dialog)),
                ('Inline generation settings', None, None, no_junk_args(self.inline_generation_settings_dialog)),
                ('Visualization settings', 'Ctrl+U', None, no_junk_args(self.visualization_settings_dialog)),
                ('Chat settings', None, None, no_junk_args(self.chat_dialog)),
                ('Model config', None, None, no_junk_args(self.model_config_dialog)),
                #('Settings', None, None, no_junk_args(self.settings))

            ],
            "Developer": [
                ('Run code', 'Ctrl+Shift+B', None, no_junk_args(self.run)),

            ],
            "Info": [
                ("Tree statistics", "I", None, no_junk_args(self.info_dialog)),
                ('Multimedia', 'U', None, no_junk_args(self.multimedia_dialog)),
                ('Node metadata', 'Ctrl+Shift+N', None, no_junk_args(self.node_info_dialogue)),
            ],
        }
        return menu_list



    @metadata(name='Debug', keys=["<Control-Shift-KeyPress-D>"])
    def debug(self, event=None):
        #self.display.textbox.fix_selection()
        #self.write_textbox_changes()
        # makes text copyable
        self.display.textbox.bind("<Button>", lambda e: self.display.textbox.focus_set())
        #print(self.display.textbox)
        print('debug')

    # @metadata(name='Generate', keys=["<Control-G>", "<Control-KeyPress-G>"])
    # def generate(self, event=None):
    #     self.generate_dialog()

    @metadata(name='View summaries', keys=["<Control-KeyPress-V>"])
    def view_summaries(self, event=None):
        self.view_summaries_dialog()

    @metadata(name='AI Memory', keys=["<Control-KeyPress-M>"])
    def ai_memory(self, event=None):
        self.ai_memory_dialog()

    @metadata(name='Create memory', keys=["<Control-KeyPress-M>"])
    def add_memory(self, event=None):
        self.add_memory_dialog()

    @metadata(name='Node memory', keys=["<Alt-KeyPress-M>"])
    def node_memory(self, event=None):
        self.node_memory_dialog()

    @metadata(name='Search ancestry', keys=["<Control-KeyPress-F>"])
    def search_ancestry(self, event=None):
        self.search_ancestry_dialog()

    @metadata(name='Search tree', keys=["<Control-Shift-KeyPress-F>"])
    def search(self, event=None):
        self.search_dialog()

    #################################
    #   Navigation
    #################################

    # @metadata(name=, keys=, display_key=)
    @metadata(name="Next", keys=["<period>", "<Return>", "<Control-period>"], display_key=">")
    def next(self, node=None):
        node = node if node else self.state.selected_node
        self.select_node(node=self.state.node(self.state.find_next(node=node, visible_filter=self.in_nav)))

    @metadata(name="Prev", keys=["<comma>", "<Control-comma>"], display_key="<",)
    def prev(self, node=None):
        node = node if node else self.state.selected_node
        self.select_node(node=self.state.node(self.state.find_prev(node=node, visible_filter=self.in_nav)))

    @metadata(name="Go to parent", keys=["<Left>", "<Control-Left>"], display_key="←")
    def parent(self, node=None):
        node = node if node else self.state.selected_node
        parent = self.state.parent(node)
        if parent:
            self.select_node(node=parent)

    @metadata(name="Go to child", keys=["<Right>", "<Control-Right>"], display_key="→")
    def child(self, node=None, idx=0):
        node = node if node else self.state.selected_node
        child = self.state.child(node, idx, filter=self.in_nav)
        if child is not None:
            self.select_node(node=child)

    @metadata(name="Go to next sibling", keys=["<Down>", "<Control-Down>"], display_key="↓")
    def next_sibling(self, node=None):
        node = node if node else self.state.selected_node
        self.select_node(node=self.state.sibling(node, 1, filter=self.in_nav))

    @metadata(name="Go to previous Sibling", keys=["<Up>", "<Control-Up>"], display_key="↑")
    def prev_sibling(self, node=None): 
        node = node if node else self.state.selected_node
        self.select_node(node=self.state.sibling(node, -1, filter=self.in_nav))

    @metadata(name="Walk", keys=["<Key-w>", "<Control-w>"], display_key="w")
    def walk(self, node=None, filter=None):
        # TODO custom probs
        node = node if node else self.state.selected_node
        filter = filter if filter else self.in_nav
        if 'children' in node and len(node['children']) > 0:
            chosen_child = stochastic_transition(node, mode='leaves', filter=filter)
            self.select_node(node=chosen_child)

    @metadata(name="Return to root", keys=["<Key-r>", "<Control-r>"], display_key="r")
    def return_to_root(self):
        self.select_node(node=self.state.root())

    @metadata(name="Save checkpoint", keys=["<Control-t>"], display_key="ctrl-t")
    def save_checkpoint(self, node=None):
        node = node if node else self.state.selected_node
        self.state.checkpoint = node['id']
        self.state.tree_updated(edit=[node['id']])

    @metadata(name="Go to checkpoint", keys=["<Key-t>"], display_key="t")
    def goto_checkpoint(self):
        if self.state.checkpoint:
            self.select_node(node=self.state.node(self.state.checkpoint))

    @metadata(name="Nav Select")
    def nav_select(self, *, node_id, open=False):
        if not node_id or node_id == self.state.selected_node_id:
            return
        if self.change_parent.meta["click_mode"]:
            self.change_parent(node=self.state.node(node_id))
        # TODO This causes infinite recursion from the vis node. Need to change how updating open status works
        # Update the open state of the node based on the nav bar
        # node = self.state.node(node_id]
        # node["open"] = self.display.nav_tree.item(node["id"], "open")
        #self.state.select_node(node_id)
        self.select_node(node=self.state.node(node_id), open=open)

    # figure out scope and whether should add, edit, delete
    @metadata(name="Tag")
    def toggle_tag(self, tag, node=None):
        node = node if node else self.state.selected_node
        self.state.toggle_tag(node, tag)
        self.state.update_tree_tag_changed(node, tag)

    @metadata(name="Toggle prompt", keys=["<asterisk>"], display_key="")
    def toggle_prompt(self, node=None):
        self.state.preferences['show_prompt'] = not self.state.preferences['show_prompt']
        self.refresh_textbox()

    def next_tag(self, tag, node=None):
        node = node if node else self.state.selected_node
        next_tag_id = self.state.find_next(node=node, filter=lambda node: self.state.has_tag_attribute(node, tag),
                                           visible_filter=self.in_nav)
        self.select_node(self.state.node(next_tag_id))

    def prev_tag(self, tag, node=None):
        node = node if node else self.state.selected_node
        prev_tag_id = self.state.find_prev(node=node, filter=lambda node: self.state.has_tag_attribute(node, tag),
                                           visible_filter=self.in_nav)
        self.select_node(self.state.node(prev_tag_id))

    @metadata(name="Go to next bookmark", keys=["<Key-d>", "<Control-d>"])
    def next_bookmark(self):
        self.next_tag(self.state.preferences.get("nav_tag", "bookmark"))

    @metadata(name="Go to prev bookmark", keys=["<Key-a>", "<Control-a>"])
    def prev_bookmark(self):
        self.prev_tag(self.state.preferences.get("nav_tag", "bookmark"))

    @metadata(name="Center view", keys=["<Key-l>", "<Control-l>"])
    def center_view(self):
        #self.display.vis.center_view_on_canvas_coords(*self.display.vis.node_coords[self.state.selected_node_id])
        #self.display.vis.center_view_on_node(self.state.selected_node)
        pass

    def update_read_color(self, old_node, node):
        if self.display.mode == 'Read':
            pass
            # nca_node, index = nearest_common_ancestor(old_node, node, self.state.tree_node_dict)
            # ancestor_indices = self.state.ancestor_text_indices(self.state.selected_node)
            # ancestor_end_indices = [ind[1] for ind in ancestor_indices]
            # nca_end_index = ancestor_end_indices[index]
            # self.display.textbox.tag_delete("old")
            # self.display.textbox.tag_add("old",
            #                              "1.0",
            #                              f"1.0 + {nca_end_index} chars")
            # self.display.textbox.tag_config("old", foreground=history_color())
            # self.display.textbox.see(f"1.0 + {nca_end_index} chars")
            # pass

            #print('coloring text')

    @metadata(name="In nav")
    def in_nav(self, node):
        return self.display.nav_tree.exists(node['id'])

    @metadata(name="Select node")
    def select_node(self, node, noscroll=False, ask_reveal=True, open=True):
        if node == self.state.selected_node:
            return
        if not self.in_nav(node):
            if ask_reveal:
                if not self.ask_reveal(node):
                    return
            else:
                self.reveal_node(node)
        if not self.state.selected_node:
            # if no selected node (probably previous node was deleted), just select
            self.state.select_node(node['id'])
        #print('writing textbox changes')
        self.write_textbox_changes()
        if open:
            node['open'] = True
            self.refresh_nav_node(node)
        else:
            node['open'] = self.display.nav_tree.item(node["id"], "open")
        self.nav_history.append(self.state.selected_node_id)
        self.undo_history = []
        self.state.select_node(node['id'])
        # if self.state.preferences['coloring'] == 'read':
        #     old_node = self.state.selected_node
        #     self.state.select_node(node['id'], noscroll=True)
        #     if old_node:
        #         self.update_read_color(old_node, node)

        # else:
            #self.state.select_node(node['id'])

    @metadata(name="Update text")
    def update_text(self, text, node=None):
        node = node if node else self.state.selected_node
        self.state.update_text(node, text, save_revision_history=self.state.preferences['revision_history'])

    @metadata(name="<", keys=["<Command-minus>", "<Alt-minus>"])
    def prev_selection(self):
        if self.nav_history:
            self.undo_history.append(self.state.selected_node_id)
            self.state.select_node(self.nav_history.pop())

    @metadata(name=">", keys=["<Command-equal>", "<Alt-equal>"])
    def next_selection(self):
        if self.undo_history:
            self.nav_history.append(self.state.selected_node_id)
            self.state.select_node(self.undo_history.pop())

    @metadata(name="Undo")
    def undo_action(self):
        # this navigates to the parent of the last non-AI generated node
        ancestry = self.state.ancestry(self.state.selected_node)
        if len(ancestry) > 1:
            for ancestor in ancestry[::-1]:
                if not self.state.is_AI_generated(ancestor):
                    self.parent(node=ancestor)
                    return

    @metadata(name="Rewind")
    def rewind(self, node=None, filter=None):
        # navigates to previous node in ancestry with more than one child
        node = node if node else self.state.selected_node
        ancestry = self.state.ancestry(node)[:-1]
        if len(ancestry) > 1:
            for ancestor in ancestry[::-1]:
                children = self.get_children(ancestor, filter=filter)
                if len(children) > 1:
                    self.select_node(ancestor)
                    return
        

    @metadata(name="Reroll")
    def alternate(self, node=None):
        node = node if node else self.state.selected_node
        next_sibling = self.state.sibling(node, wrap=True, filter=self.in_nav)
        self.select_node(next_sibling)

    #################################
    #   Getters
    #################################

    @metadata(name="Get children")
    def get_children(self, node=None, filter=None):
        node = node if node else self.state.selected_node
        filter = filter if filter else self.in_nav
        return filtered_children(node, filter)

    @metadata(name="Hidden children")
    def get_hidden_children(self, node=None):
        node = node if node else self.state.selected_node
        return [n for n in node['children'] if not self.state.visible(n)]

    @metadata(name="Text")
    def get_text(self, node_id=None, raw=False):
        node_id = node_id if node_id else self.state.selected_node_id
        return self.state.text(self.state.node(node_id), raw=raw)#self.state.node(node_id)['text']

    @metadata(name="Get floating notes")
    def get_floating_notes(self, tag='note', node=None):
        node = node if node else self.state.selected_node
        ancestry = self.state.ancestry(node)
        notes = []
        for ancestor in reversed(ancestry):
            for child in ancestor['children']:
                if self.state.has_tag(child, tag) and child != node:
                    notes.append(child)
        return notes

    @metadata(name="Pinned")
    def get_pinned(self):
        pinned = self.state.tagged_nodes(tag='pinned')
        return pinned

    @metadata(name="Prompt")
    def prompt(self, node=None):
        node = node if node else self.state.selected_node
        return self.state.prompt(node)

    @metadata(name="Get text attribute")
    def get_text_attribute(self, attribute, node=None):
        node = node if node else self.state.selected_node
        return self.state.get_text_attribute(node, attribute)

    #################################
    #   Node operations
    #################################

    @metadata(name="New root child", keys=["<Control-Shift-KeyPress-H>"], display_key="ctrl-shift-h" )
    def create_root_child(self):
        self.create_child(node=self.state.root())

    @metadata(name="New Child", keys=["<h>", "<Control-h>", "<Command-Right>", "<Alt-Right>"], display_key="h",)
    def create_child(self, node=None, update_selection=True, toggle_edit=True, text=''):
        node = node if node else self.state.selected_node
        new_child = self.state.create_child(parent=node, text=text)
        self.state.tree_updated(add=[new_child['id']])
        self.state.node_creation_metadata(new_child, source='prompt')
        if update_selection:
            self.select_node(new_child, ask_reveal=False)
            if self.display.mode == "Read" and toggle_edit and not self.state.preferences['editable']:
                self.toggle_edit_mode()
        return new_child

    @metadata(name="New Sibling", keys=["<Command-Down>", "<Alt-Down>"], display_key="Command-down")
    def create_sibling(self, node=None, toggle_edit=True):
        node = node if node else self.state.selected_node
        new_sibling = self.state.create_sibling(node=node)
        self.state.tree_updated(add=[new_sibling['id']])
        self.select_node(new_sibling, ask_reveal=False)
        self.state.node_creation_metadata(new_sibling)
        if self.display.mode == "Read" and toggle_edit and not self.state.preferences['editable']:
            self.toggle_edit_mode()
        return new_sibling

    @metadata(name="New Parent", keys=["<Command-Left>", "<Alt-Left>"], display_key="Command-left")
    def create_parent(self, node=None):
        node = node if node else self.state.selected_node
        new_parent = self.state.create_parent(node=node)
        self.state.tree_updated(add=[new_parent['id']])
        self.state.tree_updated(add=[n['id'] for n in subtree_list(new_parent, filter=self.in_nav)])
        self.state.node_creation_metadata(new_parent, source='prompt')
        return new_parent

    @metadata(name="New note")
    def new_note(self, node=None):
        node = node if node else self.state.selected_node
        new_child = self.state.create_child(parent=node)
        self.state.tag_node(new_child, 'note')
        if self.state.visible(new_child):
            self.state.tree_updated(add=[new_child['id']])
        else:
            self.state.tree_updated()
        return new_child


    @metadata(name="Change Parent", keys=["<Shift-P>"], display_key="shift-p", selected_node=None, click_mode=False)
    def change_parent(self, node=None, click_mode=False):
        node = node if node else self.state.selected_node
        if self.change_parent.meta["selected_node"] is None:
            self.display.change_cursor("fleur")
            self.change_parent.meta["selected_node"] = node
            self.change_parent.meta["click_mode"] = click_mode
        else:
            self.display.change_cursor("arrow")
            self.state.change_parent(node=self.change_parent.meta["selected_node"], new_parent_id=node["id"])
            self.state.tree_updated(add=[n['id'] for n in subtree_list(self.change_parent.meta["selected_node"],
                                                                       filter=self.in_nav)])
            self.change_parent.meta["selected_node"] = None
            self.change_parent.meta["click_mode"] = False

    @metadata(name="Merge with Parent", keys=["<Shift-Left>"], display_key="shift-left",)
    def merge_parent(self, node=None):
        node = node if node else self.state.selected_node
        if not self.state.is_mutable(node):
            self.immutable_popup(node)
            return
        parent = self.state.parent(node)
        if not self.state.is_mutable(parent):
            self.immutable_popup(parent)
            return
        self.state.merge_with_parent(node=node)
        self.state.tree_updated(add=[n['id'] for n in subtree_list(parent, filter=self.in_nav)])
        self.select_node(parent, ask_reveal=False)

    @metadata(name="Merge with children", keys=["<Shift-Right>"], display_key="shift-right")
    def merge_children(self, node=None):
        node = node if node else self.state.selected_node
        if not node['children']:
            print('no children')
            return
        if not self.state.is_mutable(node):
            self.immutable_popup(node)
            return
        children = node['children']
        for child in children:
            if not self.state.is_mutable(child):
                self.immutable_popup(child)
                return
        visible_children = filtered_children(node, filter=self.in_nav)
        self.state.merge_with_children(node=node)
        self.state.tree_updated(add=[n['id'] for n in subtree_list(self.state.parent(node), filter=self.in_nav)])
        if visible_children:
            self.select_node(visible_children[0])

    @metadata(name="Move up", keys=["<Shift-Up>"], display_key="shift-up")
    def move_up(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.shift(node, -1)
        self.state.tree_updated(add=[n['id'] for n in subtree_list(self.state.parent(node), filter=self.in_nav)])

    @metadata(name="Move down", keys=["<Shift-Down>"], display_key="shift-down")
    def move_down(self, node=None):
        if node is None:
            node = self.state.selected_node
        self.state.shift(node, 1)
        self.state.tree_updated(add=[n['id'] for n in subtree_list(self.state.parent(node), filter=self.in_nav)])

    @metadata(name="Generate", keys=["<g>", "<Control-g>"], display_key="g")
    def generate(self, node=None, **kwargs):
        if node is None:
            node = self.state.selected_node
        try:
            node["open"] = True
            self.display.nav_tree.item(node['id'], open=True)
        except Exception as e:
            print(str(e))
        self.state.generate_continuations(node=node, **kwargs)


    @metadata(name="Retry")
    def retry(self, node=None):
        # if node has a next sibling, select it
        # otherwise, navigate to parent, generate again, and select first newly generated node
        node = node if node else self.state.selected_node
        if self.state.is_AI_generated(node):
            next_sibling = self.state.sibling(node, wrap=False, filter=self.in_nav)
            self.select_node(next_sibling)
            if not self.state.is_AI_generated(self.state.selected_node):
                # moved to parent
                self.generate(update_selection=True, placeholder="")
        else:
            self.generate(update_selection=True, placeholder="")


    # def propagate_wavefunction(self):
    #     if self.display.mode == "Multiverse":
    #         if self.display.multiverse.active_wavefunction():
    #             active_node = self.display.multiverse.active_info()
    #             start_position = (active_node['x'], active_node['y'])
    #             multiverse, ground_truth, prompt = self.state.generate_greedy_multiverse(max_depth=4, prompt=active_node['prefix'],
    #                                                                              unnormalized_amplitude=active_node['amplitude'],
    #                                                                              ground_truth="",
    #                                                                              threshold=0.04,
    #                                                                              engine='ada')
    #         else:
    #             start_position = (0, 0)
    #             multiverse, ground_truth, prompt = self.state.generate_greedy_multiverse(max_depth=4, ground_truth="",
    #                                                                              threshold=0.04,
    #                                                                              engine='ada')
    #         self.display.multiverse.draw_multiverse(multiverse=multiverse, ground_truth=ground_truth,
    #                                                 start_position=start_position, prompt=prompt)

    @metadata(name="Delete", keys=["<BackSpace>", "<Control-BackSpace>"], display_key="«")
    def delete_node(self, node=None, reassign_children=False, ask=True, ask_text="Delete node and subtree?", refresh_nav=True):
        node = node if node else self.state.selected_node
        if not node:
            return
        if node == self.state.root():
            messagebox.showerror("Root", "Cannot delete root")
            return
        if ask:
            result = messagebox.askquestion("Delete", ask_text, icon='warning')
            if result != 'yes':
                return False
        next_sibling = self.state.sibling(node, wrap=False, filter=self.in_nav)
        self.state.delete_node(node=node, reassign_children=reassign_children)
        if self.state.selected_node_id == node['id']:
            self.select_node(next_sibling)
        if self.in_nav(node) and refresh_nav:
            self.state.tree_updated(delete=[node['id']])
        else:
            self.state.tree_updated()
        return True

    @metadata(name="Delete children")
    def delete_children(self, ask=True, node=None):
        node = node if node else self.state.selected_node
        if not node:
            return
        if not node['children']:
            return
        children = node['children']
        child_ids = [n['id'] for n in children]
        if ask:
            result = messagebox.askquestion("Delete", f"Delete {len(children)} children and subtrees?", icon='warning')
            if result != 'yes':
                return
        for child in children:
            self.delete_node(child, reassign_children=False, ask=False, refresh_nav=False)
        self.state.tree_updated(delete=child_ids)#n['id'] for n in subtree_list(node, filter=self.in_nav) if n != node])

    @metadata(name="Archive children")
    def archive_children(self, node=None):
        node = node if node else self.state.selected_node
        if not node:
            return
        if not node['children']:
            return
        children = node['children']
        for child in children:
            self.state.tag_node(child, "archived")
            self.state.update_tree_tag_changed(node, "archived")


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
    def split_node(self, index, change_selection=True, node=None):
        node = node if node else self.state.selected_node
        if self.display.mode == "Read":
            if self.state.is_template(node):
                #TODO
                return
            self.write_textbox_changes()
            ancestor_index, selected_ancestor = self.index_to_ancestor(index)
            ancestor_end_indices = [ind[1] for ind in self.state.ancestor_text_indices(node)]
            negative_offset = ancestor_end_indices[ancestor_index] - index
            split_index = len(selected_ancestor['text']) - negative_offset
            new_parent, _ = self.state.split_node(selected_ancestor, split_index)
            self.state.tree_updated(add=[new_parent['id']])
            self.state.tree_updated(add=[n['id'] for n in subtree_list(self.state.parent(new_parent), filter=self.in_nav)])
            if change_selection:
                self.nav_select(node_id=new_parent["id"])
            # TODO deal with metadata

    def zip_chain(self, node=None):
        node = node if node else self.state.selected_node
        self.state.zip_chain(node, filter=self.in_nav, refresh_nav=True, update_selection=True)

    @metadata(name="Unzip node")
    def unzip_node(self, node=None):
        node = node if node else self.state.selected_node
        self.state.unzip(node, filter=self.state.visible)

    def zip_all_chains(self):
        editable = False
        # temporarily disable editable textbox so that text isn't overwritten
        if self.state.preferences.get('editable', False):
            editable = True
            self.state.update_user_frame(update={'preferences': {'editable': False}})
        self.state.zip_all_chains(filter=self.in_nav)
        self.state.tree_updated(rebuild=True, write=False)
        self.state.select_node(self.state.tree_raw_data['root']['id'], write=False)
        # TODO hack
        if editable:
            self.state.update_user_frame(update={'preferences': {'editable': True}})

    def unzip_all(self):
        editable = False
        if self.state.preferences.get('editable', False):
            editable = True
            self.state.update_user_frame(update={'preferences': {'editable': False}})
        self.state.unzip_all(filter=self.state.visible)
        self.state.tree_updated(rebuild=True, write=False)
        self.state.select_node(self.state.tree_raw_data['root']['id'], write=False)
        # TODO hack
        if editable:
            self.state.update_user_frame(update={'preferences': {'editable': True}})


    #################################
    #   Textbox
    #################################


    @metadata(name="Textbox menu")
    def textbox_menu(self, char_index, tk_current, e):
        _, clicked_node = self.index_to_ancestor(char_index)
        node_range = self.node_range(clicked_node)
        self.display.textbox.tag_add("node_select", f"1.0 + {node_range[0]} chars", f"1.0 + {node_range[1]} chars")
        
        menu = tk.Menu(self.display.vis.textbox, tearoff=0)
        if self.display.textbox.tag_ranges("sel"):
            menu.add_command(label="Copy", command=lambda: self.display.textbox.copy_selected())

        menu.add_command(label="Go", command=lambda: self.select_node(clicked_node))
        menu.add_command(label="Edit", command=lambda: self.edit_in_module(clicked_node))
        menu.add_command(label="Split", command=lambda: self.split_node(char_index, change_selection=True))
        # TODO
        #menu.add_command(label="Generate")
        #menu.add_command(label="Add memory")
        # splice_menu = tk.Menu(menu, tearoff=0)
        # splice_menu.add_command(label="Obliviate")
        # splice_menu.add_command(label="Inject")
        # if self.display.textbox.tag_ranges("sel"):
        #     splice_menu.add_command(label="Mask")
        #     splice_menu.add_command(label="Open window from...")
        # splice_menu.add_command(label="Open window to...")
        # splice_menu.add_command(label="Custom splice")

        #menu.add_cascade(label="Splice", menu=splice_menu)
        
        #menu.add_command(label="Annotate")
        # if there is text selected
        if self.display.textbox.tag_ranges("sel"):
            selection_menu = tk.Menu(menu, tearoff=0)
            #TODO
            # save_menu = tk.Menu(selection_menu, tearoff=0)
            # save_menu.add_command(label="Save text")
            # save_menu.add_command(label="Save window")
            # save_menu.add_command(label="Save as memory")
            # selection_menu.add_cascade(label="Save", menu=save_menu)
            #selection_menu.add_command(label="Substitute")
            transform_menu = tk.Menu(menu, tearoff=0)
            transform_menu.add_command(label="Prose to script", command=lambda: self.open_selection_in_transformer(template='./config/transformers/prose_to_script.json'))
            selection_menu.add_cascade(label="Transform", menu=transform_menu)
            
            #selection_menu.add_command(label="Transform", command=lambda: self.open_selection_in_transformer())
            # selection_menu.add_command(label="Link")
            # selection_menu.add_command(label="Add summary")
            # selection_menu.add_command(label="Delete")

            menu.add_cascade(label="Selection", menu=selection_menu)

        tag_menu = tk.Menu(menu, tearoff=0)

        # tag_menu.add_command(label="Pin")
        # tag_menu.add_command(label="Tag...")
        
        # menu.add_cascade(label="Tag", menu=tag_menu)
        #menu.add_command(label="Copy node")
        menu.add_command(label="Copy id", command=lambda: self.copy_id(clicked_node))

        menu.tk_popup(e.x_root, e.y_root + 8)


    def generate_template(self, inputs, template_file):
        # open template file json
        with open(template_file, 'r') as f:
            template_dict = json.load(f)
        template = template_dict['template']
        prompt = eval(f'f"""{template}"""')
        

    def refresh_textbox(self, **kwargs):
        #print('refresh textbox')
        if not self.state.tree_raw_data or not self.state.selected_node:
            return
        self.display.clear_selection_tags(self.display.textbox)
        self.display.textbox.configure(font=Font(family="Georgia", size=self.state.preferences['font_size']),
                                       spacing1=self.state.preferences['paragraph_spacing'],
                                       spacing2=self.state.preferences['line_spacing'],
                                       background=edit_color() if self.state.preferences["editable"] or self.display.mode == "Edit" else bg_color())
        #self.display.textbox.tag_config("node_select", font=Font(family="Georgia", size=self.state.preferences['font_size'], weight="bold"))

        # Fill textbox with text history, disable editing
        if self.display.mode == "Read":
            #self.display.textbox.tag_config("sel", background="black", foreground=text_color())

            self.display.textbox.configure(state="normal")
            self.display.textbox.delete("1.0", "end")

            # if self.state.preferences.get('show_prompt', False):
            #     self.display.textbox.insert("end-1c", self.state.prompt(self.state.selected_node))
            # else:
            if self.state.preferences['coloring'] in ('edit', 'read'):
                self.display.textbox.tag_config('ooc_history', foreground=ooc_color())
                self.display.textbox.tag_config('history', foreground=history_color())
            else:
                self.display.textbox.tag_config('ooc_history', foreground=text_color())
                self.display.textbox.tag_config('history', foreground=text_color())

            ancestry = self.state.ancestor_text_list(self.state.selected_node)
            #self.ancestor_end_indices = indices
            history = ''
            for node_text in ancestry[:-1]:
                # "end" includes the automatically inserted new line
                history += node_text
            selected_text = self.state.text(self.state.selected_node)#self.state.selected_node["text"]
            prompt_length = self.state.generation_settings['prompt_length'] - len(selected_text)

            in_context = history[-prompt_length:]
            if prompt_length < len(history):
                out_context = history[:len(history)-prompt_length]
                self.display.textbox.insert("end-1c", out_context, "ooc_history")
            self.display.textbox.insert("end-1c", in_context, "history")

            history_end = self.display.textbox.index(tk.END)
            self.display.textbox.insert("end-1c", selected_text)

            active_append_text = self.state.get_text_attribute(self.state.selected_node, 'active_append')
            if active_append_text:
                self.display.textbox.insert("end-1c", active_append_text)

            self.tag_prompts()
            if not kwargs.get('noscroll', False):
                self.display.textbox.update_idletasks()
                if self.state.preferences['coloring'] == 'edit':
                    self.display.textbox.see(tk.END)
                else:
                    self.display.textbox.see(history_end)

            if not self.state.preferences.get('editable', False):
                self.display.textbox.configure(state="disabled")
            # makes text copyable
            #self.display.textbox.bind("<Button>", lambda event: self.display.textbox.focus_set())


        # Textbox to edit mode, fill with single node
        elif self.display.mode == "Edit":
            self.display.textbox.configure(state="normal")
            self.display.textbox.delete("1.0", "end")
            # TODO depending on show template mode
            self.display.textbox.insert("1.0", self.state.selected_node["text"])#self.state.text(self.state.selected_node))#self.state.selected_node["text"])
            self.display.textbox.see(tk.END)

            # self.display.secondary_textbox.delete("1.0", "end")
            # self.display.secondary_textbox.insert("1.0", self.state.selected_node.get("active_text", ""))
            self.display.textbox.focus()
        
        # makes text copyable
        #self.display.textbox.bind("<Button>", lambda event: self.display.textbox.focus_set())


    @metadata(name="Toggle textbox editable", keys=["<Alt-Shift-KeyPress-E>"])
    def toggle_editable(self):
        self.write_textbox_changes()
        if self.state.preferences.get('editable', False):
            self.state.update_user_frame(update={'preferences': {'editable': False}})
        else:
            self.state.update_user_frame(update={'preferences': {'editable': True}})
        self.refresh_textbox()

    @metadata(name="Write textbox")
    def write_textbox_changes(self):
        #print('writing')
        if self.state.preferences['editable'] and self.display.mode == 'Read' and self.state.selected_node:
            new_text = self.display.textbox.get("1.0", "end-1c")
            ancestry = self.state.ancestry(self.state.selected_node)
            changed_ancestry = distribute_textbox_changes(new_text, ancestry)
            for ancestor in changed_ancestry:
                self.state.tree_node_dict[ancestor['id']]['text'] = ancestor['text']
            self.update_nav_tree(edit=[ancestor['id'] for ancestor in changed_ancestry])

    def select_endpoints_range(self, start_endpoint, end_endpoint):
        start_text_index, end_text_index = self.endpoints_to_range(start_endpoint, end_endpoint)
        self.display.textbox.select_range(start_text_index, end_text_index)

    def open_selection_in_transformer(self, template=None):
        self.display.textbox.fix_selection()
        inputs = self.display.textbox.selected_inputs()
        self.open_in_transformer(inputs, template)

    def replace_selected_text(self, text):
        self.display.textbox.configure(state="normal")
        selected_text = self.display.textbox.get_selected_text()
        start_pos = self.display.textbox.index("sel.first")
        start_index = len(self.display.textbox.get("1.0", start_pos))
        end_index = start_index + len(selected_text)
        self.try_replace_range(start_index, end_index, text)

    def try_replace_range(self, start_index, end_index, text):
        start_endpoint, end_endpoint = self.range_to_endpoints(start_index, end_index)
        if self.path_uninterrupted(start_endpoint, end_endpoint):
            self.replace_trajectory(start_endpoint, end_endpoint, text)
        else:
            # TODO open warning dialog to ask user to confirm
            pass

    def try_replace_ranges(self, ranges, texts):
        # check if any of the ranges are interrupted
        start_endpoints = []
        end_endpoints = []
        for i in range(len(ranges)):
            start_endpoint, end_endpoint = self.range_to_endpoints(ranges[i][0], ranges[i][1])
            start_endpoints.append(start_endpoint)
            end_endpoints.append(end_endpoint)
            if not self.path_uninterrupted(start_endpoint, end_endpoint):
                if self.state.preferences['history_conflict'] == 'overwrite':
                    pass
                elif self.state.preferences['history_conflict'] == 'branch':
                    # TODO not implemented
                    return
                elif self.state.preferences['history_conflict'] == 'ask':
                    # TODO open warning dialog to ask user to confirm
                    return
        for i in range(len(ranges)):
            self.replace_trajectory(start_endpoints[i], end_endpoints[i], texts[i], refresh_nav=True)


    def replace_trajectory(self, start_endpoint, end_endpoint, text, refresh_nav=True):
        # replace text along a trajectory. This will put all the new text in the end endpoint, and result
        # in empty nodes if the chain is greater than two nodes long
        start_node = self.state.node(start_endpoint[0])
        end_node = self.state.node(end_endpoint[0])
        node_path = ancestry_in_range(start_node, end_node, self.state.tree_node_dict)
        if start_node == end_node:
            # substitute the text range in the node
            new_text = start_node['text'][:start_endpoint[1]] + text + start_node['text'][end_endpoint[1]:]
            self.state.update_text(start_node, new_text, refresh_nav=refresh_nav)
        else:
            for node in node_path:
                if node == start_node:
                    new_text = node['text'][:start_endpoint[1]]
                    #print(node['text'][:start_endpoint[1]])
                    self.state.update_text(node, new_text, refresh_nav=refresh_nav)
                elif node == end_node: 
                    new_text = text + node['text'][end_endpoint[1]:]
                    self.state.update_text(node, new_text, refresh_nav=refresh_nav)
                else:
                    self.state.update_text(node, "", refresh_nav=refresh_nav)

    def path_uninterrupted(self, start_endpoint, end_endpoint):
        # returns true if any nodes between start_endpoint and end_endpoint have siblings
        start_node = self.state.node(start_endpoint[0])
        end_node = self.state.node(end_endpoint[0])
        return self.state.chain_uninterrupted(start_node, end_node)

    def endpoints_to_range(self, start, end):
        ancestor_text_indices = self.state.ancestor_text_indices(self.state.selected_node)
        # ancestor_text_indices is a list of types (start, end) for nodes in ancestry
        # endpoints are ({start_node_id: text_index}, {end_node_id: text_index})
        start_node_index = node_index(self.state.node(start[0]), self.state.tree_node_dict)
        end_node_index = node_index(self.state.node(end[0]), self.state.tree_node_dict)
        start_node_text_index = ancestor_text_indices[start_node_index][0]
        end_node_text_index = ancestor_text_indices[end_node_index][0]
        start_text_index = start_node_text_index + start[1]
        end_text_index = end_node_text_index + end[1]
        return start_text_index, end_text_index

    def range_to_endpoints(self, start, end):
        ancestry = self.state.ancestry(self.state.selected_node)
        ancestor_text_indices = self.state.ancestor_text_indices(self.state.selected_node)
        start_indices = [i[0] for i in ancestor_text_indices]
        # use bisect to find the index of the start and end node
        start_node_index = bisect.bisect_right(start_indices, start) - 1
        end_node_index = bisect.bisect_right(start_indices, end) - 1
        start_text_index = start - start_indices[start_node_index]
        end_text_index = end - start_indices[end_node_index]
        start_node = ancestry[start_node_index]
        end_node = ancestry[end_node_index]
        #print(start_node['text'][start_text_index])
        return (start_node['id'], start_text_index), (end_node['id'], end_text_index)

    def node_range(self, node):
        ancestor_text_indices = self.state.ancestor_text_indices(node)
        idx = node_index(node, self.state.tree_node_dict)
        return ancestor_text_indices[idx]

    def index_to_ancestor(self, index):
        ancestor_end_indices = [ind[1] for ind in self.state.ancestor_text_indices(self.state.selected_node)]
        ancestor_index = bisect.bisect_left(ancestor_end_indices, index)
        return ancestor_index, node_ancestry(self.state.selected_node, self.state.tree_node_dict)[ancestor_index]

    # TODO nodes with mixed prompt/continuation
    def tag_prompts(self):
        if self.state.preferences['bold_prompt']:
            self.display.textbox.tag_config('prompt', font=('Georgia', self.state.preferences['font_size'], 'bold'))
        else:
            self.display.textbox.tag_config('prompt', font=('Georgia', self.state.preferences['font_size']))
        self.display.textbox.tag_remove("prompt", "1.0", 'end')
        #ancestry_text = self.state.ancestry_text(self.state.selected_node)
        indices = self.state.ancestor_text_indices(self.state.selected_node)
        #start_index = 0
        for i, ancestor in enumerate(self.state.ancestry(self.state.selected_node)):
            if 'meta' in ancestor and 'source' in ancestor['meta']:
                if not (ancestor['meta']['source'] == 'AI' or ancestor['meta']['source'] == 'mixed'):
                    self.display.textbox.tag_add("prompt", f"1.0 + {indices[i][0]} chars",
                                                 f"1.0 + {indices[i][1]} chars")
                elif ancestor['meta']['source'] == 'mixed':
                    if 'diffs' in ancestor['meta']:
                        # TODO multiple diffs in sequence
                        original_tokens = ancestor['meta']['diffs'][0]['diff']['old']

                        current_tokens = ancestor['meta']['diffs'][-1]['diff']['new']
                        total_diff = diff(original_tokens, current_tokens)
                        for addition in total_diff['added']:
                            self.display.textbox.tag_add("prompt", f"1.0 + {indices[i][0] + addition['indices'][0]} chars",
                                                         f"1.0 + {indices[i][0] + addition['indices'][1]} chars")
            #start_index = indices[i][1]

    #################################
    #   Search
    #################################

    @metadata(name="Search", keys=["<Control-Shift-KeyPress-F>"], display_key="ctrl-shift-f")
    def search(self):
        dialog = SearchDialog(parent=self.display.frame, state=self.state, goto=self.nav_select)
        self.refresh_textbox()

    @metadata(name="Search ancestry", keys=["<Control-f>"], display_key="ctrl-f")
    def search_ancestry(self):
        self.toggle_search()

    @metadata(name="Search textbox", matches=None, match_index=None, search_term=None, case_sensitive=None)
    def search_textbox(self, pattern, case_sensitive=False):
        if self.search_textbox.meta['matches'] is not None:
            if self.search_textbox.meta['search_term'] == pattern \
                    and self.search_textbox.meta['case_sensitive'] == case_sensitive:
                self.next_match()
                return
            else:
                self.clear_search()
        self.search_textbox.meta['search_term'] = pattern
        self.search_textbox.meta['case_sensitive'] = case_sensitive
        ancestry_text = self.state.ancestry_text(self.state.selected_node)
        matches = []
        matches_iter = re.finditer(pattern, ancestry_text) if case_sensitive \
            else re.finditer(pattern, ancestry_text, re.IGNORECASE)
        for match in matches_iter:
            matches.append({'span': match.span(),
                            'match': match.group()})
        self.search_textbox.meta['matches'] = matches
        if not matches:
            self.display.update_search_results(num_matches=0)
            self.clear_search()
            return
        for match in matches:
            self.display.textbox.tag_add("match",
                                         f"1.0 + {match['span'][0]} chars",
                                         f"1.0 + {match['span'][1]} chars")
        self.next_match()

    @metadata(name="Clear search")
    def clear_search(self):
        self.search_textbox.meta['search_term'] = None
        self.search_textbox.meta['matches'] = None
        self.search_textbox.meta['match_index'] = None
        self.search_textbox.meta['case_sensitive'] = None
        self.display.textbox.tag_delete("match")
        self.display.textbox.tag_delete("active_match")

    @metadata(name="Next match")
    def next_match(self):
        if self.search_textbox.meta['matches'] is None:
            return
        if self.search_textbox.meta['match_index'] is None:
            self.search_textbox.meta['match_index'] = 0
        else:
            self.search_textbox.meta['match_index'] += 1
        if self.search_textbox.meta['match_index'] >= len(self.search_textbox.meta['matches']):
            self.search_textbox.meta['match_index'] = 0
        active_match = self.search_textbox.meta['matches'][self.search_textbox.meta['match_index']]
        
        self.display.update_search_results(num_matches=len(self.search_textbox.meta['matches']), 
                                           active_index=self.search_textbox.meta['match_index'])
        self.display.textbox.tag_delete("active_match")
        self.display.textbox.tag_add("active_match",
                                     f"1.0 + {active_match['span'][0]} chars",
                                     f"1.0 + {active_match['span'][1]} chars")
        # scroll to active match
        self.display.textbox.see(f"1.0 + {active_match['span'][0]} chars")

    def in_search(self):
        return self.search_textbox.meta['matches'] is not None

    def toggle_search(self, toggle=None):
        print('controller: toggle_search')
        toggle = not self.state.workspace['show_search'] if not toggle else toggle
        self.state.update_user_frame(update={'workspace': {'show_search': toggle}})
        #self.state.user_workspace['show_search'] = toggle
        if toggle:
            self.display.open_search()
        else:
            self.display.exit_search()




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
            if 'generation' in selected_node:
                self.change_token.meta["counterfactual_index"] = 0
                self.change_token.meta["prev_token"] = None
                model_response, prompt, completion = self.state.get_request_info(selected_node)
                token_offsets = [token_data['position']['start'] for token_data in completion['tokens']]
                token_index = bisect.bisect_left(token_offsets, offset) - 1
                token_data = completion['tokens'][token_index]
                counterfactuals = token_data['counterfactuals']
                start = token_data['position']['start']
                end = token_data['position']['end']
                if self.state.preferences['prob']:
                    counterfactuals = {k: logprobs_to_probs(v) for k, v in
                                       sorted(counterfactuals.items(), key=lambda item: item[1], reverse=True)}

                self.print_to_debug(counterfactuals)
                self.display.textbox.tag_add("selected",
                                             f"1.0 + {self.ancestor_end_indices[ancestor_index - 1] + start} chars",
                                             f"1.0 + {self.ancestor_end_indices[ancestor_index - 1] + end} chars")

                self.select_token.meta["selected_node"] = selected_node
                self.select_token.meta["token_index"] = token_index

    @metadata(name="Change token", keys=[], display_key="", counterfactual_index=0, prev_token=None, temp_token_offsets=None)
    def change_token(self, node=None, token_index=None, traverse=1):
        if not self.select_token.meta["selected_node"]:
            return
        elif not node:
            node = self.select_token.meta["selected_node"]
            token_index = self.select_token.meta["token_index"]

        model_response, prompt, completion = self.state.get_request_info(node)
        token_data = completion['tokens'][token_index]

        if not self.change_token.meta['temp_token_offsets']:
            token_offsets = [token_data['position']['start'] for token_data in completion['tokens']]
            self.change_token.meta['temp_token_offsets'] = token_offsets
        else:
            token_offsets = self.change_token.meta['temp_token_offsets']

        start_position = token_offsets[token_index]
        token = token_data['generatedToken']['token']
        counterfactuals = token_data['counterfactuals'].copy()
        original_token = (token, counterfactuals.pop(token, None))
        index = node_index(node, self.state.tree_node_dict)
        sorted_counterfactuals = list(sorted(counterfactuals.items(), key=lambda item: item[1], reverse=True))
        sorted_counterfactuals.insert(0, original_token)

        self.change_token.meta["counterfactual_index"] += traverse
        if self.change_token.meta["counterfactual_index"] < 0 \
                or self.change_token.meta["counterfactual_index"] > len(sorted_counterfactuals) - 1:
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


        # update temp token offsets
        diff = len(new_token) - len(self.change_token.meta['prev_token'])
        for index, offset in enumerate(self.change_token.meta['temp_token_offsets'][token_index + 1:]):
            self.change_token.meta['temp_token_offsets'][index + token_index + 1] += diff
        self.change_token.meta['prev_token'] = new_token

    @metadata(name="Next token", keys=["<Command-period>"], display_key="", counterfactual_index=0, prev_token=None)
    def next_token(self, node=None, token_index=None):
        self.change_token(node, token_index, traverse=1)

    @metadata(name="Prev token", keys=["<Command-comma>"], display_key="", counterfactual_index=0, prev_token=None)
    def prev_token(self, node=None, token_index=None):
        self.change_token(node, token_index, traverse=-1)

    @metadata(name="Apply counterfactual", keys=["<Command-Return>"], display_key="", counterfactual_index=0, prev_token=None)
    def apply_counterfactual_changes(self):
        # TODO apply to non selected nodes
        index = node_index(self.state.selected_node, self.state.tree_node_dict)

        new_text = self.display.textbox.get(f"1.0 + {self.ancestor_end_indices[index - 1]} chars", "end-1c")
        self.state.update_text(node=self.state.selected_node, text=new_text, modified_flag=False)
        self.display.textbox.tag_remove("modified", "1.0", 'end-1c')

        # TODO what to do about this now that request information is not saved in individual node?
        # TODO calculate diffs?
        # TODO or save temp offsets only in a single session?
        if 'generation' in self.state.selected_node:
            pass
            #self.state.selected_node['meta']['generation']["logprobs"]["text_offset"] = self.change_token.meta['temp_token_offsets']
        self.refresh_counterfactual_meta()


    @metadata(name="Refresh counterfactual")
    def refresh_counterfactual_meta(self, **kwargs):
        self.change_token.meta['prev_token'] = None
        self.change_token.meta['temp_token_offsets'] = None

    #################################
    #   State
    #################################

    def immutable_popup(self, node):
        if self.state.is_compound(node):
            if self.state.is_root(node):
                self.ask_unhoist()
            else:
                self.ask_unzip(node)
        else:
            messagebox.showerror(title="Immutable", message=f"Operation disallowed on immutable node")

    def ask_unzip(self, node=None):
        node = node if node else self.state.selected_node
        result = messagebox.askquestion("Edit compound node", "Operation disallowed on zipped node. Would you like to unzip this compound node?", icon='warning')
        if result == 'yes':
            self.state.unzip(mask=node)

    def ask_unhoist(self):
        result = messagebox.askquestion("Unhoist",
                                        "Unhoist tree (unzip root)?",
                                        icon='warning')
        if result == 'yes':
            self.state.unhoist()

    # TODO fix metadata references?
    @metadata(name="Edit", keys=[], display_key="e")
    def edit_button_pressed(self):
        self.toggle_edit_mode(override_focus=True)

    # Enters edit mode or exits either edit mode
    @metadata(name="Edit Toggle", keys=["<Key-e>", "<Control-e>"], display_key="e")
    def toggle_edit_mode(self, to_edit_mode=None, override_focus=False):
        if not self.state.is_mutable(self.state.selected_node):
            self.immutable_popup(self.state.selected_node)
        else:
            if self.display.mode != "Visualize":
                if self.has_focus(self.display.textbox) or override_focus:
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
                # else:
                #     self.display.all_edit_off()

            else:
                if self.display.vis.textbox is None:
                    self.display.vis.textbox_events[self.state.selected_node['id']]()
                else:
                    self.display.vis.delete_textbox()

    @metadata(name="Edit in module")
    def edit_in_module(self, node, create_attribute=None):
        self.state.update_user_frame(update={'module_settings': {'edit': {'node_id': node['id']}}})
        # TODO if already open, refresh selection
        if create_attribute:
            if 'text_attributes' not in node:
                node['text_attributes'] = {}
            if create_attribute not in node['text_attributes']:
                node['text_attributes'][create_attribute] = ''
        if self.display.module_open("edit"):
            self.display.modules['edit'].rebuild_textboxes()
        else:
            self.open_module("side_pane", "edit")

    @metadata(name="Open in transformer")
    def open_in_transformer(self, inputs, template=None):
        if not self.display.module_open('transformers'):
            self.open_module('side_pane', 'transformers')
        if template:
            self.display.modules['transformers'].open_template_file(template)
        self.display.modules['transformers'].open_inputs(inputs)


    @metadata(name="Visualize", keys=["<Key-j>", "<Control-j>"], display_key="j")
    def toggle_visualization_mode(self):
        if self.state.preferences['autosave']:
            self.save_edits()
        self.display.set_mode("Visualize" if self.display.mode != "Visualize" else "Read")
        self.refresh_display()
        
        self.refresh_visualization()
        self.refresh_textbox()
        self.display.textbox.update_idletasks()
        self.center_view()


    # @metadata(name="Wavefunction", keys=[])
    # def toggle_multiverse_mode(self):
    #     if self.state.preferences['autosave']:
    #         self.save_edits()
    #     self.display.set_mode("Multiverse" if self.display.mode != "Multiverse" else "Read")
    #     self.refresh_visualization()
    #     self.refresh_textbox()
    #     self.refresh_display()



    #################################
    #   Edit
    #################################

    @metadata(name="Copy")
    def copy_text(self):
        pyperclip.copy(self.display.textbox.get("1.0", "end-1c"))
        confirmation_dialog = messagebox.showinfo(title="Copy text", message="Copied node text to clipboard")


    @metadata(name="Copy id", keys=["<Control-Shift-KeyPress-C>"])
    def copy_id(self, node=None):
        node = node if node else self.state.selected_node
        pyperclip.copy(node['id'])
        confirmation_dialog = messagebox.showinfo(title="Copy id", message="Copied node id to clipboard")


    @metadata(name="Prepend newline", keys=["n", "<Control-n>"], display_key="n")
    def prepend_newline(self, node=None):
        node = node if node else self.state.selected_node
        if not self.state.is_mutable(node):
            self.immutable_popup(node)
        else:
            self.save_edits()
            if self.state.selected_node:
                text = node["text"]
                if text.startswith("\n"):
                    text = text[1:]
                else:
                    if text.startswith(' '):
                        text = text[1:]
                    text = "\n" + text

                self.state.update_text(node, text)


    @metadata(name="Prepend space", keys=["<Control-space>"], display_key="ctrl-space")
    def prepend_space(self, node=None):
        node = node if node else self.state.selected_node
        if not self.state.is_mutable(node):
            self.immutable_popup(node)
        else:
            self.save_edits()
            if self.state.selected_node:
                text = node["text"]
                if text.startswith(" "):
                    text = text[1:]
                else:
                    text = " " + text
                self.state.update_text(node, text)


    @metadata(name="Add multimedia")
    def add_multimedia(self, filenames, node=None):
        node = node if node else self.state.selected_node
        if 'multimedia' not in self.state.selected_node:
            self.state.selected_node['multimedia'] = []
        added_file = False
        for filename in filenames:
            # check if filename is already in multimedia
            old_filenames = [x['file'] for x in self.state.selected_node['multimedia']]
            if filename not in old_filenames:
                self.state.selected_node['multimedia'].append({'file': filename, 'caption': ''})
                added_file = True
        if added_file:
            self.state.tree_updated()

    #################################
    #   Collapsing
    #################################


    @metadata(name="Collapse subtree", keys=["<Control-minus>"], display_key="Ctrl-minus")
    def collapse_subtree(self, node=None):
        node = node if node else self.state.selected_node
        self.collapse_node(node)
        for child in filtered_children(node, self.in_nav):
            self.collapse_subtree(child)

    @metadata(name="Expand subtree", keys=["<Control-plus>"], display_key="Ctrl-plus")
    def expand_subtree(self, node=None):
        node = node if node else self.state.selected_node
        self.expand_node(node)
        for child in filtered_children(node, self.in_nav):
            self.expand_subtree(child)

    @metadata(name="Expand children", keys=["<Control-slash>"], display_key="Ctrl-/")
    def expand_node(self, node=None):
        node = node if node else self.state.selected_node
        node['open'] = True
        self.display.nav_tree.item(
            node["id"],
            open=True
        )

    @metadata(name="Collapse node", keys=["<Control-question>"], display_key="Ctrl-?")
    def collapse_node(self, node=None):
        node = node if node else self.state.selected_node
        node['open'] = False
        self.display.nav_tree.item(
            node["id"],
            open=False
        )

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
        elif 'meta' in node and 'source' in node['meta'] and node['meta']['source'] == 'prompt':
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


    @metadata(name="New")
    def new_tree(self):
        self.state.open_empty_tree()

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

    @metadata(name="New tree from node", keys=[], display_key="")
    def new_from_node(self):
        self.state.open_node_as_root()

    @metadata(name="Hoist", keys=["<Command-h>", "<Alt-h>"], display_key="")
    def hoist(self, node=None):
        node = node if node else self.state.selected_node
        self.state.hoist(node=node)

    @metadata(name="Unhoist", keys=["<Command-Shift-KeyPress-H>", "<Control-Shift-KeyPress-H>"], display_key="")
    def unhoist(self):
        self.state.unhoist()

    @metadata(name="Unhoist all", keys=[], display_key="")
    def unhoist_all(self):
        self.state.unhoist_all()

    @metadata(name="Save", keys=["<s>", "<Control-s>"], display_key="s")
    def save_tree(self, popup=True, autosave=False, filename=None, subtree=None):
        if autosave and not self.state.preferences['autosave']:
            return
        #try:
        # if not autosave and not self.state.preferences['save_counterfactuals']:
        #     self.state.delete_counterfactuals()
        self.save_edits()
        if self.state.preferences['model_response'] == 'backup' and not autosave:
            self.state.backup_and_delete_model_response_data()
        elif self.state.preferences['model_response'] == 'discard':
            self.state.tree_raw_data['model_responses'] = {}

        self.state.save_tree(backup=popup, save_filename=filename, subtree=subtree)
        if popup:
            messagebox.showinfo(title=None, message="Saved!")
        #except Exception as e:
            #messagebox.showerror(title="Error", message=f"Failed to Save!\n{str(e)}")

    @metadata(name="Save as sibling", keys=["<Command-e>", "<Alt-e>"], display_key="Command-e")
    def save_as_sibling(self):
        # TODO fails on root node
        if self.display.mode == "Edit":
            new_text = self.display.textbox.get("1.0", 'end-1c')
            #new_active_text = self.display.secondary_textbox.get("1.0", 'end-1c')
            self.escape()
            sibling = self.create_sibling(self.state.selected_node, toggle_edit=False)
            #self.nav_select(node_id=sibling['id'])
            self.state.update_text(sibling, new_text)

    @metadata(name="Duplicate")
    def duplicate(self, node=None):
        node = node if node else self.state.selected_node
        sibling = self.create_sibling(self.state.selected_node, toggle_edit=False)
        self.state.update_text(sibling, node['text'])

    # Exports subtree as a loom json
    @metadata(name="Export subtree", keys=["<Control-Command-KeyPress-X>", "<Control-Alt-KeyPress-X>"], display_key="Ctrl-Command-X")
    def export_subtree(self, node=None):
        node = node if node else self.state.selected_node
        export_options = {
            'subtree_only': True,
            'visible_only': True,
            'root_frame': True,
            'frame': False,
            'tags': False,
            'chapter_id': False,
            'text_attributes': False,
            'multimedia': False,
        }
        dialog = ExportOptionsDialog(parent=self.display.frame, options_dict=export_options)
        if not dialog.result:
            return 
        filename = self.state.tree_filename if self.state.tree_filename \
            else os.path.join(os.getcwd() + '/data', "new_tree.json")
        # TODO default name shouldn't be parent tree name
        filename = filedialog.asksaveasfilename(
            initialfile=os.path.splitext(os.path.basename(filename))[0],
            initialdir=os.path.dirname(filename),
            defaultextension='.json')
        if filename:
            #self.state.tree_filename = filename
            node = node if export_options['subtree_only'] else self.state.root()
            filter = self.in_nav if export_options['visible_only'] else None
            copy_attributes = [attribute for attribute in ['frame', 'tags', 'chapter_id', 'text_attributes', 'multimedia'] if export_options[attribute]]
            # TODO don't necessarily copy mutable for zipped things
            copy_attributes += ['mutable', 'text'] #'parent_id'
            self.state.export_subtree(node, filename, filter, copy_attributes)
            # new_tree = node.copy()
            # new_tree.pop('parent_id')
            # new_tree = {'root': new_tree}
            # new_tree = self.state.copy_global_objects(new_tree)
            # print(new_tree)
            # self.save_tree(subtree=new_tree, filename=filename)
            # return


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

    @metadata(name="Export simple subtree")
    def export_simple_subtree(self, node=None):
        node = node if node else self.state.selected_node
        title = os.path.splitext(os.path.basename(self.state.tree_filename))[0] if self.state.tree_filename else 'untitled'
        filename = os.path.join(os.getcwd() + '/data/exports',
                                f"{title}_export.json")
        filename = filedialog.asksaveasfilename(
            initialfile=os.path.splitext(os.path.basename(filename))[0],
            initialdir=os.path.dirname(filename),
            defaultextension='.json')
        if filename:
            self.state.save_simple_tree(filename, subtree=node)



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


    #################################
    #   Dialogs
    #################################

    @metadata(name="Preferences", keys=["<Control-p>"], display_key="")
    def preferences(self):
        #print(self.state.preferences)
        dialog = PreferencesDialog(parent=self.display.frame, orig_params=self.state.preferences,
                          user_params=self.state.user_preferences, state=self.state)
        self.state.tree_updated()
        self.state.selection_updated()


    @metadata(name="Generation Settings", keys=["<Control-Shift-KeyPress-P>"], display_key="ctrl-p")
    def generation_settings_dialog(self):
        dialog = GenerationSettingsDialog(parent=self.display.frame, orig_params=self.state.generation_settings, 
                                          user_params=self.state.user_generation_settings, state=self.state)
        self.state.tree_updated()
        self.state.selection_updated()

    @metadata(name="Inline Generation Settings")
    def inline_generation_settings_dialog(self):
        dialog = GenerationSettingsDialog(parent=self.display.frame, orig_params=self.state.inline_generation_settings, 
                                          user_params=self.state.user_inline_generation_settings, state=self.state)

    def chat_dialog(self):
        dialog = ChatDialog(parent=self.display.frame, state=self.state)

    def model_config_dialog(self):
        dialog = ModelConfigDialog(parent=self.display.frame, state=self.state)

    @metadata(name="Visualization Settings", keys=["<Control-u>"], display_key="ctrl-u")
    def visualization_settings_dialog(self):
        dialog = VisualizationSettingsDialog(self.display.frame, self.state.visualization_settings)
        if dialog.result:
            #print("Settings saved")
            #pprint(self.state.visualization_settings)
            self.refresh_visualization()
            # self.save_tree(popup=False)

    def workspace_dialog(self):
        dialog = WorkspaceDialog(self.display.frame, self.state.workspace)
        if dialog.result:
            self.refresh_workspace()

    @metadata(name="Show Info", keys=["<Control-i>"], display_key="i")
    def info_dialog(self):
        all_text = "".join([d["text"] for d in self.state.tree_node_dict.values()])

        data = {
            "Total characters": f'{len(all_text):,}',
            "Total words": f'{len(all_text.split()):,}',
            "Total pages": f'{len(all_text) / 3000:,.1f}',
            "": "",
            "Total nodes": f'{len(self.state.tree_node_dict):,}',
            "Max depth": height(self.state.tree_raw_data["root"]),
            "Max branching factor": max([len(d["children"]) for d in self.state.tree_node_dict.values()])

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

    @metadata(name="Multimedia dialog", keys=["<u>"], display_key="u")
    def multimedia_dialog(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = MultimediaDialog(parent=self.display.frame, callbacks=self.callbacks, state=self.state)

    # @metadata(name="Memory dialogue", keys=["<Control-Shift-KeyPress-M>"], display_key="Control-shift-m")
    # def ai_memory(self, node=None):
    #     if node is None:
    #         node = self.state.selected_node
    #     dialog = AIMemory(parent=self.display.frame, node=node, state=self.state)
    #     self.refresh_textbox()

    # @metadata(name="Node memory", keys=["<Command-m>", "<Alt-m>"], display_key="Command-m")
    # def node_memory(self, node=None):
    #     if node is None:
    #         node = self.state.selected_node
    #     dialog = NodeMemory(parent=self.display.frame, node=node, state=self.state)
    #     self.refresh_textbox()

    @metadata(name="Add memory", keys=["<m>", "<Control-m>"], display_key="m")
    def add_memory(self, node=None):
        if node is None:
            node = self.state.selected_node
        dialog = CreateMemory(parent=self.display.frame, node=node, state=self.state, default_inheritability='delayed')
        self.refresh_textbox()


    #################################
    #   Modules
    #################################

    def open_module(self, pane_name, module_name):
        #print('controller: open_module')
        #self.state.workspace[pane_name]['open'] = True
        if not self.state.workspace[pane_name]['open']:
            #self.state.update_user_frame({'workspace': {pane_name: {'open': True}}})
            self.open_pane(pane_name)
        if module_name not in self.state.workspace[pane_name]['modules']:
            #self.state.user_workspace[pane_name]['modules'].append(module_name)
            # TODO this only appends to frame, doesn't append during accumulation
            self.state.update_user_frame({'workspace': {pane_name: {'modules': [module_name]}}}, append=True)
            #print(self.state.workspace)
        self.refresh_workspace()

    def toggle_module(self, pane_name, module_name):
        if self.state.workspace[pane_name]['open'] and module_name in self.state.workspace[pane_name]['modules']:
            self.close_pane(pane_name)
        else:
            self.open_module(pane_name, module_name)
        self.refresh_workspace()

    def open_pane(self, pane_name):
        #print('controller: open_pane')
        self.state.update_user_frame({'workspace': {pane_name: {'open': True}}})
        #print('1', self.state.workspace)
        self.refresh_workspace()

    def close_pane(self, pane_name):
        #print('controller: close_pane')
        self.state.update_user_frame({'workspace': {pane_name: {'open': False}}})
        self.refresh_workspace()

    @metadata(name="Side pane", keys=["<Command-p>", "<Alt-p>"], display_key="")
    def toggle_side(self, toggle='either'):
        if toggle == 'on' or (toggle == 'either' and not self.state.workspace['side_pane']['open']):
            self.open_pane("side_pane")
        else:
            self.close_pane('side_pane')

    @metadata(name="Bottom pane", keys=["<Command-b>", "<Alt-b>"], display_key="")
    def toggle_bottom(self, toggle='either'):
        if toggle == 'on' or (toggle == 'either' and not self.state.workspace['bottom_pane']['open']):
            self.open_pane("bottom_pane")
        else:
            self.close_pane('bottom_pane')

    # this only builds the workspace according to state - doesn't set workspace state
    def refresh_workspace(self):
        for pane in self.display.panes:
            if self.state.workspace[pane]["open"]:
                if not self.display.pane_open(pane):
                    self.display.open_pane(pane)
                #print(self.state.workspace[pane]["modules"])
                self.display.update_modules(pane, self.state.workspace[pane]["modules"])
            else:
                self.display.close_pane(pane)
        self.display.configure_buttons(visible_buttons=self.state.workspace['buttons'])


    @metadata(name="Submit", keys=[], display_key="")
    def submit(self, text, auto_response):
        if text:
            #new_text = self.state.submit_modifications(text)
            new_child = self.create_child(toggle_edit=False)
            new_child['text'] = text
            self.state.tree_updated(add=[new_child['id']])    
        if auto_response:
            self.generate(update_selection=True, placeholder="")

    @metadata(name="Toggle input box", keys=["<Tab>"], display_key="")
    def toggle_input_box(self):
        self.toggle_module("bottom_pane", "input")
    
    @metadata(name="Toggle debug", display_key="")
    def toggle_debug_box(self):
        self.toggle_module("bottom_pane", "debug")

    @metadata(name="Children")#, keys=["<Command-c>", "<Alt-c>"], display_key="")
    def toggle_show_children(self, toggle='either'):
        self.toggle_module("bottom_pane", "children")

    @metadata(name="Show hidden children")
    def show_hidden_children(self, node=None):
        node = node if node else self.state.selected_node
        self.state.tree_updated(add=[n['id'] for n in node['children'] if not self.in_nav(n)])

    @metadata(name="Hide invisible children")
    def hide_invisible_children(self, node=None):
        node = node if node else self.state.selected_node
        self.state.tree_updated(delete=[n['id'] for n in node['children'] if not self.state.visible(n)])

    @metadata(name="Wavefunction")#, keys=["<Command-c>", "<Alt-c>"], display_key="")
    def toggle_multiverse(self, toggle='either'):
        self.toggle_module("side_pane", "wavefunction")

    @metadata(name="Map")#, keys=["<Command-c>", "<Alt-c>"], display_key="")
    def toggle_minimap(self, toggle='either'):
        self.toggle_module("side_pane", "minimap")

    def print_to_debug(self, message):
        if message:
            self.open_module("bottom_pane", "debug")
            # TODO print to debug stream even if debug box is not active
            self.display.modules['debug'].write(message)

    @metadata(name="Run", keys=["<Control-Shift-KeyPress-B>"], display_key="", prev_cmd="")
    def run(self):
        dialog = RunDialog(parent=self.display.frame, callbacks=self.callbacks, init_text=self.callbacks["Run"]["prev_cmd"])

    def open_alt_textbox(self):
        if not self.display.alt_textbox:
            self.display.build_alt_textbox()

    def close_alt_textbox(self):
        if self.display.alt_textbox:
            self.display.destroy_alt_textbox()

    def configure_tags(self):
        dialog = TagsDialog(parent=self.display.frame, state=self.state)
        print('configure tags(1)')
        if dialog.result:
            print('configure tags')
            self.state.tree_updated(rebuild=True)

    def add_tag(self):
        dialog = AddTagDialog(parent=self.display.frame, state=self.state)

    @metadata(name="Tag node dialog")
    def tag_node(self, node=None):
        node = node if node else self.state.selected_node
        modifications = {'add': [], 'remove': []}
        dialog = TagNodeDialog(parent=self.display.frame, node=node, state=self.state, modifications=modifications)
        # TODO will this be slow for large trees?
        if modifications['add'] or modifications['remove']:
            self.state.tree_updated(rebuild=True)
        # for added_tag in modifications['add']:
        #     self.state.tag_scope_update(node, added_tag)


    @metadata(name="Insert summary")
    def insert_summary(self, index):
        ancestor_index, selected_ancestor = self.index_to_ancestor(index)
        negative_offset = self.ancestor_end_indices[ancestor_index] - index
        offset = len(selected_ancestor['text']) - negative_offset
        dialog = CreateSummary(parent=self.display.frame, root_node=selected_ancestor, state=self.state, position=offset)

    def view_summaries(self):
        dialog = Summaries(parent=self.display.frame, node=self.state.selected_node, state=self.state)

    @metadata(name="Goto node id", keys=["<Control-Shift-KeyPress-G>"], display_key="")
    def goto_node_dialog(self):
        dialog = GotoNode(parent=self.display.frame, goto=lambda node_id: self.select_node(self.state.node(node_id)))

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

    #################################
    #   Autocomplete
    #################################

    # @metadata(name="Autocomplete", keys=["<Alt_L>"], display_key="", in_autocomplete=False, autocomplete_range=None,
    #           input_range=None, possible_tokens=None, matched_tokens=None, token_index=None, filter_chars='', leading_space=False)
    # def autocomplete(self):
    #
    #     # TODO determine whether in edit mode, input box, or vis textbox
    #
    #     if self.has_focus(self.display.input_box):
    #         self.display.input_box.tag_config('autocomplete', background="blue")
    #         if not self.autocomplete.meta["in_autocomplete"]:
    #             self.autocomplete.meta["possible_tokens"] = self.state.autocomplete_generate(self.display.input_box.get("1.0", tk.INSERT), engine='curie')
    #             self.autocomplete.meta["matched_tokens"] = self.autocomplete.meta["possible_tokens"]
    #             self.autocomplete.meta["token_index"] = 0
    #             self.autocomplete.meta["in_autocomplete"] = True
    #             self.insert_autocomplete()
    #         else:
    #             self.scroll_autocomplete(1)


    # # autocomplete_range is full range of suggested token regardless of user input
    # def insert_autocomplete(self, offset=0):
    #     # todo remove leading space
    #
    #     insert = self.display.input_box.index(tk.INSERT)
    #     #print(f'text box contents: [{self.display.input_box.get("1.0", "end-1c")}]')
    #
    #     start_position = self.autocomplete.meta["autocomplete_range"][0] if self.autocomplete.meta["autocomplete_range"] else insert
    #     # TODO if run out of suggested tokens
    #     suggested_token = self.autocomplete.meta["matched_tokens"][self.autocomplete.meta["token_index"]][0]
    #     # if self.autocomplete.meta['leading_space'] and offset == 0 and not disable_effects and suggested_token[0] == ' ':
    #     #     print('drop leading space')
    #     #     suggested_token = suggested_token[1:]
    #     #     self.autocomplete.meta['leading_space'] = False
    #     self.autocomplete.meta["autocomplete_range"] = (start_position, f'{start_position} + {str(len(suggested_token))} chars') #(start_position, f'{insert} + {str(len(suggested_token) - offset)} chars') #
    #
    #     #self.display.input_box.insert(start_position, suggested_token[:offset])
    #     #self.display.input_box.insert(f'{start_position} + {offset} chars', suggested_token[offset:], "autocomplete")
    #     self.display.input_box.insert(insert, suggested_token[offset:], "autocomplete")
    #     if suggested_token[0] == ' ' and offset == 1:
    #         self.display.input_box.delete(start_position, f'{start_position} + 1 char')
    #         self.display.input_box.insert(start_position, ' ')
    #         self.display.input_box.mark_set(tk.INSERT, f'{start_position} + 1 char')
    #         self.autocomplete.meta["filter_chars"] = ' ' + self.autocomplete.meta["filter_chars"]
    #     else:
    #         self.display.input_box.mark_set(tk.INSERT, insert)

    # TODO <Right> doesn't work
    # TODO examples
    # @metadata(name="Apply Autocomplete", keys=["<Alt_R>", "<Right>"], display_key="")
    # def apply_autocomplete(self, auto=True):
    #     if self.has_focus(self.display.input_box) and self.autocomplete.meta["in_autocomplete"]:
    #         self.delete_autocomplete()
    #         self.insert_autocomplete()
    #         self.display.input_box.tag_delete("autocomplete")
    #         self.display.input_box.mark_set(tk.INSERT, f'{self.autocomplete.meta["autocomplete_range"][1]} + 1 chars')
    #         self.exit_autocomplete()
    #         if auto:
    #             self.autocomplete()

    # @metadata(name="Rewind Autocomplete", keys=["<Control_L>"], display_key="")
    # def rewind_autocomplete(self):
    #     if self.has_focus(self.display.input_box) and self.autocomplete.meta["in_autocomplete"]:
    #         self.scroll_autocomplete(-1)

    # def scroll_autocomplete(self, step=1):
    #     new_index = self.autocomplete.meta["token_index"] + step
    #     if 0 <= new_index < 100:
    #         self.autocomplete.meta["token_index"] = new_index
    #         self.display.input_box.delete(*self.autocomplete.meta[
    #             "autocomplete_range"])
    #         self.insert_autocomplete()


    @metadata(name="Key Pressed", keys=[], display_key="")
    def key_pressed(self, char):
        if char and self.autocomplete.meta["in_autocomplete"]:
            if char.isalnum() or char in ['\'', '-', '_', ' ']:
                self.filter_autocomplete_suggestions(char)
            elif char == 'Tab':
                # FIXME this doesn't work - why?
                print('tab')
                self.apply_autocomplete()
            else:
                self.delete_autocomplete()
                self.exit_autocomplete()

    # def delete_autocomplete(self, offset=0):
    #     #print(self.autocomplete.meta['autocomplete_range'])
    #     #print('text box contents: ', self.display.input_box.get("1.0", 'end-1c'))

    #     # delete_range = self.autocomplete.meta['autocomplete_range']
    #     delete_range = (f'{self.autocomplete.meta["autocomplete_range"][0]} + {offset} chars',
    #                                     f'{self.autocomplete.meta["autocomplete_range"][1]}')
    #     #print(self.display.input_box.get(*delete_range))
    #     self.display.input_box.delete(*delete_range)
    #     #print('text box contents: ', self.display.input_box.get("1.0", 'end-1c'))

    # def filter_autocomplete_suggestions(self, char):
    #     # TODO deleting tokens
    #     # TODO infer instead of record offset?
    #     # TODO space usually accepts
    #     if char == ' ':
    #         self.autocomplete.meta['leading_space'] = True
    #         self.apply_autocomplete()
    #         return
    #     self.delete_autocomplete(offset=len(self.autocomplete.meta["filter_chars"]))

    #     self.autocomplete.meta["filter_chars"] += char
    #     print(self.autocomplete.meta["filter_chars"])

    #     match_beginning = re.compile(rf'^\s*{self.autocomplete.meta["filter_chars"]}.*', re.IGNORECASE)
    #     self.autocomplete.meta["matched_tokens"] = [token for token in self.autocomplete.meta['possible_tokens']
    #                                                 if match_beginning.match(token[0])]
    #     print(self.autocomplete.meta["matched_tokens"])
    #     if len(self.autocomplete.meta["matched_tokens"]) < 1:
    #         # TODO if empty list, substitute nothing, but don't exit autocomplete
    #         self.exit_autocomplete()
    #     else:
    #         self.autocomplete.meta["token_index"] = 0
    #         self.insert_autocomplete(offset=len(self.autocomplete.meta["filter_chars"]))

    # def exit_autocomplete(self):
    #     self.autocomplete.meta["autocomplete_range"] = None
    #     self.autocomplete.meta["in_autocomplete"] = False
    #     self.autocomplete.meta["token_index"] = None
    #     self.autocomplete.meta["possible_tokens"] = None
    #     self.autocomplete.meta["matched_tokens"] = None
    #     self.autocomplete.meta["filter_chars"] = ''


    def has_focus(self, widget):
        return self.display.textbox.focus_displayof() == widget

    # def multi_text_has_focus(self):
    #     if self.display.multi_textboxes:
    #         for id, textbox in self.display.multi_textboxes.items():
    #             if self.display.textbox.focus_displayof() == textbox['textbox']:
    #                 return True
    #     return False

    def module_textbox_has_focus(self):
        for pane in self.display.panes:
            if self.state.workspace[pane]['open']:
                for module in self.state.workspace[pane]['modules']:
                    if self.display.modules[module].textbox_has_focus():
                        return True
        return False

    #################################
    #   Story frame TODO call set text, do this in display?
    #################################

    @metadata(name="Save Edits")
    def save_edits(self, **kwargs):
        #print('save edits')
        #print(kwargs)
        if not self.state.selected_node_id:
            return

        if self.display.mode == "Edit":
            new_text = self.display.textbox.get("1.0", 'end-1c')
            #new_active_text = self.display.secondary_textbox.get("1.0", 'end-1c')
            self.state.update_text(self.state.selected_node, new_text, save_revision_history=self.state.preferences['revision_history'])

        elif self.display.mode == "Visualize":
            if self.display.vis.textbox:
                new_text = self.display.vis.textbox.get("1.0", 'end-1c')
                self.state.update_text(self.state.node(self.display.vis.editing_node_id), new_text, save_revision_history=self.state.preferences['revision_history'])

        elif kwargs.get("write", True):
            self.write_textbox_changes()

    def modules_tree_updated(self, **kwargs):
        for pane in self.display.panes:
            if self.state.workspace[pane]['open']:
                for module in self.state.workspace[pane]['modules']:
                    self.display.modules[module].tree_updated()

    def modules_selection_updated(self, **kwargs):
        for pane in self.display.panes:
            if self.state.workspace[pane]['open']:
                for module in self.state.workspace[pane]['modules']:
                    if self.display.module_open(module):
                        self.display.modules[module].selection_updated()

    def refresh_display(self, **kwargs):
        self.configure_buttons()
        self.configure_nav_tags()
        self.refresh_workspace()


    def refresh_alt_textbox(self, **kwargs):
        # open alt textbox if node has "alt" attribute
        if self.display.mode == 'Read':
            alt_text = self.state.get_text_attribute(self.state.selected_node, 'alt_text')
            if alt_text:
                self.open_alt_textbox()
                # insert alt text into textbox
                self.display.alt_textbox.configure(state='normal')
                self.display.alt_textbox.delete('1.0', 'end')
                self.display.alt_textbox.insert('1.0', alt_text)
                self.display.alt_textbox.configure(state='disabled')
            else:
                self.close_alt_textbox()


    def refresh_visualization(self, center=False, **kwargs):
        if self.display.mode != "Visualize":
            return
        # self.display.vis.redraw(self.state.root(), self.state.selected_node)
        self.display.vis.draw(self.state.tree_raw_data["root"], self.state.selected_node, center_on_selection=False)
        if center:
            # self.display.vis.center_view_on_canvas_coords(*self.display.vis.node_coords[self.state.selected_node_id])
            self.display.vis.center_view_on_node(self.state.selected_node)


    def refresh_vis_selection(self, **kwargs):
        if self.display.mode != "Visualize":
            return
        # self.display.vis.redraw(self.state.root(), self.state.selected_node)
        self.display.vis.refresh_selection(self.state.tree_raw_data["root"], self.state.selected_node)
        # TODO Without redrawing, the new open state won't be reflected
        # self.display.vis.draw(self.state.tree_raw_data["root"], self.state.selected_node)
        # self.display.vis.center_view_on_canvas_coords(*self.display.vis.node_coords[self.state.selected_node_id])

    @metadata(name="Reset zoom", keys=["<Control-0>"], display_key="Ctrl-0")
    def reset_zoom(self):
        if self.display.mode == 'Visualize':
            self.display.vis.reset_zoom()
        # elif self.display.mode == 'Multiverse':
        #     self.display.multiverse.reset_view()

    # @metadata(name="Clear multiverse", keys=["<Command-0>", "<Alt-0>"], display_key="Command-0")
    # def reset_multiverse(self):
    #     if self.display.mode == 'Multiverse':
    #         self.display.multiverse.clear_multiverse()



    #################################
    #   Navtree
    #################################

    def nav_name(self, node):
        if self.state.is_root(node) and not self.state.is_compound(node):
            text = self.state.name()
        else:
            nav_preview = self.state.get_text_attribute(node, 'nav_preview')
            if nav_preview:
                text = nav_preview.replace('\n', '\\n')
            else:
                node_text = node['text']
                text = node_text.strip()[:25].replace('\n', '\\n')
                text = text if text else "EMPTY"
                text = text + "..." if len(node_text) > 25 else text
            #text = '~' + text if self.state.has_tag(node, "archived") else text
        if 'chapter_id' in node:
            text = f"{text} | {self.state.chapter_title(node)}"
        return node.get("name", text)

    @metadata(name="Nav icon")
    def nav_icon(self, node):
        image = None
        if node == self.state.root():
            image = self.icons.get_icon('tree-lightblue')
        elif node['id'] == self.state.checkpoint:
            image = self.icons.get_icon('marker-black')
        elif self.state.is_compound(node):
            image = self.icons.get_icon('layers-black')
        elif 'multimedia' in node and len(node['multimedia']) > 0:
            image = self.icons.get_icon('media-white')
        for tag in self.state.tags:
            if self.state.has_tag_attribute(node, tag):
                if self.state.tags[tag]['icon'] != 'None':
                    image = self.icons.get_icon(self.state.tags[tag]['icon'])
        if not image:
            image = self.icons.get_icon('empty')
        return image

    def configure_nav_tags(self):
        self.display.nav_tree.tag_configure("not visited", background=not_visited_color())
        self.display.nav_tree.tag_configure("visited", background=visited_color())
        self.display.nav_tree.tag_configure("immutable", foreground=immutable_color())

    def insert_nav(self, node, image, tags):
        # get index of node in sibling list 
        # if node is root, then index = 0
        insert_idx = self.state.siblings_index(node, filter=self.state.visible)
        parent_id = node.get("parent_id", "")
        # TODO instead of visible, check if parent is in nav tree
        if parent_id:
            if not self.in_nav(self.state.node(parent_id)):
                if not self.state.visible(self.state.node(parent_id)):
                    #parent_id = self.state.root()['id']
                    return
                else:
                    #print('parent not in nav but visible')
                    return
        self.display.nav_tree.insert(
            parent=parent_id,
            index=insert_idx,#0 if self.state.preferences.get('reverse', False) else "end",
            iid=node["id"],
            text=self.nav_name(node),
            #open=True,
            open=node.get("open", False),
            tags=tags,
            **dict(image=image) if image else {}
        )

    def build_nav_tree(self, flat_tree=None):
        if not flat_tree:
            flat_tree = self.state.nodes_dict(filter=self.state.visible)#self.state.generate_filtered_tree()
        self.display.nav_tree.delete(*self.display.nav_tree.get_children())
        for id in flat_tree:
            node = self.state.node(id)
            image = self.nav_icon(node)
            tags = self.state.get_node_tags(node)
            self.insert_nav(node, image, tags)
        self.configure_nav_tags()

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

        #override_visible = kwargs.get('override_visible', True)

        if 'edit' not in kwargs and 'add' not in kwargs and 'delete' not in kwargs:
            return
        else:
            #visible = lambda _node: all(condition(_node) for condition in self.state.generate_visible_conditions())
            #visible = self.state.id_visible
            delete_items = [i for i in kwargs['delete']] if 'delete' in kwargs else []
            edit_items = [i for i in kwargs['edit'] if (i in self.state.tree_node_dict
                          and self.in_nav(node=self.state.node(i)))] if 'edit' in kwargs else []
            add_items = [i for i in kwargs['add'] if i in self.state.tree_node_dict] if 'add' in kwargs else []

        self.display.nav_tree.delete(*delete_items)

        for id in add_items + edit_items:
            node = self.state.node(id)
            image = self.nav_icon(node)
            tags = self.state.get_node_tags(node)
            if id in add_items:
                #print('adding id', id)
                if self.display.nav_tree.exists(id):
                    self.display.nav_tree.delete(id)
                self.insert_nav(node, image, tags)
            elif id in edit_items:
                self.display.nav_tree.item(id,
                                           text=self.nav_name(node),
                                           open=node.get("open", False),
                                           tags=tags,
                                           **dict(image=image) if image else {})


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

        if not self.display.nav_tree.exists(self.state.selected_node_id):
            print('error: node is not in treeview')
            return

        # Select on the nav tree and highlight
        state_selected_id = self.state.selected_node["id"]
        navbar_selected_id = self.display.nav_tree.selection()[0] if self.display.nav_tree.selection() else None

        if navbar_selected_id != state_selected_id:
            try:
                self.display.nav_tree.selection_set(state_selected_id)  # Will cause a recursive call
            except tk.TclError:
                print('selection set error')

        # Update the open state of all nodes based on the navbar
        # TODO
        for node in self.state.nodes:
            if self.display.nav_tree.exists(node["id"]):
                node["open"] = self.display.nav_tree.item(node["id"], "open")

        # Update tag of node based on visited status
        self.refresh_nav_node(self.state.selected_node)

        # Scroll to node, open it's parent nodes
        self.scroll_to_selected()

    @metadata(name="Refresh nav node")
    def refresh_nav_node(self, node):
        if self.in_nav(node):
            tags = self.state.get_node_tags(node)
            image = self.nav_icon(node)
            self.display.nav_tree.item(
                node["id"],
                text=self.nav_name(node),
                open=node.get("open", False),
                tags=tags,
                **dict(image=image) if image else {})


    # add node and ancestry to open tree
    # TODO masked nodes
    def reveal_node(self, node):
        if self.display.nav_tree.exists(node['id']):
            return
        self.state.reveal_ancestry(node)


    def ask_reveal(self, node):
        result = messagebox.askquestion("Navigate to hidden node",
                                        "Attempting to navigate to a hidden node. Reveal node in nav tree?",
                                        icon='warning')
        if result == 'yes':
            self.reveal_node(node)
            return True
        return False

    @metadata(name="Center", keys=[], display_key="")
    def scroll_to_selected(self):
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

    @metadata(name="Node open")
    def node_open(self, node):
        try:
            open = self.display.nav_tree.item(node['id'], "open")
            return open
        except tk.TclError:
            return False

    def set_nav_scrollbars(self):

        open_nav_nodes = self.state.nodes_list(filter=lambda node: self.in_nav(node) and self.node_open(node))

        open_nav_ids = {d["id"] for d in open_nav_nodes}
        # Ordered by tree order
        open_nav_ids = [iid for iid in self.state.tree_node_dict.keys() if iid in open_nav_ids]

        # Magic numbers
        WIDTH_PER_INDENT = 20  # Derived...
        start_width = 200
        # offset_from_selected = -15
        offset_from_selected = -25

        open_height = max([
            depth(self.state.tree_node_dict.get(iid, {}), self.state.tree_node_dict)
            for iid in open_nav_ids] + [0])

        total_width = start_width + open_height * WIDTH_PER_INDENT

        self.display.nav_tree.column("#0", width=total_width, minwidth=total_width)

        current_width = depth(self.state.selected_node, self.state.tree_node_dict) \
                        * WIDTH_PER_INDENT + offset_from_selected
        self.display.nav_tree.xview_moveto(clip_num(current_width / total_width, 0, 1))


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
        visible_chapters = [n for c in chapter_trees for n in collect_visible_chapters(c)]
        visible_ids = {d["id"] for d in visible_chapters}
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

    def configure_buttons(self):
        if self.state.selected_node:
            if not self.state.is_mutable(self.state.selected_node):
                self.display.buttons["Edit"].configure(state='disabled')
            else:
                self.display.buttons["Edit"].configure(state='normal')
            if self.state.is_root(self.state.selected_node):
                self.display.hoist_button.configure(state='disabled')
            else:
                self.display.hoist_button.configure(state='normal')
        if self.state.is_compound(self.state.root()):
            self.display.unhoist_button.configure(state='normal')
        else:
            self.display.unhoist_button.configure(state='disabled')

        if self.nav_history:
            self.display.back_button.configure(state='normal')
        else:
            self.display.back_button.configure(state='disabled')
        if self.undo_history:
            self.display.forward_button.configure(state='normal')
        else:
            self.display.forward_button.configure(state='disabled')

    def fix_selection(self, **kwargs):
        if not self.state.selected_node:
            self.state.selected_node_id = self.state.root()["id"]
        elif not self.display.nav_tree.exists(self.state.selected_node_id):
            self.state.selected_node_id = self.state.find_next(node=self.state.selected_node,
                                                               filter=self.in_nav)

    #################################
    #   Programmatic weaving
    #################################

    @metadata(name="Eval")
    def eval_code(self, code_string):
        if code_string:
            result = eval(code_string)
            print(result)
            #self.print_to_debug(result)
            # try:
            #     result = eval(code_string)
            #     self.print_to_debug(message=result)
            #     print(result)
            # except Exception as e:
            #     self.print_to_debug(message=e)
            #     print(e)



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

