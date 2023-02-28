import math
import os

import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText
from view.icons import Icons

from loom.components.templates import *
from loom.utils.custom_tks import Dialog, TextAware
from loom.utils.keybindings import special_keybindings
from loom.utils.util_tk import (
    Entry,
    create_button,
    create_checkbutton,
    create_combo_box,
    create_label,
    create_side_label,
    create_slider,
)
from loom.utils.util_tree import search
from loom.view.colors import PROB_1, PROB_2, PROB_3, PROB_4, PROB_5, PROB_6, bg_color, text_color
from loom.view.styles import textbox_config

icons = Icons()


class InfoDialog(Dialog):
    def __init__(self, parent, data_dict):
        self.data_dict = data_dict
        Dialog.__init__(self, parent, title="Information", cancellable=False)

    def body(self, master):
        for label_text, data_text in self.data_dict.items():
            create_side_label(master, label_text)
            create_label(master, data_text, row=master.grid_size()[1] - 1, col=1, padx=15)


class NodeInfoDialog(Dialog):
    def __init__(self, parent, node, state):
        self.node = node
        self.state = state
        Dialog.__init__(self, parent, title="Node Metadata", cancellable=False)

    def body(self, master):
        create_side_label(master, "id")
        create_label(master, self.node["id"], row=master.grid_size()[1] - 1, col=1, padx=15)

        create_side_label(master, "mutable")
        create_label(
            master,
            "true" if self.state.is_mutable(self.node) else "false",
            row=master.grid_size()[1] - 1,
            col=1,
            padx=15,
        )

        create_side_label(master, "bookmarked")
        create_label(
            master,
            "true" if self.state.has_tag(self.node, "bookmark") else "false",
            row=master.grid_size()[1] - 1,
            col=1,
            padx=15,
        )

        create_side_label(master, "visited")
        create_label(
            master,
            "true" if self.node.get("visited", False) else "false",
            row=master.grid_size()[1] - 1,
            col=1,
            padx=15,
        )

        create_side_label(master, "canonical")
        create_label(
            master,
            "true" if self.state.has_tag(self.node, "canonical") else "false",
            row=master.grid_size()[1] - 1,
            col=1,
            padx=15,
        )

        if "meta" in self.node:
            meta = self.node["meta"]
            create_side_label(master, "source")
            if "source" in meta:
                create_label(master, meta["source"], row=master.grid_size()[1] - 1, col=1, padx=15)
            else:
                create_label(master, "unknown", row=master.grid_size()[1] - 1, col=1, padx=15)

            if "creation_timestamp" in meta:
                create_side_label(master, "created at")
                create_label(master, meta["creation_timestamp"], row=master.grid_size()[1] - 1, col=1, padx=15)

        if "generation" in self.node:
            model_response, prompt, completion = self.state.get_request_info(self.node)
            if model_response:
                create_side_label(master, "prompt")
                prompt_text = tk.Text(master, height=15)
                prompt_text.grid(row=master.grid_size()[1] - 1, column=1)
                prompt_text.insert(tk.INSERT, prompt)
                prompt_text.configure(
                    state="disabled",
                    spacing1=8,
                    foreground=text_color(),
                    background=bg_color(),
                    wrap="word",
                )
                # makes text copyable
                prompt_text.bind("<Button>", lambda event: prompt_text.focus_set())

                create_side_label(master, "original generated text")
                gen_text = tk.Text(master, height=5)
                gen_text.grid(row=master.grid_size()[1] - 1, column=1)
                gen_text.insert(tk.INSERT, completion["text"])

                gen_text.tag_config("prob_1", background=PROB_1)
                gen_text.tag_config("prob_2", background=PROB_2)
                gen_text.tag_config("prob_3", background=PROB_3)
                gen_text.tag_config("prob_4", background=PROB_4)
                gen_text.tag_config("prob_5", background=PROB_5)
                gen_text.tag_config("prob_6", background=PROB_6)

                # TODO continuous coloration
                for i, token_data in enumerate(completion["tokens"]):
                    prob = math.exp(token_data["generatedToken"]["logprob"])
                    label = (
                        "prob_1"
                        if prob >= 0.8
                        else "prob_2"
                        if prob >= 0.6
                        else "prob_3"
                        if prob >= 0.4
                        else "prob_4"
                        if prob >= 0.2
                        else "prob_5"
                        if prob >= 0.05
                        else "prob_6"
                    )

                    gen_text.tag_add(
                        label,
                        f"0.1 + {token_data['position']['start']} chars",
                        f"0.1 + {token_data['position']['end']} chars",
                    )

                gen_text.configure(state="disabled")

                gen_text.bind("<Button>", lambda event: gen_text.focus_set())
                create_side_label(master, "model")
                create_label(master, model_response["model"], row=master.grid_size()[1] - 1, col=1, padx=15)


