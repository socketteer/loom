import tkinter as tk
from tkinter import ttk

import PIL

from view.tree_vis import TreeVis
from view.block_multiverse import BlockMultiverse
from util.custom_tks import TextAware, ScrollableFrame
from view.colors import bg_color, text_color, edit_color, GREEN, BLUE
from util.util import metadata
from util.util_tree import num_descendents
from view.panes import Pane, NestedPane
from view.modules import *
from view.icons import Icons
from view.styles import textbox_config
from tkinter.font import Font
# from PIL import ImageTk, Image
import uuid
import time
import os
from pprint import pformat


class Display:

    def __init__(self, root, callbacks, state, controller):
        self.root = root
        # Dict of callback names to callback data {**metadata, callback=func}
        self.callbacks = callbacks
        self.state = state
        self.controller = controller

        self.modes = {"Read", "Edit", "Multi Edit", "Visualize", "Multiverse"}
        self.mode = "Read"

        self.frame = ttk.Frame(self.root)
        self.frame.pack(expand=True, fill="both")

        # Variables initialized below
        self.pane = None

        self.nav_frame = None
        self.nav_pane = None
        self.nav_tree = None
        self.nav_scrollbarx = None

        self.chapter_nav_frame = None
        self.chapter_nav_tree = None
        self.chapter_nav_scrollbarx = None

        self.main_pane = None

        self.alt_frame = None
        self.alt_textbox = None

        self.story_frame = None
        self.textbox_frame = None
        self.textbox = None
        self.secondary_textbox_frame = None
        self.secondary_textbox = None
        self.preview_textbox_frame = None
        self.preview_textbox = None
        self.vis_frame = None
        self.vis = None

        self.multiverse_frame = None
        self.multiverse = None

        self.panes = {'side_pane': None, 'bottom_pane': None}

        self.button_frame = None

        self.search_box = None
        self.search_frame = None
        self.search_label = None
        self.case_sensitive_checkbox = None
        self.case_sensitive = None
        self.search_results = None
        self.search_close_button = None

        self.button_bar = None
        self.edit_button = None

        self.hoist_button = None
        self.unhoist_button = None
        self.scroll_to_selected_button = None

        self.font = Font(family='Georgia', size=12)

        self.modules = {'notes': Notes,
                        'texteditor': TextEditor,
                        'prompt': Prompt,
                        'run': Run,
                        'minimap': MiniMap,
                        'children': Children}

        # Build it!
        self.build_display(self.frame)
        self.set_mode(self.mode)
        self.icons = Icons()

    #################################
    #   Util
    #################################

    def button_name(self, name):
        display_key = self.callbacks[name].get("display_key", "")
        display_key = f" [{display_key}]" if display_key else ""
        return name + display_key

    def change_cursor(self, cursor_type):
        self.root.config(cursor=cursor_type)

        # TODO make a decorator which automatically caches default=CACHE args. None should be a cacheable value

    # Caches param arguments so repeated calls will use the same args unless overridden
    @metadata(first_call=True, args={})
    def build_button(self, frame, name, button_params=None, pack_params=None, pack=True, side="left"):
        if not self.build_button.meta["first_call"]:
            if button_params is None:
                button_params = self.build_button.meta["args"]["button_params"]
            if pack_params is None:
                pack_params = self.build_button.meta["args"]["pack_params"]
        self.build_button.meta["args"]["button_params"] = button_params
        self.build_button.meta["args"]["pack_params"] = pack_params

        display_name = self.button_name(name)
        # FIXME formatting, stupid construct. Use NameSpace?
        button_params = {**dict(
            text=display_name,
            command=self.callbacks[name]["callback"],
            width=max(6, len(display_name))
        ), **(button_params if button_params else {})}
        button = ttk.Button(frame, **button_params)

        if pack:
            button.pack(**{**dict(side=side, fill="y"), **(pack_params if pack_params else {})})
        return button

    def build_display(self, frame):
        self.pane = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        self.pane.pack(expand=True, fill="both")

        self.build_nav(self.pane)
        self.pane.add(self.nav_frame, weight=1)

        self.build_main_frame(self.pane)
        self.pane.add(self.main_frame, weight=6)

    #################################
    #   Main frame
    #################################

    def build_main_frame(self, frame):
        self.main_frame = ttk.Frame(frame)
        self.main_pane = ttk.PanedWindow(self.main_frame, orient=tk.VERTICAL)
        self.main_pane.pack(expand=True, fill="both")
        self.story_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.story_frame, weight=6)

        self.build_textboxes(self.story_frame)
        self.textbox_frame.pack(expand=True, fill="both")

        self.vis = TreeVis(self.story_frame,
                           self.state, self.controller)

        self.multiverse = BlockMultiverse(self.story_frame)

        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(side="bottom", fill="both")
        self.build_main_buttons(self.button_frame)
        self.button_bar.pack(side="top", fill="both")

        self.search_frame = ttk.Frame(self.main_pane, relief=tk.RAISED, borderwidth=2)

    def build_textboxes(self, frame):
        self._build_textbox(frame, "preview_textbox_frame", "preview_textbox", height=3)
        self._build_textbox(frame, "textbox_frame", "textbox", height=1)
        self._build_textbox(frame, "secondary_textbox_frame", "secondary_textbox", height=3)


    def key_pressed(self, event=None):
        if event.keysym == 'Tab':
            self.callbacks["Key Pressed"]["callback"](char=event.keysym)
            return 'break'
        self.callbacks["Key Pressed"]["callback"](char=event.char)

    # Text area and scroll bar  TODO Make a scrollable textbox tkutil
    def _build_textbox(self, frame, frame_attr, textbox_attr, height=1):
        textbox_frame = ttk.Frame(frame)
        self.__setattr__(frame_attr, textbox_frame)

        scrollbar = ttk.Scrollbar(textbox_frame, command=lambda *args: self.__getattribute__(textbox_attr).yview(*args))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        textbox = TextAware(textbox_frame, bd=3, height=height, yscrollcommand=scrollbar.set, undo=True)
        self.__setattr__(textbox_attr + "_scrollbar", scrollbar)
        self.__setattr__(textbox_attr, textbox)
        # TODO move this out
        textbox.bind("<Control-Button-1>", lambda event: self.edit_history(txt=textbox))
        textbox.bind("<Control-Shift-Button-1>", lambda event: self.goto_history(txt=textbox))
        textbox.bind("<Control-Alt-Button-1>", lambda event: self.split_node(txt=textbox))
        textbox.bind("<Alt-Button-1>", lambda event: self.select_token(txt=textbox))
        textbox.bind("<Button-3>", lambda event: self.add_summary(txt=textbox))
        textbox.pack(expand=True, fill='both')

         # Other nice options: Helvetica, Arial, Georgia
        textbox.configure(**textbox_config())


    def edit_history(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Edit history"]["callback"](index=char_index)

    def goto_history(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Goto history"]["callback"](index=char_index)

    def split_node(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Split node"]["callback"](index=char_index)

    def select_token(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Select token"]["callback"](index=char_index)

    def add_summary(self, txt, event=None):
        # print('clicked')
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Insert summary"]["callback"](index=char_index)

    def build_main_buttons(self, frame):
        self.button_bar = ttk.Frame(frame, width=500, height=20)

        # First a large edit button
        self.edit_button = self.build_button(frame, "Edit", dict(width=12))
        self.build_button(frame, "Children")
        self.build_button(frame, "Visualize")
        self.build_button(frame, "Wavefunction")

        # Button name, button params, pack params
        buttons = [
            # Tree modification on the left
            # ["Delete"],
            # ["Newline"],
            # ["Space"],
            # ["Copy"],
            ["New Child", {}],
            ["Generate"],
            # Navigation on the right
            ["Next", {}, dict(side="right")],
            ["Prev", {}, dict(side="right")],
            # ["Parent"],
            #["Bookmark"],
        ]

        for btn in buttons:
            self.build_button(frame, *btn)

    #################################
    #   Alt Textbox
    #################################

    def build_alt_textbox(self):
        if not self.alt_frame:
            self.alt_frame = ttk.Frame(self.main_pane, height=500, width=400, relief='sunken', borderwidth=2)
        self.main_pane.insert(self.story_frame, self.alt_frame, weight=1)
        #self.pane.add(self.alt_frame, weight=1)
        #self.story_frame.pack_forget()
        #self.alt_frame.pack(expand=False, fill='x')
       # self.story_frame.pack(expand=True, fill='both')

        self.alt_textbox = TextAware(self.alt_frame, height=3)
        self.alt_textbox.pack(expand=True, fill='both')
        self.alt_textbox.configure(**textbox_config())
        self.alt_textbox.configure(state='disabled')


    def destroy_alt_textbox(self):
        if self.alt_frame is not None:
            self.main_pane.forget(self.alt_frame)
            self.alt_frame.destroy()
        if self.alt_textbox:
            self.alt_textbox.pack_forget()
        self.alt_textbox = None
        #self.alt_frame.pack_forget()
        #self.textbox_frame.pack(expand=True, side="top", fill='both')

    #################################
    #   Nav Panel
    #################################

    def build_nav(self, frame):
        self.nav_frame = ttk.Frame(frame, height=500, width=300, relief='sunken', borderwidth=2)
        # Nav controls
        self.hoist_button = self.build_button(self.nav_frame, "Hoist", dict(width=15), dict(fill="x"), side="top")
        self.unhoist_button = self.build_button(self.nav_frame, "Unhoist", dict(width=15), dict(fill="x"), side="top")
        self.scroll_to_selected_button = self.build_button(self.nav_frame, "Scroll to selected", dict(width=15), dict(fill="x"), side="top")
        # buttons = [
        #     # ["Clear chapters", dict(width=30), dict(fill="x", side="top")],
        #     ["Hoist", dict(width=15), dict(fill="x")],
        #     ["Unhoist", dict(width=15), dict(fill="x")],
        #     ["Scroll to selected", dict(width=15), dict(fill="x")],  # , dict(side="bottom", fill="x")],
        # ]
        # for btn in buttons:
        #     self.build_button(self.nav_frame, *btn, side="top")

        self.nav_pane = ttk.PanedWindow(self.nav_frame, height=500, width=300)
        self.nav_pane.pack(expand=True, fill='both')

        # Tree nav
        self._build_treeview(self.nav_frame, "nav_tree", "nav_scrollbarx", "nav_scrollbary")
        self.nav_pane.add(self.nav_tree, weight=3)

        self.build_chapter_nav()

        # Make display nav (but not chapter) selection update real selection (e.g. arrow keys
        f = self.callbacks["Nav Select"]["callback"]
        self.nav_tree.bind("<<TreeviewSelect>>", lambda event: f(node_id=(self.nav_tree.selection()[0])))

        # Make nav and chapter clicks update real selection
        self.nav_tree.bind(
            "<Button-1>", lambda event: f(node_id=self.nav_tree.identify('item', event.x, event.y))
        )
        self.chapter_nav_tree.bind(
            "<Button-1>", lambda event: f(node_id=self.chapter_nav_tree.identify('item', event.x, event.y))
        )

        # File controls
        buttons = [
            # ["Clear chapters", dict(width=30), dict(fill="x", side="top")],
            ["Save", dict(width=15), dict(fill="x")],  # , dict(side="bottom", fill="x")],
            ["Open", dict(width=15), dict(fill="x")],  # , dict(side="bottom", fill="x")],
        ]
        for btn in buttons:
            self.build_button(self.nav_frame, *btn)

    def build_chapter_nav(self):
        self._build_treeview(self.nav_frame, "chapter_nav_tree")
        self.nav_pane.add(self.chapter_nav_tree, weight=1)

    # # TODO make a scrollable obj so I don't have to keep doing this
    def _build_treeview(self, frame, tree_attr, scrollbarx_attr=None, scrollbary_attr=None):
        style = ttk.Style(frame)
        style.configure('Treeview', rowheight=25)  # Spacing between rows
        tree = ttk.Treeview(frame, selectmode="browse", padding=(0, 0, 0, 1))
        self.__setattr__(tree_attr, tree)

        # Scrollbars
        scrollbary = ttk.Scrollbar(tree, orient="vertical", command=tree.yview)
        scrollbary.pack(side="left", fill="y")
        tree.configure(yscrollcommand=scrollbary.set)
        if scrollbary_attr is not None:
            self.__setattr__(scrollbary_attr, scrollbary)

        scrollbarx = ttk.Scrollbar(tree, orient="horizontal", command=tree.xview)
        scrollbarx.pack(side='bottom', fill='x')
        tree.configure(xscrollcommand=scrollbarx.set)
        if scrollbarx_attr is not None:
            self.__setattr__(scrollbarx_attr, scrollbarx)

    # TODO chapter_nav_frame is currently not used
    def destroy_chapter_nav(self):
        print('destroy chapter nav')
        if self.chapter_nav_frame is not None:
            print('destroying')
            self.chapter_nav_frame.pack_forget()
            self.chapter_nav_frame.destroy()
            self.chapter_nav_tree = None
            self.chapter_nav_scrollbarx = None

    # def refresh_nav_node(self, node):
    #     tags = self.state.get_node_tags(node)
    #     self.nav_tree.item(
    #         node["id"],
    #         open=node.get("open", False),
    #         tags=tags
    #     )

    #################################
    #   Panes
    #################################

    def destroy_pane(self, pane_name):
        if self.panes[pane_name]:
            self.panes[pane_name].destroy()
        self.panes[pane_name] = None
        self.state.workspace[pane_name]['open'] = False

    def open_pane(self, pane_name, orient):
        self.state.workspace[pane_name]['open'] = True
        if orient == 'horizontal':
            parent = self.pane
        else:
            parent = self.main_pane
        self.panes[pane_name] = NestedPane(pane_name, parent, orient='vertical')
        self.panes[pane_name].build_pane()
        self.panes[pane_name].build_menu_frame(options=self.modules.keys(), selection_callback=self.module_selected, destroy_callback=self.destroy_pane)
        self.panes[pane_name].module_selection.set(self.state.workspace[pane_name]['module'])

    def open_module(self, pane, module):
        pane.clear()
        pane.module = module
        module.build()

    def module_selected(self, pane_name):
        pane = self.panes[pane_name]
        module_name = pane.module_selection.get()
        #print(f'{module_name} selected')
        self.state.workspace[pane_name]['module'] = module_name
        module = self.modules[module_name](parent=pane, callbacks=self.callbacks, state=self.state)
        self.open_module(pane, module)

    #################################
    #   Bottom frame
    #################################

    # def destroy_debug_box(self):
    #     if self.debug_box is not None:
    #         self.debug_box.pack_forget()
    #         self.debug_box.destroy()
    #     self.debug_box = None
    #
    # def build_debug_box(self):
    #     self.rebuild_bottom_frame()
    #     self.debug_box = TextAware(self.bottom_frame, bd=3, height=3)
    #     self.debug_box.pack(expand=True, fill='both')
    #     self.debug_box.configure(
    #         foreground='white',
    #         background='black',
    #         wrap="word",
    #     )
    #     self.debug_box.configure(state="disabled")
    #
    # def write_to_debug(self, message):
    #     if self.debug_box:
    #         self.debug_box.configure(state="normal")
    #         self.debug_box.insert("end-1c", '\n')
    #         self.debug_box.insert("end-1c", pformat(message))
    #         self.debug_box.configure(state="disabled")
    #
    # def destroy_input_box(self):
    #     if self.input_frame is not None:
    #         self.input_frame.pack_forget()
    #         self.input_frame.destroy()
    #     self.input_box = None
    #     self.submit_button = None
    #
    # def build_input_box(self):
    #     self.rebuild_bottom_frame()
    #     self.input_frame = ttk.Frame(self.bottom_frame)
    #     self.input_box = TextAware(self.input_frame, bd=3, height=2, undo=True)
    #     self.input_box.pack(expand=True, fill='both')
    #     self.input_box.configure(**textbox_config())
    #     self.input_box.bind("<Key>", lambda event: self.key_pressed(event))

        # self.mode_var = tk.StringVar()
        # choices = ('default', 'chat', 'dialogue', 'antisummary')
        # self.mode_select = tk.OptionMenu(self.input_frame, self.mode_var, *choices)
        # self.mode_var.trace('w', self.callbacks["Update mode"]["callback"])

        # tk.Label(self.input_frame, text="Mode", bg=bg_color(), fg=text_color()).pack(side='left')
        # self.mode_select.pack(side='left')

        # self.submit_button = ttk.Button(self.input_frame, text="Submit",
        #                                 command=self.callbacks["Submit"]["callback"], width=10)
        # self.submit_button.pack(side='right')
        # self.input_frame.pack(side="bottom", expand=True, fill="both")

    #################################
    #   Edit mode
    #################################

    # TODO does this need to return true if focus is in multi edit sometimes?
    @property
    def in_edit_mode(self):
        return self.mode in {"Edit", "Multi Edit"}

    def set_mode(self, new_state):
        assert new_state in self.modes
        self.mode = new_state
        self.edit_button.config(text="Finish Editing" if self.in_edit_mode else self.button_name("Edit"))

        self.clear_story_frame()

        if self.mode == "Read":
            self.textbox_frame.pack(expand=True, side="top", fill='both')
            self.textbox.config(foreground=text_color(), background=bg_color())
            self.textbox.edit_reset()

        elif self.mode == "Edit":
            self.textbox_frame.pack(expand=True, side="top", fill='both')
            self.textbox.config(foreground=text_color(), background=edit_color())
            #self.secondary_textbox_frame.pack(expand=False, side="bottom", fill='both')
            self.secondary_textbox.config(foreground=text_color(), background=edit_color())
            self.preview_textbox.config(foreground=text_color(), background=edit_color())

        elif self.mode == "Visualize":
            self.vis.frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        elif self.mode == "Multiverse":
            self.multiverse.frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        else:
            raise NotImplementedError(self.mode, type(self.mode))

    def clear_story_frame(self):
        # self.destroy_multi_edit()
        self.textbox_frame.pack_forget()
        self.secondary_textbox_frame.pack_forget()
        self.vis.frame.pack_forget()
        self.multiverse.frame.pack_forget()

    def close_secondary_textbox(self):
        self.secondary_textbox_frame.pack_forget()

    def open_secondary_textbox(self):
        self.secondary_textbox_frame.pack(expand=False, side="bottom", fill='both')

    def close_preview_textbox(self):
        self.preview_textbox_frame.pack_forget()

    def open_preview_textbox(self):
        self.preview_textbox_frame.pack(expand=False, side="top", fill='both')

    #################################
    #   Search
    #################################

    def open_search(self):
        self.close_search()
        self.search_frame.pack(side='bottom', expand=False, fill='x')

        self.search_label = tk.Label(self.search_frame, text='Search:', bg=bg_color(), fg=text_color())
        self.search_label.pack(side='left', expand=True)

        self.search_box = TextAware(self.search_frame, bd=2, height=1)
        self.search_box.pack(side='left', expand=True, fill='x', padx=5)
        self.search_box.configure(
            font=self.font,
            foreground=text_color(),
            background=bg_color(),
        )
        if not self.case_sensitive:
            self.case_sensitive = tk.BooleanVar(value=0)
        self.case_sensitive_checkbox = ttk.Checkbutton(self.search_frame, text='Aa', variable=self.case_sensitive, 
                                                       )
        self.case_sensitive_checkbox.pack(side='left', expand=True, padx=5)

        #self.search_close_button = ttk.Button(self.search_frame, text='[x]', command=self.exit_search, width=2.5)
        self.search_close_button = tk.Label(self.search_frame, text='⨯', font=("Arial", 12), fg=text_color(), bg=bg_color(), cursor='hand2')
        self.search_close_button.bind('<Button-1>', self.exit_search)
        self.search_close_button.pack(side='left', expand=True, padx=2)

        self.search_box.focus()

        self.search_box.bind("<Key>", lambda event: self.search_key_pressed(event))

    def close_search(self):
        if self.search_box:
            self.search_box.pack_forget()
            self.search_box = None
        if self.search_label:
            self.search_label.pack_forget()
            self.search_label = None
        if self.search_results:
            self.search_results.pack_forget()
            self.search_results = None
        if self.case_sensitive_checkbox:
            self.case_sensitive_checkbox.pack_forget()
            self.case_sensitive_checkbox = None
        if self.search_close_button:
            self.search_close_button.pack_forget()
            self.search_close_button = None
        self.search_frame.pack_forget()

    def search_key_pressed(self, event=None):
        if event.keysym == 'Return':
            search_term = self.search_box.get("1.0", 'end-1c')
            self.callbacks["Search textbox"]["callback"](pattern=search_term, 
                                                         case_sensitive=self.case_sensitive.get())
            return 'break'
        elif event.keysym == 'Escape':
            self.exit_search()

    def exit_search(self, *args):
        self.callbacks["Clear search"]["callback"]()
        self.textbox.focus()
        self.close_search()

    def update_search_results(self, num_matches, active_index=1):
        if not self.search_results:
            self.search_results = tk.Label(self.search_frame, bg=bg_color(), fg=text_color())
            self.search_results.pack(side='left', padx=5)
        if num_matches == 0:
            self.search_results.config(text='No matches')
        else:
            self.search_results.config(text=f'{active_index}/{num_matches}')