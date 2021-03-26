import tkinter as tk
from tkinter import ttk
from tkinter.font import Font

import PIL

from view.tree_vis import TreeVis
from util.custom_tks import TextAware, ScrollableFrame
from view.colors import bg_color, text_color, edit_color
from util.util import metadata


class Display:

    def __init__(self, root, callbacks, state, controller):
        self.root = root
        # Dict of callback names to callback data {**metadata, callback=func}
        self.callbacks = callbacks
        self.state = state
        self.controller = controller

        self.modes = {"Read", "Edit", "Multi Edit", "Visualize"}
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

        self.main_frame = None

        self.story_frame = None
        self.textbox_frame = None
        self.textbox = None
        self.secondary_textbox_frame = None
        self.secondary_textbox = None
        self.vis_frame = None
        self.vis = None
        self.notes_frame = None
        self.notes_textbox = None

        self.multi_edit_frame = None
        self.multi_textboxes = None

        self.button_bar = None
        self.edit_button = None

        # Build it!
        self.build_static()
        self.build_display(self.frame)
        self.set_mode(self.mode)


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
    def build_button(self, frame, name, button_params=None, pack_params=None, pack=True):
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
            button.pack(**{**dict(side="left", fill="y"), **(pack_params if pack_params else {})})
        return button


    def ctrl_click(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Edit history"]["callback"](index=char_index)

    def alt_click(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Goto history"]["callback"](index=char_index)

    def ctrl_alt_click(self, txt, event=None):
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Split node"]["callback"](index=char_index)

    #################################
    #   Display
    #################################

    def build_static(self):
        self.bookmark_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/star_small.png"))
        self.marker_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/marker.png"))
        self.media_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/media.png"))


    def build_display(self, frame):
        self.pane = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        self.pane.pack(expand=True, fill="both")

        self.build_nav(self.pane)
        self.pane.add(self.nav_frame, weight=1)

        self.build_main_frame(self.pane)
        self.pane.add(self.main_frame, weight=6)

        if self.state.preferences["side_pane"]:
            self.open_side()

    #################################
    #   Main frame
    #################################


    def build_main_frame(self, frame):
        self.main_frame = ttk.Frame(frame, width=500, height=500)

        # Textbox
        self.story_frame = ttk.Frame(self.main_frame)
        self.story_frame.pack(expand=True, fill='both')

        self.build_textboxes(self.story_frame)
        self.textbox_frame.pack(expand=True, fill="both")

        self.vis = TreeVis(self.story_frame,
                           self.state, self.controller)

        # Button bar
        self.build_main_buttons(self.main_frame)
        self.button_bar.pack(side="bottom", fill="x")

    def build_textboxes(self, frame):
        self._build_textbox(frame, "textbox_frame", "textbox", height=1)
        self._build_textbox(frame, "secondary_textbox_frame", "secondary_textbox", height=3)


    # Text area and scroll bar  TODO Make a scrollable textbox tkutil
    def _build_textbox(self, frame, frame_attr, textbox_attr, height=1):
        textbox_frame = ttk.Frame(frame)
        self.__setattr__(frame_attr, textbox_frame)

        scrollbar = ttk.Scrollbar(textbox_frame, command=lambda *args: self.__getattribute__(textbox_attr).yview(*args))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        textbox = TextAware(textbox_frame, bd=3, height=height, yscrollcommand=scrollbar.set, undo=True)
        self.__setattr__(textbox_attr, textbox)
        # TODO move this out
        textbox.bind("<Control-Button-1>", lambda event: self.ctrl_click(txt=textbox))
        textbox.bind("<Alt-Button-1>", lambda event: self.alt_click(txt=textbox))
        textbox.bind("<Control-Alt-Button-1>", lambda event: self.ctrl_alt_click(txt=textbox))
        textbox.pack(expand=True, fill='both')

        readable_font = Font(family="Georgia", size=12)  # Other nice options: Helvetica, Arial, Georgia
        textbox.configure(
            font=readable_font,
            spacing1=10,
            foreground=text_color(),
            background=bg_color(),
            padx=2,
            pady=5,
            spacing2=8,  # Spacing between lines4
            spacing3=5,
            wrap="word",
        )


    def build_main_buttons(self, frame):
        self.button_bar = ttk.Frame(frame, width=500, height=20)

        # First a large edit button
        self.edit_button = self.build_button(frame, "Edit", dict(width=12))
        self.build_button(frame, "Child Edit")
        self.build_button(frame, "Visualize")

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
            ["Prev"],
            # ["Parent"],
            ["Bookmark"],
        ]

        for btn in buttons:
            self.build_button(frame, *btn)


    #################################
    #   Nav Panel
    #################################

    def build_nav(self, frame):
        self.nav_frame = ttk.Frame(frame, height=500, width=300, relief='sunken', borderwidth=2)
        self.nav_pane = ttk.PanedWindow(self.nav_frame, height=500, width=300)
        self.nav_pane.pack(expand=True, fill='both')

        # Tree nav
        self._build_treeview(self.nav_frame, "nav_tree", "nav_scrollbarx", "nav_scrollbary")
        self.nav_pane.add(self.nav_tree, weight=3)
        # Chapter nav
        self._build_treeview(self.nav_frame, "chapter_nav_tree")
        self.nav_pane.add(self.chapter_nav_tree, weight=1)

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
            ["Clear chapters", dict(width=30), dict(fill="x", side="top")],
            ["Save", dict(width=15), dict(fill="x")],#, dict(side="bottom", fill="x")],
            ["Open", dict(width=15), dict(fill="x")],#, dict(side="bottom", fill="x")],
        ]
        for btn in buttons:
            self.build_button(self.nav_frame, *btn)


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


    #################################
    #   Side panel
    #################################

    def build_side(self, frame):
        self.side_frame = ttk.Frame(frame, height=500, width=300, relief='sunken', borderwidth=2)

        self._build_textbox(self.side_frame, "notes_frame", "notes_textbox", height=1)
        self.notes_frame.pack(expand=True, fill="both")

    def open_side(self):
        self.build_side(self.pane)
        self.pane.add(self.side_frame, weight=1)

    def destroy_side(self):
        if self.side_frame is not None:
            self.side_frame.pack_forget()
            self.side_frame.destroy()
            self.notes_frame = None

    #################################
    #   Edit mode
    #################################

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
            self.secondary_textbox_frame.pack(expand=False, side="bottom", fill='both')
            self.textbox.config(foreground=text_color(), background=edit_color())
            self.secondary_textbox.config(foreground=text_color(), background=edit_color())

        # Caller needs to use start_multi_edit
        elif self.mode == "Multi Edit":
            pass

        elif self.mode == "Visualize":
            self.vis.frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        else:
            raise NotImplementedError(self.mode, type(self.mode))


    def clear_story_frame(self):
        self.destroy_multi_edit()
        self.textbox_frame.pack_forget()
        self.secondary_textbox_frame.pack_forget()
        self.vis.frame.pack_forget()


    def start_multi_edit(self, num_textboxes=5):
        assert self.mode == "Multi Edit"
        self.clear_story_frame()

        self.multi_edit_frame = ScrollableFrame(self.story_frame)
        self.multi_edit_frame.pack(expand=True, fill="both")

        self.multi_textboxes = [TextAware(self.multi_edit_frame.scrollable_frame, height=5) for i in range(num_textboxes)]
        for tb in self.multi_textboxes:
            tb.pack(expand=True, fill="both")
            readable_font = Font(family="Georgia", size=12)  # Other nice options: Helvetica, Arial, Georgia
            tb.configure(
                font=readable_font,
                spacing1=10,
                foreground=text_color(),  # Darkmode
                background=bg_color(),
                padx=2,
                pady=2,
                # spacing2=3,  # Spacing between lines4
                # spacing3=3,
                wrap="word",
            )


    def destroy_multi_edit(self):
        # Caused crashes. Oh well, memory leaks are fine.
        # if self.multi_textboxes is not None:
        #     for tb in self.multi_textboxes:
        #         tb.pack_forget()
        #         tb.destroy()
        #         self.multi_textboxes = None
        if self.multi_edit_frame is not None:
            self.multi_edit_frame.pack_forget()
            self.multi_edit_frame.destroy()
            self.multi_edit_frame = None
            self.multi_textboxes = []