class SearchDialog(Dialog):
    def __init__(self, parent, state, goto):
        self.state = state
        self.subtree = tk.BooleanVar(value=0)
        self.text = tk.BooleanVar(value=1)
        self.chapters = tk.BooleanVar(value=1)
        self.tags = tk.BooleanVar(value=1)
        self.canonical = tk.BooleanVar(value=0)
        self.regex = tk.BooleanVar(value=0)
        self.case_sensitive = tk.BooleanVar(value=0)
        self.results = []
        self.labels = []
        self.goto_buttons = []
        self.num_results_label = None
        self.depth_limit = None
        self.search_entry = None
        self.goto = goto
        self.next_page_button = None
        self.prev_page_button = None
        self.master = None
        Dialog.__init__(self, parent, title="Search")

    def body(self, master):
        self.master = master

        # TODO
        # advanced options - show/hide
        # search ancestry
        create_side_label(master, "Subtree only")
        check = ttk.Checkbutton(master, variable=self.subtree)
        check.grid(row=self.master.grid_size()[1] - 1, column=1)

        create_side_label(master, "Case sensitive")
        check = ttk.Checkbutton(master, variable=self.case_sensitive)
        check.grid(row=self.master.grid_size()[1] - 1, column=1)
        create_side_label(master, "Search text")
        check = ttk.Checkbutton(master, variable=self.text)
        check.grid(row=self.master.grid_size()[1] - 1, column=1)
        create_side_label(master, "Search chapter titles")
        check = ttk.Checkbutton(master, variable=self.chapters)
        check.grid(row=self.master.grid_size()[1] - 1, column=1)
        create_side_label(master, "Search tags")
        check = ttk.Checkbutton(master, variable=self.tags)
        check.grid(row=self.master.grid_size()[1] - 1, column=1)
        create_side_label(master, "Canonical only")
        check = ttk.Checkbutton(master, variable=self.canonical)
        check.grid(row=self.master.grid_size()[1] - 1, column=1)
        create_side_label(master, "Regex")
        check = ttk.Checkbutton(master, variable=self.regex)
        check.grid(row=self.master.grid_size()[1] - 1, column=1)

        self.depth_limit = Entry(master, master.grid_size()[1], "Max depth", "", None, width=5)

        self.search_entry = Entry(master, master.grid_size()[1], "Search", "", None, width=20)
        self.search_entry.focus_entry()
        create_button(master, "Search", self.search)

        # return causes freeze whether or not bound
        # self.master.bind('<Return>', lambda event=None: self.search)

    # TODO super deprecated
    def search(self):
        search_term = self.search_entry.tk_variables.get()
        if not search_term:
            print("not")
            return
        depth_limit = self.depth_limit.tk_variables.get()
        if not depth_limit:
            depth_limit = None
        else:
            depth_limit = int(depth_limit)
        root = self.state.selected_node if self.subtree.get() else self.state.tree_raw_data["root"]
        print("case sensitive: ", self.case_sensitive.get())
        matches = search(
            root=root,
            pattern=search_term,
            text=self.text.get(),
            tags=self.tags.get(),
            case_sensitive=self.case_sensitive.get(),
            regex=self.regex.get(),
            filter_set=self.state.tagged_nodes("canonical") if self.canonical.get() else None,
            max_depth=depth_limit,
        )

        self.search_results(matches)

    def search_results(self, matches, start=0):
        # remove previous search results
        context_padding = 50
        limit = 4
        counter = 0
        if self.num_results_label:
            self.num_results_label.destroy()
        if self.next_page_button:
            self.next_page_button.destroy()
        if self.prev_page_button:
            self.prev_page_button.destroy()
        for result in self.results:
            result.destroy()
        for label in self.labels:
            label.destroy()
        for button in self.goto_buttons:
            button.destroy()
        self.results = []
        self.labels = []
        self.goto_buttons = []
        self.num_results_label = create_side_label(self.master, f"{len(matches)} results")
        for i, match in enumerate(matches[start:]):
            if counter >= limit:
                break
            node = self.state.tree_node_dict[match["node_id"]]
            chapter = self.state.chapter(node)["title"] if self.state.chapter(node) else ""
            self.labels.append(create_side_label(self.master, f"chapter: {chapter}"))
            # side_label.config(fg="blue")
            self.results.append(TextAware(self.master, height=2))
            # readable_font = Font(family="Georgia", size=12)
            self.results[i].configure(
                # font=readable_font,
                spacing1=8,
                foreground=text_color(),
                background=bg_color(),
                wrap="word",
            )
            self.results[i].grid(row=self.master.grid_size()[1] - 1, column=1)
            node_text = node["text"]
            start_index = max(0, match["span"][0] - context_padding)
            end_index = min(len(node_text), match["span"][1] + context_padding)
            text_window = node_text[start_index:end_index]
            self.results[i].insert(tk.INSERT, text_window)
            self.results[i].tag_configure("blue", background="blue")
            self.results[i].highlight_pattern(match["match"], "blue")
            self.results[i].configure(state="disabled")

            # makes text copyable
            # binding causes computer to freeze
            # self.results[i].bind("<Button>", lambda event, _result=self.results[i]: result.focus_set())
            # matched_text.bind("<Alt-Button-1>", lambda event: self.goto_result(match['node_id']))

            self.goto_buttons.append(
                create_button(self.master, "go to match", lambda _match=match: self.goto_result(_match["node_id"]))
            )
            self.goto_buttons[i].grid(row=self.master.grid_size()[1] - 2, column=2)
            counter += 1
        if start > 0:
            self.prev_page_button = create_button(
                self.master,
                "previous page",
                lambda _start=start, _limit=limit: self.search_results(matches, start=_start - _limit),
            )
            self.prev_page_button.config(width=12)
        if len(matches) > start + limit:
            self.next_page_button = create_button(
                self.master,
                "next page",
                lambda _start=start, _limit=limit: self.search_results(matches, start=_start + _limit),
            )

    def goto_result(self, id):
        self.ok()
        self.goto(node_id=id)


class GotoNode(Dialog):
    def __init__(self, parent, goto):
        self.goto = goto
        Dialog.__init__(self, parent, title="Goto")

    def body(self, master):
        self.id_entry = Entry(master, master.grid_size()[1], "Goto id", "", None, width=20)
        self.id_entry.controls.focus_set()

    def apply(self):
        entry_text = self.id_entry.tk_variables.get()
        self.goto(entry_text)


class ChaptersInfoDialog(Dialog):
    def __init__(self, parent, data_dict):
        self.data_dict = data_dict
        Dialog.__init__(self, parent, title="Chapters")

    def body(self, master):
        for iid, chapter in self.data_dict.items():
            create_side_label(master, chapter["title"])
            create_label(master, "is a chapter", row=master.grid_size()[1] - 1, col=1, padx=15)


