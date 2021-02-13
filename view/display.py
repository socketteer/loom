import tkinter as tk
from tkinter import ttk
from tkinter.font import Font

import PIL

from tree_vis import TreeVis
from util.custom_tks import TextAware, ScrollableFrame
from colors import bg_color, text_color, edit_color
from util.util import metadata


class Display:

    def __init__(self, root, callbacks, vis_settings, state):
        self.root = root
        # Dict of callback names to callback data {**metadata, callback=func}
        self.callbacks = callbacks
        self.vis_settings = vis_settings
        self.state = state

        self.frame = ttk.Frame(self.root)
        self.frame.pack(expand=True, fill="both")

        self.modes = {"Read", "Edit", "Multi Edit", "Visualize"}
        self.mode = "Read"

        # Variables initialized below
        self.nav_frame = None
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


    # TODO make a decorator which automatically caches default=CACHE args. None should be a cachable value
    # Caches param arguments so repeated calls will use the same args unless overridden
    @metadata(first_call=True, arguments={})
    def build_button(self, frame, name, button_params=None, pack_params=None):
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

        button.pack(**{**dict(side="left", fill="y"), **(pack_params if pack_params else {})})
        return button


    #################################
    #   Display
    #################################

    def build_static(self):
        self.bookmark_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/star_small.png"))
        self.marker_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/marker.png"))
        self.media_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/media.png"))


    def build_display(self, frame):
        self.build_nav(frame)
        self.nav_frame.pack(expand=False, fill='both', side='left', anchor='nw')

        self.build_main_frame(frame)
        self.main_frame.pack(expand=True, fill='both', side='right', anchor="ne")


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
                           self.callbacks["Nav Select"]["callback"],
                           self.callbacks["Save Edits"]["callback"],
                           self.vis_settings,
                           self.state)

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
            ["New Child"],
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

        # Tree
        self.build_tree(self.nav_frame)
        self.nav_tree.pack(expand=True, fill='both', side='top', anchor='nw')


        # File controls
        buttons = [
            ["Save", dict(width=30), dict(side="bottom", fill="x")],
            ["Open"],
            ["Clear chapters"]
        ]
        for btn in buttons:
            self.build_button(self.nav_frame, *btn)

        # Chapter tree below nav tree
        self.build_chapter_nav(self.nav_frame)
        #self.chapter_nav_frame.pack(expand=True, fill='both', side='bottom', anchor="se")
        self.chapter_nav_frame.pack(expand=True, fill='both', side='bottom', anchor="se")


    def build_chapter_nav(self, frame):
        self.chapter_nav_frame = ttk.Frame(frame, height=400, width=300, relief='sunken', borderwidth=2)
        self.build_chapter_tree(self.chapter_nav_frame)
        self.chapter_nav_tree.pack(expand=True, fill='both', side='top', anchor='se')

    # TODO Fix styling, these should be adjustable height, default to smaller chapter nav
    # TODO Reduce duplication of these two methods
    # TODO make a scrollable navtree. Ah fuck it scrollable obj
    def build_tree(self, frame):
        style = ttk.Style(frame)
        style.configure('Treeview', rowheight=25)  # Spacing between rows
        self.nav_tree = ttk.Treeview(frame, selectmode="browse", padding=(0, 0, 0, 1))

        # Nav tree scrollbar
        self.nav_scrollbary = ttk.Scrollbar(self.nav_tree, orient="vertical", command=self.nav_tree.yview)
        self.nav_scrollbary.pack(side="left", fill="y")
        self.nav_tree.configure(yscrollcommand=self.nav_scrollbary.set)

        self.nav_scrollbarx = ttk.Scrollbar(self.nav_tree, orient="horizontal", command=self.nav_tree.xview)
        self.nav_tree.configure(xscrollcommand=self.nav_scrollbarx.set)
        self.nav_scrollbarx.pack(side='bottom', fill='x')

        # Nav bar click listener. Must be done here because we need event data
        f = self.callbacks["Nav Select"]["callback"]
        self.nav_tree.bind("<Button-1>", lambda event: f(node_id=self.nav_tree.identify('item', event.x, event.y)))
        self.nav_tree.bind("<<TreeviewSelect>>", lambda event: f(node_id=(self.nav_tree.selection()[0])))

    def build_chapter_tree(self, frame):
        style = ttk.Style(frame)
        style.configure('Treeview', rowheight=25)  # Spacing between rows
        self.chapter_nav_tree = ttk.Treeview(frame, selectmode="browse", padding=(0, 0, 0, 1))

        # Nav tree scrollbar
        self.chapter_nav_scrollbary = ttk.Scrollbar(self.chapter_nav_tree, orient="vertical", command=self.chapter_nav_tree.yview)
        self.chapter_nav_scrollbary.pack(side="left", fill="y")
        self.chapter_nav_tree.configure(yscrollcommand=self.chapter_nav_scrollbary.set)

        self.chapter_nav_scrollbarx = ttk.Scrollbar(self.chapter_nav_tree, orient="horizontal", command=self.chapter_nav_tree.xview)
        self.chapter_nav_tree.configure(xscrollcommand=self.chapter_nav_scrollbarx.set)
        self.chapter_nav_scrollbarx.pack(side='bottom', fill='x')

        # Nav bar click listener. Must be done here because we need event data
        f = self.callbacks["Nav Select"]["callback"]
        self.chapter_nav_tree.bind("<Button-1>", lambda event: f(node_id=self.chapter_nav_tree.identify('item', event.x, event.y)))
        #self.chapter_nav_tree.bind("<<TreeviewSelect>>", lambda event: f(node_id=(self.chapter_nav_tree.selection()[0])))

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
