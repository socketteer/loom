import tkinter as tk
from tkinter import ttk
from tkinter.font import Font

import PIL

from view.tree_vis import TreeVis
from view.block_multiverse import BlockMultiverse
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

        self.main_frame = None

        self.story_frame = None
        self.textbox_frame = None
        self.textbox = None
        self.secondary_textbox_frame = None
        self.secondary_textbox = None
        self.vis_frame = None
        self.vis = None

        self.multiverse_frame = None
        self.multiverse = None

        self.notes_frame = None
        self.notes_textbox_frame = None
        self.notes_textbox = None
        self.notes_options_frame = None
        self.notes_title = None
        self.notes_select = None
        self.scope_select = None
        self.change_root_button = None
        self.delete_note_button = None

        self.bottom_frame = None
        self.input_box = None
        self.input_frame = None
        self.mode_select = None
        self.submit_button = None
        self.mode_var = None
        self.debug_box = None
        self.past_box = None

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



    #################################
    #   Display
    #################################

    def build_static(self):
        self.bookmark_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/star_small.png"))
        self.marker_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/marker.png"))
        self.media_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/media.png"))
        self.empty_icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/icons/empty.png"))


    def build_display(self, frame):
        self.pane = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        self.pane.pack(expand=True, fill="both")

        self.build_nav(self.pane)
        self.pane.add(self.nav_frame, weight=1)

        self.build_main_frame(self.pane)
        self.pane.add(self.main_frame, weight=6)

        #self.open_side()
        if self.state.preferences["side_pane"]:
            self.open_side()

        #self.destroy_chapter_nav()

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

        self.multiverse = BlockMultiverse(self.story_frame, self.set_pastbox_text)

        self.bottom_input_frame = ttk.Frame(self.main_frame)
        self.bottom_input_frame.pack(side="bottom", fill="both")

        self.bottom_frame = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)#ttk.Frame(self.main_frame)
        self.bottom_frame.pack(side="bottom", fill="both")
        # Button bar        self.input_frame.pack(side="bottom", fill="x")
        self.build_main_buttons(self.bottom_frame)
        self.button_bar.pack(side="top", fill="both")
        #self.build_debug_box()

        # if self.state.preferences['input_box']:
        #     self.build_input_box(self.bottom_frame)

        #self.destroy_input_box()

    def build_textboxes(self, frame):
        self._build_textbox(frame, "textbox_frame", "textbox", height=1)
        self._build_textbox(frame, "secondary_textbox_frame", "secondary_textbox", height=3)

    def build_past_box(self):
        self.rebuild_bottom_frame()
        self.past_box = TextAware(self.bottom_input_frame, bd=3, height=3)
        self.past_box.pack(expand=True, fill='x')
        self.past_box.configure(
            foreground='white',
            background='black',
            wrap="word",
        )
        self.past_box.configure(state="disabled")

    def set_pastbox_text(self, text):
        print(self.past_box)
        if self.past_box:
            print('writing:', text)
            self.past_box.configure(state="normal")
            self.past_box.delete("1.0", "end")
            self.past_box.insert("end-1c", text)
            self.past_box.configure(state="disabled")

    def build_debug_box(self):
        self.rebuild_bottom_frame()
        self.debug_box = TextAware(self.bottom_input_frame, bd=3, height=12)
        self.debug_box.pack(expand=True, fill='x')
        self.debug_box.configure(
            foreground='white',
            background='black',
            wrap="word",
        )
        self.debug_box.configure(state="disabled")

    def build_input_box(self):
        self.rebuild_bottom_frame()
        self.bottom_frame.pack_forget()
        self.bottom_input_frame.pack_forget()
        self.bottom_input_frame.pack(side="bottom", fill="both")
        self.bottom_frame.pack(side="bottom", fill="both")
        self.input_frame = ttk.Frame(self.bottom_input_frame, width=500, height=20)
        self.input_box = TextAware(self.input_frame, bd=3, height=3, undo=True)
        readable_font = Font(family="Georgia", size=12)
        self.input_box.pack(expand=True, fill='x')
        self.input_box.configure(
            font=readable_font,
            spacing1=10,  # spacing between paragraphs
            foreground=text_color(),
            background=bg_color(),
            padx=2,
            pady=5,
            spacing2=8,  # Spacing between lines
            spacing3=5,
            wrap="word",
        )
        self.input_box.bind("<Key>", lambda event: self.key_pressed(event))
        self.mode_var = tk.StringVar()
        choices = ('default', 'chat', 'dialogue', 'antisummary')
        self.mode_select = tk.OptionMenu(self.input_frame, self.mode_var, *choices)
        self.mode_var.trace('w', self.callbacks["Update mode"]["callback"])

        tk.Label(self.input_frame, text="Mode", bg=bg_color(), fg=text_color()).pack(side='left')
        self.mode_select.pack(side='left')

        self.submit_button = ttk.Button(self.input_frame, text="Submit",
                                        command=self.callbacks["Submit"]["callback"], width=10)
        self.submit_button.pack(side='right')
        self.input_frame.pack(side="bottom", expand=True, fill="both")

    def rebuild_bottom_frame(self):
        self.destroy_bottom_frame()
        self.bottom_frame.pack_forget()
        self.bottom_input_frame.pack(side="bottom", fill="both")
        self.bottom_frame.pack(side="bottom", fill="both")


    def destroy_bottom_frame(self):
        if self.debug_box is not None:
            self.debug_box.pack_forget()
            self.debug_box.destroy()
        if self.input_frame is not None:
            self.input_frame.pack_forget()
            self.input_frame.destroy()
        if self.past_box is not None:
            self.past_box.pack_forget()
            self.past_box.destroy()
        self.debug_box = None
        self.input_box = None
        self.past_box = None
        self.submit_button = None
        self.bottom_input_frame.pack_forget()


    def key_pressed(self, event=None):
        if event.keysym in ('Tab'):
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
        self.__setattr__(textbox_attr, textbox)
        # TODO move this out
        textbox.bind("<Control-Button-1>", lambda event: self.edit_history(txt=textbox))
        textbox.bind("<Control-Shift-Button-1>", lambda event: self.goto_history(txt=textbox))
        textbox.bind("<Control-Alt-Button-1>", lambda event: self.split_node(txt=textbox))
        textbox.bind("<Alt-Button-1>", lambda event: self.select_token(txt=textbox))
        textbox.bind("<Button-3>", lambda event: self.add_summary(txt=textbox))
        textbox.pack(expand=True, fill='both')

        readable_font = Font(family="Georgia", size=12)  # Other nice options: Helvetica, Arial, Georgia
        textbox.configure(
            font=readable_font,
            spacing1=10, # spacing between paragraphs
            foreground=text_color(),
            background=bg_color(),
            padx=2,
            pady=5,
            spacing2=8,  # Spacing between lines
            spacing3=5,
            wrap="word",
        )


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
        #print('clicked')
        char_index = txt.count("1.0", txt.index(tk.CURRENT), "chars")[0]
        self.callbacks["Insert summary"]["callback"](index=char_index)

    def build_main_buttons(self, frame):
        self.button_bar = ttk.Frame(frame, width=500, height=20)

        # First a large edit button
        self.edit_button = self.build_button(frame, "Edit", dict(width=12))
        #self.build_button(frame, "Child Edit")
        self.build_button(frame, "Visualize")
        self.build_button(frame, "Multiverse")

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
            ["Clear chapters", dict(width=30), dict(fill="x", side="top")],
            ["Save", dict(width=15), dict(fill="x")],#, dict(side="bottom", fill="x")],
            ["Open", dict(width=15), dict(fill="x")],#, dict(side="bottom", fill="x")],
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


    #################################
    #   Side panel
    #################################

    # TODO bind to variables
    def build_side(self, frame):
        self.side_frame = ttk.Frame(frame, height=500, width=300, relief='sunken', borderwidth=2)
        self.notes_options_frame = ttk.Frame(self.side_frame, height=200, width=300)
        self.notes_options_frame.pack(fill='both')

        tk.Label(self.notes_options_frame, text="Select note", bg=bg_color(), fg=text_color()).grid(column=0, row=0)
        placeholder_options = ('aaaaa', 'bbbbbb', 'cccccc')
        v = tk.StringVar()
        v.set(placeholder_options[0])

        self.notes_select = tk.OptionMenu(self.notes_options_frame, v, *placeholder_options)
        #self.notes_select['menu'].config(relief='raised')
        self.notes_select.grid(column=1, row=0)

        tk.Label(self.notes_options_frame,
                 text="Scope",
                 bg=bg_color(),
                 fg=text_color()).grid(column=2, row=0, padx=5)

        scope_options = ('node', 'subtree', 'global')
        v = tk.StringVar()
        v.set(scope_options[0])
        self.scope_select = tk.OptionMenu(self.notes_options_frame, v, *scope_options)
        self.scope_select.grid(column=3, row=0)

        tk.Label(self.notes_options_frame, text="Note title", bg=bg_color(), fg=text_color()).grid(column=0, row=1)
        self.notes_title = tk.Entry(self.notes_options_frame,
                                    bg=bg_color(),
                                    fg=text_color(),
                                    relief='sunken')
        self.notes_title.grid(column=1, row=1, padx=10)
        tk.Label(self.notes_options_frame, text="Root node", bg=bg_color(), fg=text_color()).grid(column=2, row=1)
        tk.Label(self.notes_options_frame, text="placeholder id ...", bg=bg_color(), fg='blue').grid(column=3, row=1)
        self.change_root_button = tk.Button(self.notes_options_frame, text='Change', bg=bg_color(), fg=text_color())
        self.change_root_button.grid(column=4, row=1)
        self.change_root_button = tk.Button(self.notes_options_frame, text='Delete', bg=bg_color(), fg=text_color())
        self.change_root_button.grid(column=5, row=1, padx=10)

        self.notes_frame = ttk.Frame(self.side_frame)
        self.notes_frame.pack(expand=True, fill='both')
        self._build_textbox(self.notes_frame, "notes_textbox_frame", "notes_textbox", height=1)
        self.notes_textbox_frame.pack(expand=True, fill="both")

    def open_side(self):
        self.build_side(self.pane)
        self.pane.add(self.side_frame, weight=1)

    def destroy_side(self):
        if self.side_frame is not None:
            self.side_frame.pack_forget()
            self.side_frame.destroy()
            self.notes_frame = None
            self.notes_options_frame = None
            self.notes_select = None
            self.notes_title = None
            self.scope_select = None
            self.change_root_button = None
            self.delete_note_button = None

    # TODO chapter_nav_frame is currently not used
    def destroy_chapter_nav(self):
        print('destroy chapter nav')
        if self.chapter_nav_frame is not None:
            print('destroying')
            self.chapter_nav_frame.pack_forget()
            self.chapter_nav_frame.destroy()
            self.chapter_nav_tree = None
            self.chapter_nav_scrollbarx = None

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

        elif self.mode == "Multiverse":
            self.multiverse.frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        else:
            raise NotImplementedError(self.mode, type(self.mode))


    def clear_story_frame(self):
        self.destroy_multi_edit()
        self.textbox_frame.pack_forget()
        self.secondary_textbox_frame.pack_forget()
        self.vis.frame.pack_forget()
        self.multiverse.frame.pack_forget()


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