class NodeChapterDialog(Dialog):
    def __init__(self, parent, node, state):
        self.node = node
        self.new_chapter_title = None
        self.state = state
        Dialog.__init__(self, parent, title="Chapter")

    def body(self, master):
        create_side_label(master, "Current Chapter")
        chapter_name = "None" if "chapter_id" not in self.node else self.state.chapter_title(self.node)
        create_label(master, chapter_name, row=master.grid_size()[1] - 1, col=1, padx=15)
        self.new_chapter_title = Entry(master, master.grid_size()[1], "Enter new chapter title", "", None)
        self.new_chapter_title.controls.focus_set()

    def apply(self):
        new_title = self.new_chapter_title.tk_variables.get()
        self.state.create_new_chapter(node=self.node, title=new_title)


class TagNodeDialog(Dialog):
    def __init__(self, parent, node, state, modifications):
        self.node = node
        self.parent = parent
        self.state = state
        self.tags_textbox = None
        self.original_tags = self.node.get("tags", [])
        self.modifications = modifications
        Dialog.__init__(self, parent, title="Tag node")

    def body(self, master):
        tags = "" if "tags" not in self.node else ", ".join(self.original_tags)
        self.tags_textbox = Entry(master, master.grid_size()[1], "Tags", tags, None, width=20)
        self.tags_textbox.controls.focus_set()

    def apply(self):
        tags_string = self.tags_textbox.tk_variables.get()
        tags = [tag.strip() for tag in tags_string.split(",")]
        for tag in tags:
            if tag:
                if tag not in self.state.tags:
                    AddTagDialog(self.parent, self.state, tag)
                if tag in self.state.tags and tag not in self.original_tags:
                    self.state.tag_node(self.node, tag)
                    self.modifications["add"].append(tag)
        for tag in self.original_tags:
            if tag not in tags:
                self.state.untag_node(self.node, tag)
                self.modifications["remove"].append(tag)


class AddTagDialog(Dialog):
    def __init__(self, parent, state, tag_name=None):
        self.state = state
        self.title_textbox = None
        # self.scope_dropdown = None
        self.vars = {
            "scope": tk.StringVar(),
            "hide": tk.BooleanVar(),
            "show_only": tk.BooleanVar(),
            "toggle_key": tk.StringVar(),
        }
        self.tag_name = tag_name
        self.icon_name = "None"
        self.icon = None
        self.change_icon_button = None
        self.hide_checkbox = None
        self.show_only_checkbox = None
        self.scope_dropdown = None
        self.toggle_key_dropdown = None
        Dialog.__init__(self, parent, title="Add tag")

    def body(self, master):
        self.master = master
        name = self.tag_name if self.tag_name else ""
        self.title_textbox = Entry(master, master.grid_size()[1], "Tag name", name, None)
        self.title_textbox.controls.focus_set()
        create_side_label(master, "Scope")
        scope_options = ("node", "ancestry", "subtree")
        self.vars["scope"].set("node")

        self.scope_dropdown = tk.OptionMenu(master, self.vars["scope"], *scope_options)
        self.scope_dropdown.grid(row=master.grid_size()[1] - 1, column=1, pady=3)
        self.hide_checkbox = create_checkbutton(master, "Hide", "hide", self.vars)
        self.show_only_checkbox = create_checkbutton(master, "Show only", "show_only", self.vars)
        self.configure_checkbuttons()
        for var in self.vars.values():
            var.trace("w", self.configure_checkbuttons)
        keybinding_options = special_keybindings.keys()
        self.vars["toggle_key"].set("None")
        create_side_label(master, "Toggle key")
        self.toggle_key_dropdown = tk.OptionMenu(master, self.vars["toggle_key"], *keybinding_options)
        self.toggle_key_dropdown.grid(row=master.grid_size()[1] - 1, column=1, pady=3)
        create_side_label(master, "Nav icon")
        self.draw_icon()
        self.change_icon_button = tk.Button(master, text="Change icon", command=self.change_icon)
        self.change_icon_button.grid(row=master.grid_size()[1] - 1, column=2, pady=3)

    def draw_icon(self):
        if self.icon:
            self.icon.destroy()
        if self.icon_name == "None":
            self.icon = tk.Label(self.master, text="None", fg=text_color(), bg=bg_color())
        else:
            icon = icons.get_icon(self.icon_name)
            self.icon = tk.Label(self.master, bg=bg_color())
            self.icon.image = icon
            self.icon.configure(image=icon)
        self.icon.grid(row=self.master.grid_size()[1] - 1, column=1, pady=3)

    def change_icon(self, *args):
        # open a file chooser dialog and allow the user to select an image
        file_path = filedialog.askopenfilename(
            title="Choose an image",
            initialdir=f"loom/static/icons/tag_icons/",
            filetypes=[("PNG", ".png"), ("JPEG", ".jpg"), ("GIF", ".gif")],
        )
        if file_path:
            self.icon_name = os.path.splitext(os.path.basename(file_path))[0]
            self.draw_icon()

    def configure_checkbuttons(self, *args):
        # hide is false and disabled if scope == 'ancestry' or if show_only is true
        if self.vars["show_only"].get():  # if self.vars['scope'].get() == 'ancestry' or self.vars['show_only'].get():
            self.vars["hide"].set(False)
            self.hide_checkbox.configure(state=tk.DISABLED)
        else:
            self.hide_checkbox.configure(state=tk.NORMAL)
        # show_only is false and disabled if scope == 'node' or if hide is true
        if self.vars["hide"].get():  # self.vars['scope'].get() == 'node' or self.vars['hide'].get():
            self.vars["show_only"].set(False)
            self.show_only_checkbox.configure(state=tk.DISABLED)
        else:
            self.show_only_checkbox.configure(state=tk.NORMAL)

    def apply(self):
        self.state.add_tag(
            self.title_textbox.tk_variables.get(),
            self.vars["scope"].get(),
            self.vars["hide"].get(),
            self.vars["show_only"].get(),
            self.vars["toggle_key"].get(),
            self.icon_name,
        )


