import tkinter as tk
from tkinter import ttk

import PIL

from view.tree_vis import TreeVis
from view.block_multiverse import BlockMultiverse
from util.custom_tks import TextAware, ScrollableFrame
from view.colors import bg_color, text_color, edit_color, GREEN, BLUE
from util.util import metadata
from util.util_tree import num_descendents
from util.panes import Pane, NestedPane
from view.modules import *
from view.icons import Icons
from view.styles import textbox_config
from tkinter.font import Font
# from PIL import ImageTk, Image
import uuid
import time
import os


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

        self.panes = {'side_pane': None}

        self.bottom_frame = None
        self.button_frame = None
        self.input_box = None
        self.input_frame = None
        self.mode_select = None
        self.submit_button = None
        self.mode_var = None
        self.debug_box = None

        self.multi_scroll_frame = None
        self.multi_textboxes = None
        self.multi_pady = 8
        self.multi_padx = 2
        self.multi_default_height = 3
        self.multi_bd_width = 3
        self.default_num_textbox = 5
        self.button_height = 30
        self.add_child_button = None
        self.hidden_nodes_button = None
        self.delete_buttons = None
        self.archive_buttons = None
        self.edit_buttons = None
        self.descendents_labels = None

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
                        'run': Run,}

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

    def destroy_pane(self, pane):
        pane.destroy()
        self.panes['side_pane'] = None
        self.state.workspace[pane.name]['open'] = False

    def open_pane(self, name, orient):
        self.state.workspace[name]['open'] = True
        self.panes[name] = NestedPane(name, self.pane, orient=orient)
        self.panes[name].build_pane()
        self.panes[name].build_menu_frame(options=self.modules.keys(), selection_callback=self.module_selected, destroy_callback=self.destroy_pane)
        self.panes[name].module_selection.set(self.state.workspace[name]['module'])

    def open_module(self, pane, module):
        pane.clear()
        pane.module = module
        module.build()

    def module_selected(self, pane):
        module_name = pane.module_selection.get()
        #print(f'{module_name} selected')
        self.state.workspace[pane.name]['module'] = module_name
        module = self.modules[module_name](parent=pane, callbacks=self.callbacks, state=self.state)
        self.open_module(pane, module)


    #################################
    #   Bottom frame
    #################################

    def rebuild_bottom_frame(self):
        self.destroy_bottom_frame()
        if not self.bottom_frame:
            self.bottom_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.bottom_frame, weight=1)

    def destroy_bottom_frame(self):
        self.destroy_multi_frame()
        self.destroy_debug_box()
        self.destroy_input_box()

        if self.bottom_frame:
            self.main_pane.forget(self.bottom_frame)
            self.bottom_frame.destroy()
        self.bottom_frame = None

    def destroy_debug_box(self):
        if self.debug_box is not None:
            self.debug_box.pack_forget()
            self.debug_box.destroy()
        self.debug_box = None

    def build_debug_box(self):
        self.rebuild_bottom_frame()
        self.debug_box = TextAware(self.bottom_frame, bd=3, height=3)
        self.debug_box.pack(expand=True, fill='both')
        self.debug_box.configure(
            foreground='white',
            background='black',
            wrap="word",
        )
        self.debug_box.configure(state="disabled")

    def write_to_debug(self, message):
        if self.debug_box:
            self.debug_box.configure(state="normal")
            self.debug_box.insert("end-1c", '\n')
            self.debug_box.insert("end-1c", message)
            self.debug_box.configure(state="disabled")

    def destroy_input_box(self):
        if self.input_frame is not None:
            self.input_frame.pack_forget()
            self.input_frame.destroy()
        self.input_box = None
        self.submit_button = None

    def build_input_box(self):
        self.rebuild_bottom_frame()
        self.input_frame = ttk.Frame(self.bottom_frame)
        self.input_box = TextAware(self.input_frame, bd=3, height=2, undo=True)
        self.input_box.pack(expand=True, fill='both')
        self.input_box.configure(**textbox_config())
        self.input_box.bind("<Key>", lambda event: self.key_pressed(event))

        # self.mode_var = tk.StringVar()
        # choices = ('default', 'chat', 'dialogue', 'antisummary')
        # self.mode_select = tk.OptionMenu(self.input_frame, self.mode_var, *choices)
        # self.mode_var.trace('w', self.callbacks["Update mode"]["callback"])

        # tk.Label(self.input_frame, text="Mode", bg=bg_color(), fg=text_color()).pack(side='left')
        # self.mode_select.pack(side='left')

        self.submit_button = ttk.Button(self.input_frame, text="Submit",
                                        command=self.callbacks["Submit"]["callback"], width=10)
        self.submit_button.pack(side='right')
        self.input_frame.pack(side="bottom", expand=True, fill="both")

    #################################
    #   Show children
    #################################

    def destroy_multi_frame(self):
        self.clear_multi_frame()
        self.multi_scroll_frame = None
        self.multi_textboxes = None

    def build_multi_frame(self, children):
        #self.destroy_bottom_frame()
        self.destroy_bottom_frame()
        self.rebuild_bottom_frame()
        num_textboxes = len(children)
        self.init_multi_frame(num_textboxes)
        self.multi_textboxes = {str(uuid.uuid1()): {'textbox': TextAware(self.multi_scroll_frame.scrollable_frame,
                                                                         height=self.multi_default_height,
                                                                         bd=self.multi_bd_width,
                                                                         relief=tk.RAISED)} for i in
                                range(num_textboxes)}
        self.place_textboxes()
        self.populate_textboxes(children)

    def init_multi_frame(self, num_textboxes):
        self.multi_scroll_frame = ScrollableFrame(self.bottom_frame)#, height=self.multi_textbox_frame_height(num_textboxes))
        self.multi_scroll_frame.pack(expand=True, fill="both", side=tk.BOTTOM)
        #self.main_pane.sash_place(index=0, x=0, y=self.multi_textbox_frame_height(num_textboxes))
        #self.bottom_frame.configure(height=self.multi_textbox_frame_height(num_textboxes))

    def multi_textbox_frame_height(self, num_textboxes=None):
        num_textboxes = num_textboxes if num_textboxes is not None else len(self.multi_textboxes.items())
        font_height = tk.font.Font(font=self.font).metrics('linespace')
        textbox_height = self.multi_default_height * font_height + self.multi_pady * 2 + self.multi_bd_width * 2 + 2

        height = min(num_textboxes, self.default_num_textbox) * textbox_height
        return height

    def place_textboxes(self):
        row = 0
        tk.Grid.columnconfigure(self.multi_scroll_frame.scrollable_frame, 1, weight=1)

        for textbox_id, tb_item in self.multi_textboxes.items():
            tk.Grid.rowconfigure(self.multi_scroll_frame.scrollable_frame, row, weight=1)
            tk.Grid.rowconfigure(self.multi_scroll_frame.scrollable_frame, row + 1, weight=1)

            tb = tb_item['textbox']
            tb.grid(row=row, column=1, rowspan=2, sticky=tk.N + tk.S + tk.E + tk.W)
            tb.configure(
                font=self.font,
                foreground=text_color(),  # Darkmode
                background=bg_color(),
                padx=self.multi_padx,
                pady=self.multi_pady,
                wrap="word",
            )
            # tb.configure(state='disabled')
            row += 2

    # rebuilds multi frame from multi_textboxes dictionary
    # remakes all widgets
    # TODO different height if textbox in edit mode
    def rebuild_multi_frame(self):
        self.clear_multi_frame()
        self.multi_scroll_frame = None
        self.init_multi_frame(num_textboxes=len(self.multi_textboxes.items()))

        for tb_id, tb_item in self.multi_textboxes.items():
            state = 'disabled'
            height = self.multi_default_height
            # if tb_item['textbox']:
            #     if tb_item['textbox'].cget('state') == 'normal':
            #         height = min(6, tb_item['num_lines'] + 2)
            #         state = 'normal'
            tb_item['textbox'] = TextAware(self.multi_scroll_frame.scrollable_frame, height=height,
                                           bd=3, relief=tk.RAISED)
            tb_item['textbox'].configure(state=state)

        self.place_textboxes()
        active_children = [tb_item[1]['node'] for tb_item in self.multi_textboxes.items()]
        self.populate_textboxes(active_children)

    # add more children to multi_textboxes and rebuild
    # TODO also for delete, modified?
    # TODO add to the top of the list?
    # or add to the bottom but scroll?
    def update_children(self, new_children):
        for child in new_children:
            self.multi_textboxes[str(uuid.uuid1())] = {'node': child}
        self.rebuild_multi_frame()
        if not self.state.preferences.get('reverse', False):
            self.multi_scroll_frame.canvas.update_idletasks()
            self.multi_scroll_frame.canvas.yview_moveto(1)

    def update_text(self):
        for tb_id, tb_item in self.multi_textboxes.items():
            tb = tb_item['textbox']
            node = tb_item['node']
            tb.configure(state='normal')
            tb.delete("1.0", "end")
            tb.insert("1.0", node["text"])
            tb.configure(state='disabled')
            tb_item['num_lines'] = max(node["text"].count("\n"), int(tb.index('end').split('.')[0]))
            tb.configure(height=min(tb_item['num_lines'], self.multi_default_height))

    def forget_row(self, tb):
        if 'textbox' in tb:
            tb['textbox'].grid_forget()
        if 'close' in tb:
            tb['close'].grid_forget()
        if 'go' in tb:
            tb['go'].grid_forget()
        if 'archive' in tb:
            tb['archive'].grid_forget()
        if 'edit' in tb:
            tb['edit'].grid_forget()
        if 'delete' in tb:
            tb['delete'].grid_forget()
        if 'descendents_label' in tb:
            tb['descendents_label'].grid_forget()

    # clears tkinter widgets but doesn't clear multi_textboxes info
    def clear_multi_frame(self):
        if self.multi_textboxes:
            for tb in self.multi_textboxes.values():
                self.forget_row(tb)
            if self.add_child_button:
                self.add_child_button.grid_forget()
                self.add_child_button = None
            if self.hidden_nodes_button:
                self.hidden_nodes_button.grid_forget()
                self.hidden_hodes_button = None
        if self.multi_scroll_frame:
            self.multi_scroll_frame.pack_forget()


    # adds text of children into textboxes
    # creates icons/labels and binds functions
    def populate_textboxes(self, children):
        if not children:
            return
        children = children if not self.state.preferences.get("reverse", False) else children[::-1]
        for i, (tb_id, tb_item) in enumerate(self.multi_textboxes.items()):
            child = children[i]
            tb = tb_item['textbox']
            tb.configure(state='normal')
            tb.delete("1.0", "end")
            tb.insert("1.0", child["text"])
            tb.configure(state='disabled')
            tb_item['node'] = child
            tb_item['num_lines'] = max(child["text"].count("\n"), int(tb.index('end').split('.')[0]))
            height = self.multi_default_height#self.textbox_height(tb_id)
            tb.configure(height=height)

            tb.bind("<Button-1>", lambda event, _textbox_id=tb_id: self.textbox_clicked(_textbox_id))

            if self.state.preferences['coloring'] != 'read':
                self.make_button('arrow-green', self.goto_child, i, 2, tb_id, tb_item)
                self.make_button('x-lightgray', self.dismiss_textbox, i, 3, tb_id, tb_item)
                if self.state.is_mutable(child):
                    self.make_button('edit-blue', self.toggle_editable, i, 4, tb_id, tb_item)
                self.make_button('archive-yellow', self.archive_child, i, 5, tb_id, tb_item)
                self.make_button('trash-red', self.delete_child, i, 6, tb_id, tb_item)
                # TODO only create label if node has descendents
                descendents = num_descendents(child) - 1
                if descendents != 0:
                    var = tk.StringVar()
                    label = tk.Label(self.multi_scroll_frame.scrollable_frame, textvariable=var, relief=tk.FLAT,
                                     fg=text_color(), bg=bg_color())
                    if descendents == 1:
                        var.set(f"{1} descendent")
                    else:
                        var.set(f"{descendents} descendents")
                    label.grid(row=i * 2 + 1, column=2, columnspan=5)
                    tb_item['descendents_label'] = label

        if self.state.preferences['coloring'] != 'read':
            all_siblings = self.state.parent(children[0])['children']
            num_hidden = len(all_siblings) - len(children)
            if num_hidden > 0:
                self.hidden_nodes_button = ttk.Button(self.multi_scroll_frame.scrollable_frame,
                                                     text=f"Show {num_hidden} hidden children",
                                                     command=self.show_hidden, width=20)#, background=BLUE,
                                                     #foreground=text_color())
                self.hidden_nodes_button.grid(row=self.multi_scroll_frame.scrollable_frame.grid_size()[1], column=1)

    def make_button(self, name, function, row, column, tb_id, tb_item):
        button = tk.Label(self.multi_scroll_frame.scrollable_frame, image=self.icons.get_icon(name), bg=bg_color(), cursor='hand2')
        button.grid(row=row * 2, column=column, padx=5)
        button.bind("<Button-1>", lambda event, _textbox_id=tb_id: function(_textbox_id))
        tb_item[name] = button

    def textbox_height(self, tb_id):
        adaptive_height = False
        return min(self.multi_textboxes[tb_id]['num_lines'],
                   self.multi_default_height) if adaptive_height else self.multi_default_height

    def dismiss_textbox(self, tb_id):
        self.forget_row(self.multi_textboxes[tb_id])
        self.multi_textboxes.pop(tb_id)
        if len(self.multi_textboxes.items()) < self.default_num_textbox:
            self.rebuild_multi_frame()


    # when editing is enabled, textbox height expands to show all text
    # when editing is disabled, height defaults to self.multi_default_height
    def toggle_editable(self, textbox_id):
        if self.multi_textboxes[textbox_id]['textbox'].cget('state') == 'disabled':
            self.edit_on(textbox_id)
        else:
            self.edit_off(textbox_id)
        # self.rebuild_multi_frame()

    def edit_on(self, textbox_id):
        if self.state.is_compound(self.state.selected_node):
            print('error: node is compound')
            pass
        else:
            
            edit_height = self.multi_default_height#min(self.multi_default_height, self.multi_textboxes[textbox_id]['num_lines'] + 2)
            self.multi_textboxes[textbox_id]['textbox'].configure(state='normal', background=edit_color(),
                                                                  relief=tk.SUNKEN,
                                                                  height=edit_height)
            self.multi_textboxes[textbox_id]['textbox'].focus()
            self.multi_textboxes[textbox_id]["node"]["visited"] = True
            self.callbacks['Refresh nav node']['callback'](node=self.multi_textboxes[textbox_id]["node"])
            #self.refresh_nav_node(self.multi_textboxes[textbox_id]["node"])

    def edit_off(self, textbox_id):
        height = self.multi_default_height#self.textbox_height(textbox_id)
        self.multi_textboxes[textbox_id]['textbox'].configure(state='disabled', background=bg_color(),
                                                              relief=tk.RAISED, height=height)
        self.save_edits(textbox_id)
        self.textbox.focus()

    def all_edit_off(self):
        if self.multi_textboxes:
            for tb_id in self.multi_textboxes:
                self.edit_off(tb_id)

    # regrid textboxes without remaking widgets
    def regrid_textboxes(self):
        pass

    def textbox_clicked(self, textbox_id):
        # TODO will this recalculate at runtime?
        if self.multi_textboxes[textbox_id]['textbox'].cget('state') == 'disabled':
            self.goto_child(textbox_id)

    def tb_id_from_node(self, node):
        for tb_id, item in self.multi_textboxes.items():
            if item['node'] == node:
                return tb_id
        return None

    # when textbox is not editable, clicking on it will goto child
    # if textbox is active, need to click on icon and it will save edits
    def goto_child(self, textbox_id):
        self.callbacks["Select node"]["callback"](node=self.multi_textboxes[textbox_id]["node"])

    def add_child(self):
        new_child = self.callbacks["New Child"]["callback"](node=self.state.selected_node, update_selection=False,
                                                            toggle_edit=False)
        self.edit_on(self.tb_id_from_node(new_child))

    def show_hidden(self, *args):
        self.callbacks["Show hidden children"]["callback"]()

    def delete_child(self, textbox_id):
        ask = True if 'descendents_label' in self.multi_textboxes[textbox_id] else False
        deleted = self.callbacks["Delete"]["callback"](node=self.multi_textboxes[textbox_id]["node"], ask=ask,
                                                       ask_text="Delete subtree?")
        if deleted:
            self.dismiss_textbox(textbox_id)

    def archive_child(self, textbox_id):
        #self.callbacks["Archive"]["callback"](node=self.multi_textboxes[textbox_id]["node"])
        node = self.multi_textboxes[textbox_id]["node"]
        self.state.tag_node(node, 'archived')
        #TODO
        self.dismiss_textbox(textbox_id)
        self.state.tree_updated(delete=[node['id']])


    # called when:
    # edit mode toggled
    # navigate away from node in any way
    def save_edits(self, textbox_id):
        node = self.multi_textboxes[textbox_id]['node']
        if node['id'] in self.state.tree_node_dict:
            new_text = self.multi_textboxes[textbox_id]['textbox'].get("1.0", 'end-1c')
            self.state.update_text(node=node, text=new_text, refresh_nav=True)
            #self.callbacks['Refresh nav node']['callback'](node=node)

    def save_all(self):
        if self.multi_textboxes:
            for tb_id, tb_item in self.multi_textboxes.items():
                if self.multi_textboxes[tb_id]['textbox'].cget('state') == 'normal':
                    self.save_edits(tb_id)

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
        self.search_close_button =tk.Label(self.search_frame, text='⨯', font=("Arial", 12), fg=text_color(), bg=bg_color(), cursor='hand2')
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