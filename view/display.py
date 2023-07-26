import tkinter as tk
from tkinter import ttk
from util.gpt_util import event_probs

import PIL
from view import colors

from view.tree_vis import TreeVis
#from components.block_multiverse import BlockMultiverse
#from util.custom_tks import TextAware, ScrollableFrame
from view.colors import bg_color, text_color, edit_color, GREEN, BLUE
from util.util import metadata
from view.panes import Pane, NestedPane
from components.modules import *
from components.templates import LoomTerminal
from view.icons import Icons
from view.styles import textbox_config
from tkinter.font import Font
# from PIL import ImageTk, Image
import uuid
import time
import os
from pprint import pformat


modules = {'edit': Edit,
           'notes': Notes,
           'minimap': MiniMap,
           'texteditor': TextEditor,
           'prompt': Prompt,
           'children': Children,
           'read children': ReadChildren,
           'run': Run,
           'debug': DebugConsole,
           'input': Input,
           'janus/playground': JanusPlayground,
           'transformers': Transformers,
           'metaprocess': MetaProcess,
           'media': Media,
           'paint': Paint,
           'generation settings': GenerationSettings,
           'frame editor': FrameEditor,
           'memories': Memories,
           'vars': Vars,
           'wavefunction': Wavefunction}

orients = {'side_pane': "horizontal",
           "bottom_pane": "vertical"}