class TagsDialog(Dialog):
    def __init__(self, parent, state, modifications=None):
        self.state = state
        self.parent = parent
        self.modifications = modifications
        self.vars = {}
        self.widgets = {}
        self.icon_names = {}
        self.add_button = None
        Dialog.__init__(self, parent, title="Tags")

    def body(self, master):
        self.master = master
        # create header labels
        create_side_label(master, "Tag")
        create_side_label(master, "Scope", row=master.grid_size()[1] - 1, col=1)
        create_side_label(master, "Hide", row=master.grid_size()[1] - 1, col=2)
        create_side_label(master, "Show only", row=master.grid_size()[1] - 1, col=3)
        create_side_label(master, "Toggle key", row=master.grid_size()[1] - 1, col=4)
        create_side_label(master, "Nav icon", row=master.grid_size()[1] - 1, col=5)
        for tag, properties in self.state.tags.items():
            self.add_row(tag, properties)
        self.make_add_button()

    def make_add_button(self):
        self.add_button = tk.Button(self.master, text="Add tag", command=self.add_tag)
        self.add_button.grid(row=self.master.grid_size()[1], column=0, pady=3)

    def add_row(self, tag, properties):
        scope_options = ("node", "ancestry", "subtree")
        keybinding_options = special_keybindings.keys()
        self.vars[tag] = {
            "scope": tk.StringVar,
            "hide": tk.BooleanVar,
            "show_only": tk.BooleanVar,
            "toggle_key": tk.StringVar,
        }
        self.widgets[tag] = {}
        for key in self.vars[tag].keys():
            self.vars[tag][key] = self.vars[tag][key](value=properties[key])
        self.icon_names[tag] = properties["icon"]
        self.widgets[tag]["name"] = create_side_label(self.master, tag)
        self.widgets[tag]["scope_dropdown"] = tk.OptionMenu(self.master, self.vars[tag]["scope"], *scope_options)
        self.widgets[tag]["scope_dropdown"].grid(row=self.master.grid_size()[1] - 1, column=1, pady=3)
        self.widgets[tag]["hide_checkbox"] = tk.Checkbutton(self.master, variable=self.vars[tag]["hide"])
        self.widgets[tag]["hide_checkbox"].grid(row=self.master.grid_size()[1] - 1, column=2, pady=3)
        self.widgets[tag]["show_only_checkbox"] = tk.Checkbutton(self.master, variable=self.vars[tag]["show_only"])
        self.widgets[tag]["show_only_checkbox"].grid(row=self.master.grid_size()[1] - 1, column=3, pady=3)

        # trace all vars to configure checkbuttons
        for var in self.vars[tag].values():
            var.trace("w", lambda *_, _tag=tag: self.configure_checkbuttons(_tag))

        self.widgets[tag]["toggle_key_dropdown"] = tk.OptionMenu(
            self.master, self.vars[tag]["toggle_key"], *keybinding_options
        )
        self.widgets[tag]["toggle_key_dropdown"].grid(row=self.master.grid_size()[1] - 1, column=4, pady=3)
        self.configure_checkbuttons(tag)
        # draw icon
        self.widgets[tag]["icon"] = None
        self.draw_icon(tag, row=self.master.grid_size()[1] - 1)
        # add button for changing icon
        self.widgets[tag]["change_icon_button"] = tk.Button(
            self.master,
            text="Change icon",
            command=lambda _tag=tag, _row=self.master.grid_size()[1] - 1: self.change_icon(_tag, _row),
        )
        self.widgets[tag]["change_icon_button"].grid(row=self.master.grid_size()[1] - 1, column=6, pady=3)

        # make delete button
        self.widgets[tag]["delete_button"] = tk.Button(
            self.master, text="Delete", command=lambda _tag=tag: self.delete_tag(_tag), width=4
        )
        self.widgets[tag]["delete_button"].grid(row=self.master.grid_size()[1] - 1, column=7, pady=3)

    def draw_icon(self, tag, row):
        if self.widgets[tag]["icon"]:
            self.widgets[tag]["icon"].destroy()
        if self.icon_names[tag] == "None":
            self.widgets[tag]["icon"] = tk.Label(self.master, text="None", bg=bg_color(), fg=text_color())
        else:
            icon = icons.get_icon(self.icon_names[tag])
            self.widgets[tag]["icon"] = tk.Label(self.master, bg=bg_color())
            self.widgets[tag]["icon"].image = icon
            self.widgets[tag]["icon"].configure(image=icon)
        self.widgets[tag]["icon"].grid(row=row, column=5, padx=2, pady=2)

    def change_icon(self, tag, row):
        # open a file chooser dialog and allow the user to select an image
        file_path = filedialog.askopenfilename(
            title="Choose an image",
            initialdir=f"loom/static/icons/tag_icons/",
            filetypes=[("PNG", ".png"), ("JPEG", ".jpg"), ("GIF", ".gif")],
        )
        if file_path:
            self.icon_names[tag] = os.path.splitext(os.path.basename(file_path))[0]
            self.draw_icon(tag, row)

    def configure_checkbuttons(self, tag):
        # hide is false and disabled if scope == 'ancestry' or if show_only is true
        if self.vars[tag][
            "show_only"
        ].get():  # self.vars[tag]['scope'].get() == 'ancestry' or self.vars[tag]['show_only'].get():
            self.vars[tag]["hide"].set(False)
            self.widgets[tag]["hide_checkbox"].configure(state=tk.DISABLED)
        else:
            self.widgets[tag]["hide_checkbox"].configure(state=tk.NORMAL)
        # show_only is false and disabled if scope == 'node' or if hide is true
        if self.vars[tag]["hide"].get():  # self.vars[tag]['scope'].get() == 'node' or self.vars[tag]['hide'].get():
            self.vars[tag]["show_only"].set(False)
            self.widgets[tag]["show_only_checkbox"].configure(state=tk.DISABLED)
        else:
            self.widgets[tag]["show_only_checkbox"].configure(state=tk.NORMAL)

    def append_new_tags(self):
        # remove add_tag button
        self.add_button.grid_remove()
        # adds new rows for new tags in self.state.tags that aren't already in self.vars
        for tag in self.state.tags:
            print(f"adding tag {tag}")
            if tag not in self.vars:
                self.add_row(tag, self.state.tags[tag])
        # add add_tag button
        self.make_add_button()

    def add_tag(self, *args):
        # open AddTagDialog
        add_tag_dialog = AddTagDialog(self.parent, self.state)
        # pprint(self.state.tags)
        self.append_new_tags()

    def delete_tag(self, tag):
        self.state.delete_tag(tag)
        self.vars.pop(tag)
        # remove row from grid
        self.widgets[tag]["name"].grid_remove()
        self.widgets[tag]["scope_dropdown"].grid_remove()
        self.widgets[tag]["hide_checkbox"].grid_remove()
        self.widgets[tag]["show_only_checkbox"].grid_remove()
        self.widgets[tag]["toggle_key_dropdown"].grid_remove()
        self.widgets[tag]["change_icon_button"].grid_remove()
        self.widgets[tag]["icon"].grid_remove()
        self.widgets[tag]["delete_button"].grid_remove()

    def apply(self):
        for tag in self.vars:
            for key, var in self.vars[tag].items():
                self.state.tags[tag][key] = var.get()
            self.state.tags[tag]["icon"] = self.icon_names[tag]
        self.result = True