# #################################
# #   Events generated by the UI
# #################################
#
# # Returns a lambda which generates an event on this display frame with the given name
# def event(self, event_name):
#     assert event_name in self.events.keys(), event_name
#     # Must form closure with _event_name!
#     return lambda *args, _event_name=event_name: self.frame.event_generate(f"<<{_event_name}>>")
#
#
# # # Register a listener to an event on this display frame
# # # Virtual event data doesn't work, so just take a no-argument funcs
# # # TODO Could create a dict of event data dicts and provide them to the binders myself... no.
# def listen(self, event_name, func):
#     assert event_name in self.events.keys(), event_name
#     # CAREFUL. If you don't make the lambda args a closure it will be lost
#     # because it will look just like the other lambdas until evaluated...
#     self.frame.bind(f"<<{event_name}>>", lambda tk_event, _func=func: func())
#
# def bind_handlers(self):
#     nav_select_handler = self.events["NavTreeSelect"]["call"]
#
#     # Nav bar click listener. Must be done here because we need event data
#     self.nav_tree.bind("<Button-1>", lambda event: nav_select_handler(self.nav_tree.identify('item', event.x, event.y)))
#     self.nav_tree.bind("<<TreeviewSelect>>", lambda event: nav_select_handler(self.nav_tree.selection()[0]))
#
#     for event_name, event_data in self.events.items():
#         if event_name != "NavTreeSelect":
#             self.listen(event_name, event_data["call"])