class Display:

    def __init__(self, root, callbacks, state, controller):
        self.root = root
        # Dict of callback names to callback data {**metadata, callback=func}
        style = ttk.Style(root)
    # set ttk theme to "clam" which support the fieldbackground option
        style.configure("Treeview", background=bg_color(), 
                        fieldbackground=bg_color())
        style.configure("TPanedwindow", background=bg_color(), 
                        fieldbackground=bg_color())
        self.callbacks = callbacks
        self.state = state
        self.controller = controller

        self.modes = {"Read", "Edit", "Visualize"}
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
        # self.secondary_textbox_frame = None
        # self.secondary_textbox = None
        # self.preview_textbox_frame = None
        # self.preview_textbox = None
        self.vis_frame = None
        self.vis = None

        # self.multiverse_frame = None
        # self.multiverse = None

        self.panes = {'side_pane': None, 'bottom_pane': None}

        self.button_frame = None

        self.search_box = None
        self.search_frame = None
        self.search_label = None
        self.case_sensitive_checkbox = None
        self.case_sensitive = None
        self.search_results = None
        self.search_close_button = None

        self.buttons = {}

        self.back_button = None
        self.forward_button = None
        self.hoist_button = None
        self.unhoist_button = None
        self.nav_button_frame = None
        self.scroll_to_selected_button = None

        self.edit_textbox_icon = None

        self.font = Font(family='Georgia', size=12)
        self.font_bold = Font(family='Georgia', size=12, weight='bold')

        self.modules = {}

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

        # self.multiverse = BlockMultiverse(self.story_frame)

        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(side="bottom", fill="both")
        self.build_main_buttons(self.button_frame)
        #self.button_bar.pack(side="top", fill="both")

        self.search_frame = ttk.Frame(self.main_pane, relief=tk.RAISED, borderwidth=2)

    def build_textboxes(self, frame):
        #self._build_textbox(frame, "preview_textbox_frame", "preview_textbox", height=3)
        self._build_textbox(frame, "textbox_frame", "textbox", height=1)
        #self._build_textbox(frame, "secondary_textbox_frame", "secondary_textbox", height=3)


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
        textbox = LoomTerminal(textbox_frame, bd=3, height=height, yscrollcommand=scrollbar.set)
        self.__setattr__(textbox_attr + "_scrollbar", scrollbar)
        self.__setattr__(textbox_attr, textbox)
        # TODO move this out
        textbox.bind("<Control-Button-1>", lambda event: self.edit_history(txt=textbox))
        textbox.bind("<Control-Shift-Button-1>", lambda event: self.goto_history(txt=textbox))
        textbox.bind("<Alt-Button-1>", lambda event: self.split_node(txt=textbox))
        textbox.bind("<Command-Button-1>", lambda event: self.split_node(txt=textbox))
        #textbox.bind("<Option-Button-1>", lambda event: self.split_node(txt=textbox))
        #textbox.bind("<Alt_L><Button-1>", lambda event: self.select_token(txt=textbox))
        
        #textbox.bind("<Button-3>", lambda event: self.open_menu(txt=textbox, event=event))
        #textbox.bind("<Button-2>", lambda event: self.open_menu(txt=textbox, event=event))
        
        textbox.bind("<Button-1>", lambda event: self.clear_selection_tags(textbox=textbox))
        textbox.bind("<Escape>", self.clear_selection_tags(textbox=textbox))
        textbox.bind("<Button-1>", lambda event: textbox.focus_set())
        textbox.bind("<Button-1>", lambda event: self.write_modifications())
        textbox.bind("<FocusOut>", lambda event: self.write_modifications())

        textbox.bind("<Button-2>", lambda event: self.right_click(event, textbox=textbox))
        textbox.bind("<Button-3>", lambda event: self.right_click(event, textbox=textbox))


        # generation
        textbox.bind("<Alt-i>", lambda event: self.inline_generate(textbox=textbox))
        textbox.bind("<Command-i>", lambda event: self.inline_generate(textbox=textbox))
        textbox.bind("<Alt-period>", lambda event: self.insert_inline_completion(step=1, textbox=textbox))
        textbox.bind("<Alt-comma>", lambda event: self.insert_inline_completion(step=-1, textbox=textbox))
        textbox.bind("<Command-period>", lambda event: self.insert_inline_completion(step=1, textbox=textbox))
        textbox.bind("<Command-comma>", lambda event: self.insert_inline_completion(step=-1, textbox=textbox))

        textbox.pack(expand=True, fill='both')

        self.setup_textbox_tags(textbox)
        # create edit textbox icon

        self.edit_textbox_icon = tk.Label(textbox_frame,
                                          image=icons.get_icon("edit-blue"),
                                          cursor='hand2',
                                          background=bg_color())
        self.edit_textbox_icon.bind("<Button-1>", lambda event: self.callbacks["Toggle textbox editable"]["callback"]())
                                          
        self.edit_textbox_icon.place(rely=1.0, relx=1.0, x=-20, y=-10, anchor=tk.SE)


        textbox.configure(**textbox_config())

    def setup_textbox_tags(self, textbox):
        #textbox.tag_configure("bold", font=self.font_bold)
        textbox.tag_configure("node_select", background=edit_color())
        textbox.tag_configure("modified", background="blue", foreground=text_color())
        textbox.tag_configure('match', background='blue', foreground=text_color())
        textbox.tag_configure('active_match', background='black', foreground='white')
        textbox.tag_raise("sel")
        textbox.tag_raise("insert")

    def clear_selection_tags(self, textbox):
        #self.display.textbox.tag_remove("sel", "1.0", "end")
        textbox.tag_remove("insert", "1.0", "end")
        textbox.tag_remove("node_select", "1.0", "end")

    def button_pressed(self, event):
        print(event.keysym)

    def write_modifications(self):
        self.callbacks["Write textbox"]["callback"]()
    
    def right_click(self, event, textbox):
        counterfactuals = self.open_counterfactuals(event=event, textbox=textbox)
        if not counterfactuals:
            self.open_menu(txt=textbox, event=event)

    def inline_generate(self, textbox):
        textbox.inline_generate(self.state.inline_generation_settings, self.state.model_config)

    def insert_inline_completion(self, textbox, step=1):
        textbox.insert_inline_completion(step)

    def open_counterfactuals(self, event, textbox):
        return textbox.open_alt_dropdown(event)

    def open_menu(self, txt, event):
        self.clear_selection_tags(txt)
        txt.tag_add("insert", txt.index(tk.CURRENT), txt.index(tk.CURRENT) + "+1c")
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Textbox menu"]["callback"](char_index=char_index, tk_current=txt.index(tk.CURRENT), e=event)

    def edit_history(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Edit history"]["callback"](index=char_index)

    def goto_history(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Goto history"]["callback"](index=char_index)

    def split_node(self, txt, event=None):
        fixed_position = txt.fix_insertion_position(txt.index(tk.CURRENT))
        char_index = txt.count("1.0", fixed_position, "chars")[0]
        self.callbacks["Split node"]["callback"](index=char_index)

    def select_token(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Select token"]["callback"](index=char_index)

    def add_summary(self, txt, event=None):
        # print('clicked')
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Insert summary"]["callback"](index=char_index)

    def build_main_buttons(self, frame):

        # First a large edit button
        # self.edit_button = self.build_button(frame, "Edit", dict(width=12))
        # self.build_button(frame, "Children")
        # self.build_button(frame, "Visualize")
        # self.build_button(frame, "Wavefunction")
        # self.build_button(frame, "Side pane")

        # Button name, button params, pack params
        buttons = [
            # Tree modification on the left
            ["Delete"],
            # ["Newline"],
            # ["Space"],
            # ["Copy"],
            ["Edit"],
            ["Children"],
            ["Visualize", {}, dict(side="right")],

            ["Bottom pane"],
            ["Side pane"],
            ["New Child", {}],
            ["Generate"],
            ["Wavefunction", {}, dict(side="right")],
            ["Map", {}, dict(side="right")],
            ["Retry", {}, dict(side="right")],
            ["Undo", {}, dict(side="right")],
            ["Rewind", {}, dict(side="right")],
            ["Reroll", {}, dict(side="right")],
            # Navigation on the right
            ["Next", {}, dict(side="right")],
            ["Prev", {}, dict(side="right")],
            # ["Parent"],
            #["Bookmark"],
        ]

        for btn in buttons:
            self.buttons[btn[0]] = self.build_button(frame, *btn)

    
    def configure_buttons(self, visible_buttons):
        visible_buttons += ["Save", "Open"]
        for btn in self.buttons:
            # hide all buttons not in the list that are currently visible
            if btn not in visible_buttons and self.buttons[btn].winfo_ismapped():
                self.buttons[btn].pack_forget()
            # show all buttons in the list that are currently hidden
            if btn in visible_buttons and not self.buttons[btn].winfo_ismapped():
                side = "right" if btn in ("Next", "Prev", "Undo", "Retry", "Rewind", "Reroll") else "left"
                self.buttons[btn].pack(side=side, fill='y')


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
        self.nav_button_frame = ttk.Frame(self.nav_frame)
        self.nav_button_frame.pack(side='top', fill='x')
        self.back_button = self.build_button(self.nav_button_frame, "<", dict(width=2), side="left")
        self.forward_button = self.build_button(self.nav_button_frame, ">", dict(width=2), side="left")
        self.hoist_button = self.build_button(self.nav_button_frame, "Hoist", dict(width=5), side="left")
        self.unhoist_button = self.build_button(self.nav_button_frame, "Unhoist", dict(width=7),side="left")
        self.scroll_to_selected_button = self.build_button(self.nav_button_frame, "Center", dict(width=6), side="left")
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

        # bind right click to context menu
        self.nav_tree.bind("<Button-3>", self.nav_tree_context_menu)
        self.nav_tree.bind("<Button-2>", self.nav_tree_context_menu)

        # File controls
        buttons = [
            # ["Clear chapters", dict(width=30), dict(fill="x", side="top")],
            ["Save", dict(width=15), dict(fill="x")],  # , dict(side="bottom", fill="x")],
            ["Open", dict(width=15), dict(fill="x")],  # , dict(side="bottom", fill="x")],
        ]
        for btn in buttons:
            self.buttons[btn[0]] = self.build_button(self.nav_frame, *btn)

    def nav_tree_context_menu(self, event):
        # get the item the mouse is over
        item = self.nav_tree.identify('item', event.x, event.y)
        if item:
            # TODO abstract this menu and use for children module too
            # create a menu
            menu = tk.Menu(self.nav_tree, tearoff=0)
            # add a command to the menu
            menu.add_command(label="Go", command=lambda id=item: self.callbacks["Select node"]["callback"](node=self.state.node(id)))
            menu.add_command(label="Edit", command=lambda id=item: self.callbacks["Edit in module"]["callback"](node=self.state.node(id)))
            #menu.add_command(label="Copy")
            menu.add_command(label="Copy id", command=lambda id=item: self.callbacks["Copy id"]["callback"](node=self.state.node(id)))
            menu.add_command(label="Duplicate", command=lambda id=item: self.callbacks["Duplicate"]["callback"](node=self.state.node(id)))
            menu.add_command(label="Delete", command=lambda id=item: self.callbacks["Delete"]["callback"](node=self.state.node(id)))
            menu.add_command(label="Delete children", command=lambda id=item: self.callbacks["Delete children"]["callback"](node=self.state.node(id)))

            move_menu = tk.Menu(menu, tearoff=0)
            move_menu.add_command(label="Move up", command=lambda id=item: self.callbacks["Move up"]["callback"](node=self.state.node(id)))
            move_menu.add_command(label="Move down", command=lambda id=item: self.callbacks["Move down"]["callback"](node=self.state.node(id)))
            #move_menu.add_command(label="Move to top")
            #move_menu.add_command(label="Move to bottom")
            #move_menu.add_command(label="Move to parent level")
            #move_menu.add_command(label="Change parent...")
            menu.add_cascade(label="Move", menu=move_menu)
            
            view_menu = tk.Menu(menu, tearoff=0)

            #view_menu.add_command(label="Hide")
            view_menu.add_command(label="Hoist", command=lambda id=item: self.callbacks["Hoist"]["callback"](node=self.state.node(id)))
            # contingent
            #view_menu.add_command(label="Zip")
            # contingent
            #view_menu.add_command(label="Unzip")
            # contingent
            view_menu.add_command(label="Expand subtree", command=lambda id=item: self.callbacks["Expand subtree"]["callback"](node=self.state.node(id)))
            # contingent
            view_menu.add_command(label="Collapse subtree", command=lambda id=item: self.callbacks["Collapse subtree"]["callback"](node=self.state.node(id)))

            menu.add_cascade(label="View", menu=view_menu)

            add_menu = tk.Menu(menu, tearoff=0)
            add_menu.add_command(label="Add child", command=lambda id=item: self.callbacks["New Child"]["callback"](node=self.state.node(id)))
            add_menu.add_command(label="Add sibling", command=lambda id=item: self.callbacks["New Sibling"]["callback"](node=self.state.node(id)))
            add_menu.add_command(label="Add parent", command=lambda id=item: self.callbacks["New Parent"]["callback"](node=self.state.node(id)))
            #add_menu.add_command(label="Add ghostchild")
            #add_menu.add_command(label="Add ghostparent")
            #add_menu.add_command(label="Add portal")

            menu.add_cascade(label="Add", menu=add_menu)

            tag_menu = tk.Menu(menu, tearoff=0)

            #tag_menu.add_command(label="Pin")
            tag_menu.add_command(label="Archive", command=lambda id=item: self.callbacks["Tag"]["callback"](tag='archived', node=self.state.node(id)))
            tag_menu.add_command(label="Archive children", command=lambda id=item: self.callbacks["Archive children"]["callback"](node=self.state.node(id)))
            #tag_menu.add_command(label="Turn into note")
            tag_menu.add_command(label="Tag...", command=lambda id=item: self.callbacks["Tag node dialog"]["callback"](node=self.state.node(id)))
            
            menu.add_cascade(label="Tag", menu=tag_menu)
            
            #menu.add_command(label="Edit frame")
            #menu.add_command(label="Edit chapter")
            #menu.add_command(label="Info")
            #menu.add_command(label="Export subtree")

            # display the menu
            menu.tk_popup(event.x_root, event.y_root)

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
        if self.chapter_nav_frame is not None:
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

    def pane_open(self, pane_name):
        pane = self.panes[pane_name]
        if pane:
            return not pane.hidden
        else:
            return False

    # called when refreshing state
    def close_pane(self, pane_name):
        if self.panes[pane_name]:
            pane = self.panes[pane_name]
            pane.hide()

    # called by hide button
    def pane_closed(self, pane):
        pane_name = pane.name
        #print('display: pane_closed')
        self.state.update_user_frame({'workspace': {pane_name: {'open': False}}})
        self.close_pane(pane_name)

    def open_pane(self, pane_name):
        if self.panes[pane_name]:
            self.panes[pane_name].show()
        else:
            orient = orients[pane_name]
            if orient == 'horizontal':
                parent = self.pane
            else:
                parent = self.main_pane
            self.panes[pane_name] = NestedPane(pane_name, parent, orient='horizontal' if orient == 'vertical' else 'vertical', 
                                               module_options=modules.keys(),
                                               module_selection_callback=self.module_selected,
                                               module_window_destroy_callback=self.window_closed,
                                               hide_pane_callback=self.pane_closed)
            self.panes[pane_name].build_pane(weight=1)

            self.build_modules(self.panes[pane_name], self.state.workspace[pane_name]['modules'])

    def build_modules(self, pane, module_names):
        for module in module_names:
            self.add_module(pane, module)

    def add_module(self, pane, module_name):
        module = modules[module_name](callbacks=self.callbacks, state=self.state)
        pane.add_module(module)
        self.modules[module_name] = module

    def open_module_in_window(self, window, module_name):
        module = modules[module_name](callbacks=self.callbacks, state=self.state)
        window.change_module(module)
        self.modules[module_name] = module

    def module_open(self, module_name):
        return module_name in self.modules and self.modules[module_name]

    # checks modules in pane against list, creates ones that don't exist, and 
    # removes ones that aren't in the list
    def update_modules(self, pane_name, new_module_names):
        pane = self.panes[pane_name]
        current_module_names = pane.module_names()
        new_modules, deleted_modules = react_changes(current_module_names, new_module_names)
        #print('new modules:', new_modules)
        #print('deleted modules:', deleted_modules)
        #print('added modules:', new_modules)
        for module_name in deleted_modules:
            # TODO
            if module_name in self.modules:
                window = self.modules[module_name].window()
                self.close_window(window)
        for module_name in new_modules:
            self.add_module(pane, module_name)

    # TODO change this
    def set_module(self, pane_name, module_name, idx):
        pane = self.panes[pane_name]
        if len(pane.module_windows) > idx:
            # this will cause update event to create a module if the name has changed
            pane.module_windows[idx].set_selection(module_name)
        elif len(pane.module_windows) == idx:
            pane.add_module(module_name)

    def module_selected(self, module_window):
        module_name = module_window.module_selection.get()
        # if module_name is not current module
        if not module_window.module or module_name != module_window.module.name:
            self.open_module_in_window(module_window, module_name)
            pane_name = module_window.pane_name()
            pane = self.panes[pane_name]
            current_modules = pane.module_names()
            self.state.update_user_frame({'workspace': {pane_name: {'modules': current_modules}}})
            

    def close_window(self, module_window):
        if module_window.module:
            module_name = module_window.module.name
            self.modules[module_name] = None
        module_window.destroy()

    # called by x button
    def window_closed(self, module_window):
        self.close_window(module_window)
        pane_name = module_window.pane_name()
        pane = self.panes[pane_name]
        current_modules = pane.module_names()
        self.state.update_user_frame({'workspace': {pane_name: {'modules': current_modules}}})

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
        self.buttons['Edit'].config(text="Write" if self.in_edit_mode else self.button_name("Edit"))

        self.clear_story_frame()

        if self.mode == "Read":
            self.textbox_frame.pack(expand=True, side="top", fill='both')
            self.textbox.config(foreground=text_color(), background=bg_color())
            self.textbox.edit_reset()

        elif self.mode == "Edit":
            self.textbox_frame.pack(expand=True, side="top", fill='both')
            self.textbox.config(foreground=text_color(), background=edit_color())
            #self.secondary_textbox_frame.pack(expand=False, side="bottom", fill='both')
            #self.secondary_textbox.config(foreground=text_color(), background=edit_color())
            #self.preview_textbox.config(foreground=text_color(), background=edit_color())

        elif self.mode == "Visualize":
            self.vis.frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # elif self.mode == "Multiverse":
        #     self.multiverse.frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        else:
            raise NotImplementedError(self.mode, type(self.mode))

    def clear_story_frame(self):
        # self.destroy_multi_edit()
        self.textbox_frame.pack_forget()
        #self.secondary_textbox_frame.pack_forget()
        self.vis.frame.pack_forget()
        # self.multiverse.frame.pack_forget()

    # def close_secondary_textbox(self):
    #     self.secondary_textbox_frame.pack_forget()

    # def open_secondary_textbox(self):
    #     self.secondary_textbox_frame.pack(expand=False, side="bottom", fill='both')

    # def close_preview_textbox(self):
    #     self.preview_textbox_frame.pack_forget()

    # def open_preview_textbox(self):
    #     self.preview_textbox_frame.pack(expand=False, side="top", fill='both')

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