# class AIMemory(Dialog):
#     def __init__(self, parent, node, state):
#         self.node = node
#         self.state = state
#         self.memories = []
#         self.checks = []
#         self.edit_buttons = []
#         self.master = None
#         self.new_button = None
#         Dialog.__init__(self, parent, title="AI Memory")

#     def body(self, master):
#         create_label(master, "Memory (prepended to AI input)")
#         self.master = master
#         self.refresh()


#     def refresh(self):
#         if self.new_button:
#             self.new_button.destroy()
#         for memory in self.memories:
#             memory.destroy()
#         for check in self.checks:
#             check.destroy()
#         for edit_button in self.edit_buttons:
#             edit_button.destroy()
#         self.memories = []
#         self.checks = []
#         self.edit_buttons = []

#         for i, memory in enumerate(self.state.construct_memory(self.node)):
#             if memory['text']:
#                 temp_check = tk.BooleanVar()
#                 temp_check.set(True)
#                 row = self.master.grid_size()[1]
#                 self.memories.append(TextAware(self.master, height=1))
#                 self.memories[i].grid(row=row, column=0, columnspan=2, padx=5)
#                 self.memories[i].insert(tk.INSERT, memory['text'])
#                 self.memories[i].configure(
#                     state='disabled',
#                     foreground=text_color(),
#                     background=bg_color(),
#                     wrap="word",
#                 )
#                 # FIXME checks are unchecked by default
#                 self.checks.append(tk.Checkbutton(self.master, variable=temp_check))
#                 self.checks[i].grid(row=row, column=2, padx=3)
#                 self.edit_buttons.append(create_button(self.master, "Edit", lambda _memory=memory: self.edit_memory(_memory), width=4))
#                 self.edit_buttons[i].grid(row=row, column=3)
#         self.new_button = create_button(self.master, "Add memory", self.create_new, width=11)


#     def create_new(self):
#         dialog = CreateMemory(parent=self.parent, node=self.node, state=self.state, default_inheritability='subtree')
#         self.refresh()

#     def edit_memory(self, memory):
#         dialog = EditMemory(parent=self.parent, memory=memory, state=self.state)
#         self.refresh()

#     def apply(self):
#         pass


# TODO repeated code
# class NodeMemory(Dialog):
#     def __init__(self, parent, node, state):
#         self.node = node
#         self.state = state
#         self.memories = []
#         self.master = None
#         self.new_button = None
#         self.edit_buttons = []
#         Dialog.__init__(self, parent, title="Node Memory")

#     def body(self, master):
#         create_label(master, "Memory entries associated with this node")
#         self.master = master
#         self.refresh()

#     def refresh(self):
#         if self.new_button:
#             self.new_button.destroy()
#         for memory in self.memories:
#             memory.destroy()
#         for edit_button in self.edit_buttons:
#             edit_button.destroy()
#         self.memories = []
#         self.checks = []
#         self.edit_buttons = []

#         if 'memories' in self.node:
#             for i, memory_id in enumerate(self.node['memories']):
#                 memory = self.state.memories[memory_id]
#                 if memory['text']:
#                     row = self.master.grid_size()[1]
#                     self.memories.append(TextAware(self.master, height=1))
#                     self.memories[i].grid(row=row, column=0, columnspan=2, padx=5)
#                     self.memories[i].insert(tk.INSERT, memory['text'])
#                     self.memories[i].configure(
#                         state='disabled',
#                         foreground=text_color(),
#                         background=bg_color(),
#                         wrap="word",
#                     )
#                     self.edit_buttons.append(create_button(self.master, "Edit", lambda _memory=memory: self.edit_memory(_memory), width=4))
#                     self.edit_buttons[i].grid(row=row, column=3)
#         self.new_button = create_button(self.master, "Add memory", self.create_new, width=11)


#     def create_new(self):
#         dialog = CreateMemory(parent=self.parent, node=self.node, state=self.state, default_inheritability='subtree')
#         self.refresh()

#     def edit_memory(self, memory):
#         dialog = EditMemory(parent=self.parent, memory=memory, state=self.state)
#         self.refresh()

#     def apply(self):
#         pass


class MemoryDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, title="Edit memory entry", enter_to_apply=False)

    def body(self, master):
        self.memory_textbox = ScrolledText(master, height=3)
        self.memory_textbox.grid(row=master.grid_size()[1], column=0, columnspan=2)
        self.memory_textbox.configure(**textbox_config())
        self.memory_textbox.insert(tk.INSERT, self.memory_text)
        self.memory_textbox.focus()
        row = master.grid_size()[1]
        create_side_label(master, "Inheritability", row)
        inheritability_options = ("none", "subtree", "delayed", "global")
        self.inheritability.set(self.memory_inheritability)
        dropdown = tk.OptionMenu(master, self.inheritability, *inheritability_options)
        dropdown.grid(row=row, column=1, pady=3)


class CreateMemory(MemoryDialog):
    def __init__(self, parent, node, state, default_inheritability="delayed"):
        self.node = node
        self.state = state
        self.inheritability = tk.StringVar()
        self.memory_textbox = None
        self.memory_text = ""
        self.memory_inheritability = default_inheritability
        MemoryDialog.__init__(self, parent)

    def apply(self):
        memory_text = self.memory_textbox.get("1.0", "end-1c")
        if memory_text:
            self.state.create_memory(self.node, memory_text, self.inheritability.get())


class EditMemory(MemoryDialog):
    def __init__(self, parent, memory, state):
        self.memory = memory
        self.state = state
        self.inheritability = tk.StringVar()
        self.delete_button = None
        self.memory_textbox = None
        self.memory_text = self.memory["text"]
        self.memory_inheritability = self.memory["inheritability"]
        self.delete_button = None
        MemoryDialog.__init__(self, parent)

    def body(self, master):
        MemoryDialog.body(self, master)
        self.delete_button = create_button(master, "Delete memory", self.delete_memory, width=15)

    def delete_memory(self):
        self.state.delete_memory_entry(self.memory)
        self.cancel()

    def apply(self):
        memory_text = self.memory_textbox.get("1.0", "end-1c")
        self.memory["text"] = memory_text
        self.memory["inheritability"] = self.inheritability.get()


class SummaryDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, title="Edit summary", enter_to_apply=False)

    def body(self, master):
        self.summary_textbox = ScrolledText(master, height=2)
        self.summary_textbox.grid(row=master.grid_size()[1], column=0, columnspan=2)
        self.summary_textbox.configure(**textbox_config())
        self.summary_textbox.insert(tk.INSERT, self.init_text)
        self.summary_textbox.focus()
        self.referent_textbox = ScrolledText(master, height=6)
        self.referent_textbox.configure(**textbox_config())
        row = master.grid_size()[1]
        self.referent_textbox.grid(row=row, column=0, columnspan=2, rowspan=4)
        self.refresh_referent()
        self.remove_all_button = create_button(master, "--", self.remove_all_children, width=3)
        self.remove_all_button.grid(row=row, column=2, sticky="w")
        self.remove_child_button = create_button(master, "-", self.remove_child, width=3)
        self.remove_child_button.grid(row=row + 1, column=2, sticky="w")
        self.add_child_button = create_button(master, "+", self.add_child, width=3)
        self.add_child_button.grid(row=row + 2, column=2, sticky="w")
        self.add_all_button = create_button(master, "++", self.add_all_children, width=3)
        self.add_all_button.grid(row=row + 3, column=2, sticky="w")
        self.refresh_buttons()

    def refresh_referent(self):
        self.referent_textbox.configure(state="normal")
        self.referent_textbox.delete("1.0", "end")
        self.referent_textbox.insert(tk.INSERT, self.root["text"][self.position :])
        for node in self.included_nodes[1:]:
            self.referent_textbox.insert(tk.INSERT, node["text"])
        self.referent_textbox.configure(state="disabled")

    def refresh_buttons(self):
        if len(self.included_nodes) == 1:
            self.remove_all_button.configure(state="disabled")
            self.remove_child_button.configure(state="disabled")
        else:
            self.remove_all_button.configure(state="normal")
            self.remove_child_button.configure(state="normal")

        if len(self.included_nodes) == len(self.descendents):
            self.add_all_button.configure(state="disabled")
            self.add_child_button.configure(state="disabled")
        else:
            self.add_all_button.configure(state="normal")
            self.add_child_button.configure(state="normal")

    def remove_all_children(self):
        self.included_nodes = [self.root]
        self.refresh_referent()
        self.refresh_buttons()

    def remove_child(self):
        self.included_nodes = self.included_nodes[:-1]
        self.refresh_referent()
        self.refresh_buttons()

    def add_child(self):
        self.included_nodes.append(self.descendents[len(self.included_nodes)])
        self.refresh_referent()
        self.refresh_buttons()

    def add_all_children(self):
        self.included_nodes = self.descendents
        self.refresh_referent()
        self.refresh_buttons()


class CreateSummary(SummaryDialog):
    def __init__(self, parent, root_node, state, position=0):
        self.root = root_node
        self.position = position
        self.summary_textbox = None
        self.referent_textbox = None
        self.state = state
        self.included_nodes = [self.root]
        self.remove_all_button = None
        self.remove_child_button = None
        self.add_child_button = None
        self.add_all_button = None
        self.init_text = ""
        self.descendents = self.state.ancestry(root=self.root, node=self.state.selected_node)
        Dialog.__init__(self, parent)

    def apply(self):
        summary_text = self.summary_textbox.get("1.0", "end-1c")
        if summary_text:
            if self.position != 0:
                self.state.split_node(self.root, self.position)
            self.state.create_summary(root_node=self.root, end_node=self.included_nodes[-1], summary_text=summary_text)


class EditSummary(SummaryDialog):
    def __init__(self, parent, summary, state):
        self.state = state
        self.root = self.state.tree_node_dict[summary["root_id"]]
        self.position = 0
        self.summary = summary
        self.summary_textbox = None
        self.referent_textbox = None
        end_node = self.state.tree_node_dict[summary["end_id"]]
        self.included_nodes = self.state.ancestry_in_range(root=self.root, node=end_node)
        self.remove_all_button = None
        self.remove_child_button = None
        self.add_child_button = None
        self.add_all_button = None
        self.delete_button = None
        self.init_text = self.summary["text"]
        self.descendents = self.state.ancestry_in_range(root=self.root, node=self.state.selected_node)
        Dialog.__init__(self, parent)

    def body(self, master):
        SummaryDialog.body(self, master)
        self.delete_button = create_button(master, "Delete summary", self.delete_summary, width=15)

    def delete_summary(self):
        self.state.delete_summary(self.summary)
        self.cancel()

    def apply(self):
        summary_text = self.summary_textbox.get("1.0", "end-1c")
        self.state.summaries[self.summary["id"]]["text"] = summary_text
        self.state.summaries[self.summary["id"]]["end_id"] = self.included_nodes[-1]["id"]


class Summaries(Dialog):
    def __init__(self, parent, node, state):
        self.node = node
        self.state = state
        self.summaries = []
        self.edit_buttons = []
        self.master = None
        Dialog.__init__(self, parent, title="Summaries")

    def body(self, master):
        self.master = master
        self.refresh()

    def refresh(self):
        for summary in self.summaries:
            summary.destroy()
        for edit_button in self.edit_buttons:
            edit_button.destroy()
        self.memories = []
        self.edit_buttons = []

        for i, summary in enumerate(self.state.past_summaries(self.node)):
            if summary["text"]:
                row = self.master.grid_size()[1]
                self.summaries.append(TextAware(self.master, height=1))
                self.summaries[i].grid(row=row, column=0, columnspan=2, padx=5)
                self.summaries[i].insert(tk.INSERT, summary["text"])
                self.summaries[i].configure(
                    state="disabled",
                    foreground=text_color(),
                    background=bg_color(),
                    wrap="word",
                )
                self.edit_buttons.append(
                    create_button(self.master, "Edit", lambda _summary=summary: self.edit_summary(_summary), width=4)
                )
                self.edit_buttons[i].grid(row=row, column=3)

    def edit_summary(self, summary):
        dialog = EditSummary(parent=self.parent, summary=summary, state=self.state)

    def apply(self):
        pass


class WorkspaceDialog(Dialog):
    def __init__(self, parent, orig_params):
        self.orig_params = orig_params
        self.vars = {
            "input_box": tk.BooleanVar,
            "debug_box": tk.BooleanVar,
            "show_children": tk.BooleanVar,
            "alt_textbox": tk.BooleanVar,
        }
        for key in self.vars.keys():
            self.vars[key] = self.vars[key](value=orig_params[key])

        Dialog.__init__(self, parent, title="Workspace")

    def body(self, master):
        # row = master.grid_size()[1]
        # create_side_label(master, "Notes", row)
        # check = ttk.Checkbutton(master, variable=self.vars["notes"])
        # check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Input box", row)
        check = ttk.Checkbutton(master, variable=self.vars["input_box"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Debug box", row)
        check = ttk.Checkbutton(master, variable=self.vars["debug_box"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Show children", row)
        check = ttk.Checkbutton(master, variable=self.vars["show_children"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Alt textbox", row)
        check = ttk.Checkbutton(master, variable=self.vars["alt_textbox"])
        check.grid(row=row, column=1, pady=3)

    def apply(self):
        for key, var in self.vars.items():
            self.orig_params[key] = var.get()
        self.result = self.orig_params


class VisualizationSettingsDialog(Dialog):
    def __init__(self, parent, orig_params):
        self.orig_params = orig_params
        self.vars = {
            "text_width": tk.IntVar,
            "leaf_distance": tk.IntVar,
            "level_distance": tk.IntVar,
            "text_size": tk.IntVar,
            "horizontal": tk.BooleanVar,
            "display_text": tk.BooleanVar,
            "show_buttons": tk.BooleanVar,
            "chapter_mode": tk.BooleanVar,
        }
        for key in self.vars.keys():
            self.vars[key] = self.vars[key](value=orig_params[key])

        Dialog.__init__(self, parent, title="Visualization Settings")

    # Creates sliders for each sensitivity slider
    def body(self, master):
        sliders = {
            "text_width": (10, 1000),
            "leaf_distance": (1, 500),
            "level_distance": (1, 500),
            "text_size": (1, 25),
        }
        for name, value_range in sliders.items():
            create_slider(master, name, self.vars[name], value_range)

        for name in ["horizontal", "display_text", "show_buttons", "chapter_mode"]:
            row = master.grid_size()[1]
            create_side_label(master, name, row)
            check = ttk.Checkbutton(master, variable=self.vars[name])
            check.grid(row=row, column=1, pady=3)

        create_button(master, "Reset", self.reset_variables)

    # Reset all sliders to 50
    def reset_variables(self):
        for key, var in self.vars.items():
            var.set(self.orig_params[key])

    # Put the slider values into the result field
    def apply(self):
        for key, var in self.vars.items():
            self.orig_params[key] = var.get()
        self.result = self.orig_params


class MultimediaDialog(Dialog):
    def __init__(self, parent, callbacks, state):
        self.multimedia = Multimedia(callbacks, state)
        Dialog.__init__(self, parent, title="Multimedia")

    def body(self, master):
        self.multimedia.body(master)


class RunDialog(Dialog):
    def __init__(self, parent, callbacks, init_text=""):
        self.eval_code = EvalCode(init_text, callbacks)
        Dialog.__init__(self, parent, title="Run code", enter_to_apply=False)

    def body(self, master):
        self.eval_code.body(master)

    def apply(self):
        self.eval_code.apply()


class PreferencesDialog(Dialog):
    def __init__(self, parent, orig_params, user_params, state):
        self.preferences = Preferences(orig_params, user_params, state, realtime_update=False)
        Dialog.__init__(self, parent, title="Settings")

    def body(self, master):
        self.preferences.body(master)

    def apply(self):
        self.preferences.write_user_frame()


class GenerationSettingsDialog(Dialog):
    def __init__(self, parent, orig_params, user_params, state):
        self.orig_params = orig_params
        self.generation_control = FullGenerationSettings(orig_params, user_params, state, realtime_update=False)
        Dialog.__init__(self, parent, title="Generation Settings")

    # Creates sliders for each sensitivity slider
    def body(self, master):
        self.generation_control.body(master)

    def reset_variables(self):
        pass

    def apply(self):
        self.generation_control.write_user_frame()


class ExportOptionsDialog(Dialog):
    def __init__(self, parent, options_dict):
        self.export_options = ExportOptions(options_dict)
        Dialog.__init__(self, parent, title="Export Options")

    def body(self, master):
        self.export_options.body(master)

    def apply(self):
        self.export_options.write()
        self.result = self.export_options


# TODO option to apply to user frame
# TODO use generic settings dialog with overrides?
# TODO use program vars?
class ChatDialog(Dialog):
    def __init__(self, parent, state):
        self.state = state
        self.AI_name_entry = None
        self.player_name_entry = None
        self.master = None
        self.AI_prefix = "\\n"
        self.AI_suffix = ":"
        self.player_prefix = "\n"
        self.player_suffix = ": {input}"
        Dialog.__init__(self, parent, title="Settings")

    def body(self, master):
        self.master = master
        self.AI_name_entry = Entry(master, master.grid_size()[1], "AI name", "", None, width=20)
        self.player_name_entry = Entry(master, master.grid_size()[1], "Player name", "", None, width=20)
        self.set_names()

    def set_names(self):

        AI_template = self.state.generation_settings["start"]
        # print(AI_template.startswith('\\n'))
        # print(AI_template.endswith(AI_suffix))
        if AI_template.startswith(self.AI_prefix) and AI_template.endswith(self.AI_suffix):
            AI_name = AI_template[len(self.AI_prefix) : -len(self.AI_suffix)]
        else:
            AI_name = ""
        self.AI_name_entry.tk_variables.set(AI_name)
        player_template = self.state.module_settings["input"]["submit_template"]
        # check if player template is in the form f"\\n{player_name}: \{input\}"
        if player_template.startswith(self.player_prefix) and player_template.endswith(self.player_suffix):
            player_name = player_template[len(self.player_prefix) : -len(self.player_suffix)]
        else:
            player_name = ""
        self.player_name_entry.tk_variables.set(player_name)

    def apply(self):
        AI_name = self.AI_prefix + self.AI_name_entry.tk_variables.get() + self.AI_suffix
        self.state.update_frame(self.state.selected_node, update={"generation_settings": {"start": AI_name}})
        player_name = self.player_name_entry.tk_variables.get()
        player_submit_template = self.player_prefix + player_name + self.player_suffix
        self.state.update_frame(
            self.state.selected_node, update={"module_settings": {"input": {"submit_template": player_submit_template}}}
        )


class AddModelDialog(Dialog):
    def __init__(self, parent):
        self.model_name_entry = None
        self.model_type_entry = None
        Dialog.__init__(self, parent, title="Model Configuration")

    def body(self, master):
        self.model_name_entry = Entry(master, master.grid_size()[1], "Model name", "", None, width=30)
        self.model_type_entry = Entry(master, master.grid_size()[1], "Model type", "openai-custom", None, width=30)

    def apply(self):
        self.result = {
            "name": self.model_name_entry.tk_variables.get(),
            "type": self.model_type_entry.tk_variables.get(),
        }


class ModelConfigDialog(Dialog):
    def __init__(self, parent, state):
        self.state = state
        self.available_models = None
        self.available_models_dropdown = None
        self.model_label = None
        self.selected_model = tk.StringVar()
        self.add_model_button = None
        self.openai_api_key_entry = None
        self.openai_api_key = None
        self.ai21_api_key_entry = None
        self.ai21_api_key = None
        self.gooseai_api_key = None
        self.gooseai_api_key_entry = None
        Dialog.__init__(self, parent, title="Model Configuration")

    def set_vars(self):
        self.available_models = self.state.model_config["models"]
        self.selected_model.set(self.state.generation_settings["model"])
        self.openai_api_key = self.state.OPENAI_API_KEY if self.state.OPENAI_API_KEY else ""
        self.ai21_api_key = self.state.AI21_API_KEY if self.state.AI21_API_KEY else ""
        self.gooseai_api_key = self.state.GOOSEAI_API_KEY if self.state.GOOSEAI_API_KEY else ""

    def body(self, master):
        self.set_vars()
        self.add_model_button = ttk.Button(master, text="Add Model", command=self.add_model)
        key_length = max(max(len(self.openai_api_key), len(self.ai21_api_key), len(self.gooseai_api_key)), 20)
        self.openai_api_key_entry = Entry(
            master, master.grid_size()[1], "OpenAI API Key", self.openai_api_key, None, width=key_length
        )
        self.ai21_api_key_entry = Entry(
            master, master.grid_size()[1], "AI21 API Key", self.ai21_api_key, None, width=key_length
        )
        self.gooseai_api_key_entry = Entry(
            master, master.grid_size()[1], "GooseAI API Key", self.gooseai_api_key, None, width=key_length
        )
        models_list = self.available_models.keys()
        self.model_label = ttk.Label(master, text="Model")
        self.model_label.grid(row=master.grid_size()[1], column=0)
        self.available_models_dropdown = tk.OptionMenu(master, self.selected_model, *models_list)
        self.available_models_dropdown.config(width=20)
        self.available_models_dropdown.grid(row=master.grid_size()[1] - 1, column=1)
        self.add_model_button.grid(row=master.grid_size()[1], column=0)

    def add_model(self):
        self.result = AddModelDialog(self).result
        if self.result:
            self.available_models[self.result["name"]] = {"type": self.result["type"]}
            self.available_models_dropdown["menu"].add_command(
                label=self.result["name"], command=lambda: self.selected_model.set(self.result["name"])
            )

    def apply(self):
        self.state.update_frame(node=self.state.root(), update={"model_config": {"models": self.available_models}})
        #'OPENAI_API_KEY': self.openai_api_key_entry.tk_variables.get(),
        #'AI21_API_KEY': self.ai21_api_key_entry.tk_variables.get(),
        self.state.OPENAI_API_KEY = self.openai_api_key_entry.tk_variables.get().strip()
        self.state.AI21_API_KEY = self.ai21_api_key_entry.tk_variables.get().strip()
        self.state.GOOSEAI_API_KEY = self.gooseai_api_key_entry.tk_variables.get().strip()
        self.state.update_user_frame(update={"generation_settings": {"model": self.selected_model.get()}})
