import os
import tkinter as tk
from tkinter import TclError, filedialog, ttk
from tkinter.font import Font
from tkinter.scrolledtext import ScrolledText

from gpt import POSSIBLE_MODELS
from util.custom_tks import Dialog, TextAware
from util.util_tk import create_side_label, create_label, Entry, create_button, create_slider, create_combo_box
from util.util_tree import search
from view.colors import default_color, text_color, bg_color, PROB_1, PROB_2, PROB_3, PROB_4, PROB_5, PROB_6
import math


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

        create_side_label(master, "bookmarked")
        create_label(master, "true" if self.node.get("bookmark", False) else "false", row=master.grid_size()[1] - 1,
                     col=1, padx=15)

        create_side_label(master, "visited")
        create_label(master, "true" if self.node.get("visited", False) else "false", row=master.grid_size()[1] - 1,
                     col=1, padx=15)

        create_side_label(master, "canonical")
        create_label(master, "true" if self.node["id"] in self.state.calc_canonical_set() else "false",
                     row=master.grid_size()[1] - 1, col=1, padx=15)

        if "meta" in self.node:
            meta = self.node["meta"]
            create_side_label(master, "origin")
            if "origin" in meta:
                create_label(master, meta["origin"], row=master.grid_size()[1] - 1, col=1, padx=15)
            else:
                create_label(master, "unknown", row=master.grid_size()[1] - 1, col=1, padx=15)

            if "generation" in meta:
                create_side_label(master, "prompt")
                prompt_text = tk.Text(master, height=15)
                prompt_text.grid(row=master.grid_size()[1] - 1, column=1)
                prompt_text.insert(tk.INSERT, meta["generation"]["prompt"])
                prompt_text.configure(
                    state='disabled',
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
                gen_text.insert(tk.INSERT, meta["generation"]["text"])

                gen_text.tag_config("prob_1", background=PROB_1)
                gen_text.tag_config("prob_2", background=PROB_2)
                gen_text.tag_config("prob_3", background=PROB_3)
                gen_text.tag_config("prob_4", background=PROB_4)
                gen_text.tag_config("prob_5", background=PROB_5)
                gen_text.tag_config("prob_6", background=PROB_6)



                # TODO continuous coloration
                for i, position in enumerate(meta["generation"]["logprobs"]["text_offset"]):
                    prob = math.exp(meta["generation"]["logprobs"]["token_logprobs"][i])
                    #index_offset = position - len(meta["generation"]["prompt"])
                    token_length = len(meta["generation"]["logprobs"]["tokens"][i])
                    if prob >= 0.8:
                        gen_text.tag_add("prob_1", f"1.0 + {position} chars",
                                         f"1.0 + {position + token_length} chars")
                    elif prob >= 0.6:
                        gen_text.tag_add("prob_2", f"1.0 + {position} chars",
                                         f"1.0 + {position + token_length} chars")
                    elif prob >= 0.4:
                        gen_text.tag_add("prob_3", f"1.0 + {position} chars",
                                         f"1.0 + {position + token_length} chars")
                    elif prob >= 0.2:
                        gen_text.tag_add("prob_4", f"1.0 + {position} chars",
                                         f"1.0 + {position + token_length} chars")
                    elif prob >= 0.05:
                        gen_text.tag_add("prob_5", f"1.0 + {position} chars",
                                         f"1.0 + {position + token_length} chars")
                    else:
                        gen_text.tag_add("prob_6", f"1.0 + {position} chars",
                                         f"1.0 + {position + token_length} chars")

                gen_text.configure(state='disabled')
                # gen_text.configure(
                #     state='disabled',
                #     font=readable_font,
                #     spacing1=10,
                #     foreground=text_color(),
                #     background=bg_color(),
                #     wrap="word",
                # )

                # makes text copyable
                gen_text.bind("<Button>", lambda event: gen_text.focus_set())
                create_side_label(master, "model")
                create_label(master, meta["generation"]["model"], row=master.grid_size()[1] - 1, col=1, padx=15)


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
        #self.master.bind('<Return>', lambda event=None: self.search)

    def search(self):
        search_term = self.search_entry.tk_variables.get()
        if not search_term:
            print('not')
            return
        depth_limit = self.depth_limit.tk_variables.get()
        if not depth_limit:
            depth_limit = None
        else:
            depth_limit = int(depth_limit)
        root = self.state.selected_node if self.subtree.get() else self.state.tree_raw_data["root"]
        print('case sensitive: ', self.case_sensitive.get())
        matches = search(root=root,
                         pattern=search_term,
                         text=self.text.get(),
                         tags=self.tags.get(),
                         case_sensitive=self.case_sensitive.get(),
                         regex=self.regex.get(),
                         filter_set=self.state.calc_canonical_set() if self.canonical.get() else None,
                         max_depth=depth_limit)

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
        self.num_results_label = create_side_label(self.master, f'{len(matches)} results')
        for i, match in enumerate(matches[start:]):
            if counter >= limit:
                break
            node = self.state.tree_node_dict[match['node_id']]
            self.labels.append(create_side_label(self.master,
                                                 f"chapter: {self.state.chapter(node)['title']}"))
            #side_label.config(fg="blue")
            self.results.append(TextAware(self.master, height=2))
            #readable_font = Font(family="Georgia", size=12)
            self.results[i].configure(
                #font=readable_font,
                spacing1=8,
                foreground=text_color(),
                background=bg_color(),
                wrap="word",
            )
            self.results[i].grid(row=self.master.grid_size()[1] - 1, column=1)
            node_text = node["text"]
            start_index = max(0, match['span'][0] - context_padding)
            end_index = min(len(node_text), match['span'][1] + context_padding)
            text_window = node_text[start_index:end_index]
            self.results[i].insert(tk.INSERT, text_window)
            self.results[i].tag_configure("blue", background="blue")
            self.results[i].highlight_pattern(match['match'], "blue")
            self.results[i].configure(state='disabled')

            # makes text copyable
            # binding causes computer to freeze
            #self.results[i].bind("<Button>", lambda event, _result=self.results[i]: result.focus_set())
            #matched_text.bind("<Alt-Button-1>", lambda event: self.goto_result(match['node_id']))

            self.goto_buttons.append(create_button(self.master, "go to match",
                                                   lambda _match=match: self.goto_result(_match['node_id'])))
            self.goto_buttons[i].grid(row=self.master.grid_size()[1] - 2, column=2)
            counter += 1
        if start > 0:
            self.prev_page_button = create_button(self.master, "previous page",
                                                  lambda _start=start, _limit=limit: self.search_results(matches, start=_start-_limit))
            self.prev_page_button.config(width=12)
        if len(matches) > start + limit:
            self.next_page_button = create_button(self.master, "next page",
                                                  lambda _start=start, _limit=limit: self.search_results(matches, start=_start+_limit))

    def goto_result(self, id):
        self.ok()
        self.goto(node_id=id)


class ChaptersInfoDialog(Dialog):
    def __init__(self, parent, data_dict):
        self.data_dict = data_dict
        Dialog.__init__(self, parent, title="Chapters")

    def body(self, master):
        for iid, chapter in self.data_dict.items():
            create_side_label(master, chapter['title'])
            create_label(master, 'is a chapter', row=master.grid_size()[1]-1, col=1, padx=15)


class NodeChapterDialog(Dialog):
    def __init__(self, parent, node, state):
        self.node = node
        self.new_chapter_title = None
        self.state = state
        Dialog.__init__(self, parent, title="Chapter")

    def body(self, master):
        create_side_label(master, 'Current Chapter')
        chapter_name = "None" if 'chapter_id' not in self.node else self.state.chapter_title(self.node)
        create_label(master, chapter_name, row=master.grid_size()[1] - 1, col=1, padx=15)
        self.new_chapter_title = Entry(master, master.grid_size()[1], "Enter new chapter title", "", None)
        self.new_chapter_title.controls.focus_set()

    def apply(self):
        new_title = self.new_chapter_title.tk_variables.get()
        self.state.create_new_chapter(node=self.node, title=new_title)


class AIMemory(Dialog):
    def __init__(self, parent, node, state):
        self.node = node
        self.state = state
        self.memories = []
        self.checks = []
        self.edit_buttons = []
        self.master = None
        self.new_button = None
        Dialog.__init__(self, parent, title="AI Memory")

    def body(self, master):
        create_label(master, "Memory (prepended to AI input)")
        self.master = master
        self.refresh()


    def refresh(self):
        if self.new_button:
            self.new_button.destroy()
        for memory in self.memories:
            memory.destroy()
        for check in self.checks:
            check.destroy()
        for edit_button in self.edit_buttons:
            edit_button.destroy()
        self.memories = []
        self.checks = []
        self.edit_buttons = []

        for i, memory in enumerate(self.state.construct_memory(self.node)):
            if memory['text']:
                temp_check = tk.BooleanVar()
                temp_check.set(True)
                row = self.master.grid_size()[1]
                self.memories.append(TextAware(self.master, height=1))
                self.memories[i].grid(row=row, column=0, columnspan=2, padx=5)
                self.memories[i].insert(tk.INSERT, memory['text'])
                self.memories[i].configure(
                    state='disabled',
                    foreground=text_color(),
                    background=bg_color(),
                    wrap="word",
                )
                # FIXME checks are unchecked by default
                self.checks.append(tk.Checkbutton(self.master, variable=temp_check))
                self.checks[i].grid(row=row, column=2, padx=3)
                self.edit_buttons.append(create_button(self.master, "Edit", lambda _memory=memory: self.edit_memory(_memory), width=4))
                self.edit_buttons[i].grid(row=row, column=3)
        self.new_button = create_button(self.master, "Add memory", self.create_new, width=11)


    def create_new(self):
        dialog = CreateMemory(parent=self.parent, node=self.node, state=self.state, default_inheritability='subtree')
        self.refresh()

    def edit_memory(self, memory):
        dialog = EditMemory(parent=self.parent, memory=memory, state=self.state)
        self.refresh()

    def apply(self):
        pass


class NodeMemory(Dialog):
    def __init__(self, parent, node, state):
        self.node = node
        self.state = state
        self.memories = []
        self.master = None
        self.new_button = None
        self.edit_buttons = []
        Dialog.__init__(self, parent, title="Node Memory")

    def body(self, master):
        create_label(master, "Memory entries associated with this node")
        self.master = master
        self.refresh()

    def refresh(self):
        if self.new_button:
            self.new_button.destroy()
        for memory in self.memories:
            memory.destroy()
        for edit_button in self.edit_buttons:
            edit_button.destroy()
        self.memories = []
        self.checks = []
        self.edit_buttons = []

        if 'memories' in self.node:
            for i, memory_id in enumerate(self.node['memories']):
                memory = self.state.memories[memory_id]
                if memory['text']:
                    row = self.master.grid_size()[1]
                    self.memories.append(TextAware(self.master, height=1))
                    self.memories[i].grid(row=row, column=0, columnspan=2, padx=5)
                    self.memories[i].insert(tk.INSERT, memory['text'])
                    self.memories[i].configure(
                        state='disabled',
                        foreground=text_color(),
                        background=bg_color(),
                        wrap="word",
                    )
                    self.edit_buttons.append(create_button(self.master, "Edit", lambda _memory=memory: self.edit_memory(_memory), width=4))
                    self.edit_buttons[i].grid(row=row, column=3)
        self.new_button = create_button(self.master, "Add memory", self.create_new, width=11)


    def create_new(self):
        dialog = CreateMemory(parent=self.parent, node=self.node, state=self.state, default_inheritability='subtree')
        self.refresh()

    def edit_memory(self, memory):
        dialog = EditMemory(parent=self.parent, memory=memory, state=self.state)
        self.refresh()

    def apply(self):
        pass


class CreateMemory(Dialog):
    def __init__(self, parent, node, state, default_inheritability='delayed'):
        self.node = node
        self.state = state
        self.inheritability = tk.StringVar()
        self.default_inheritability = default_inheritability
        self.memory_textbox = None
        Dialog.__init__(self, parent, title="Add memory entry", enter_to_apply=False)

    def body(self, master):
        self.memory_textbox = ScrolledText(master, height=3)
        self.memory_textbox.grid(row=master.grid_size()[1], column=0, columnspan=2)
        self.memory_textbox.configure(
            font=Font(family="Georgia", size=12),  # Other nice options: Helvetica, Arial, Georgia
            spacing1=10,
            foreground=text_color(),
            background=bg_color(),
            padx=3,
            pady=3,
            spacing2=3,  # Spacing between lines
            spacing3=5,
            wrap="word",
        )
        self.memory_textbox.focus()
        row = master.grid_size()[1]
        create_side_label(master, "Inheritability", row)
        inheritability_options = ('none', 'subtree', 'delayed')
        self.inheritability.set(self.default_inheritability)
        dropdown = tk.OptionMenu(master, self.inheritability, *inheritability_options)
        dropdown.grid(row=row, column=1, pady=3)

    def apply(self):
        memory_text = self.memory_textbox.get("1.0", 'end-1c')
        if memory_text:
            self.state.create_memory_entry(self.node, memory_text, self.inheritability.get())


class EditMemory(Dialog):
    def __init__(self, parent, memory, state):
        self.memory = memory
        self.state = state
        self.inheritability = tk.StringVar()
        self.delete_button = None
        self.memory_textbox = None
        Dialog.__init__(self, parent, title="Edit memory entry", enter_to_apply=False)

    def body(self, master):
        self.memory_textbox = ScrolledText(master, height=3)
        self.memory_textbox.grid(row=master.grid_size()[1], column=0, columnspan=2)
        self.memory_textbox.configure(
            font=Font(family="Georgia", size=12),  # Other nice options: Helvetica, Arial, Georgia
            spacing1=10,
            foreground=text_color(),
            background=bg_color(),
            padx=3,
            pady=3,
            spacing2=3,  # Spacing between lines
            spacing3=5,
            wrap="word",
        )
        self.memory_textbox.insert(tk.INSERT, self.memory['text'])
        self.memory_textbox.focus()
        row = master.grid_size()[1]
        create_side_label(master, "Inheritability", row)
        inheritability_options = ('none', 'subtree', 'delayed')
        self.inheritability.set(self.memory['inheritability'])
        dropdown = tk.OptionMenu(master, self.inheritability, *inheritability_options)
        dropdown.grid(row=row, column=1, pady=3)
        self.delete_button = create_button(master, "Delete memory", self.delete_memory, width=15)

    def delete_memory(self):
        self.state.delete_memory_entry(self.memory)
        self.cancel()

    def apply(self):
        memory_text = self.memory_textbox.get("1.0", 'end-1c')
        self.memory['text'] = memory_text
        self.memory['inheritability'] = self.inheritability.get()


class PreferencesDialog(Dialog):
    def __init__(self, parent, orig_params):
        #print(orig_params)
        self.orig_params = orig_params
        self.vars = {
            "canonical_only": tk.BooleanVar,
            "side_pane": tk.BooleanVar,
            "bold_prompt": tk.BooleanVar,
            "input_box": tk.BooleanVar,
            "auto_response": tk.BooleanVar,
            "coloring": tk.StringVar,
            "gpt_mode": tk.StringVar,
            "font_size": tk.IntVar,
            "line_spacing": tk.IntVar,
            "paragraph_spacing": tk.IntVar
        }
        for key in self.vars.keys():
            self.vars[key] = self.vars[key](value=orig_params[key])

        Dialog.__init__(self, parent, title="Preferences")

    def body(self, master):
        #print(self.orig_params)
        row = master.grid_size()[1]
        create_side_label(master, "Canonical only", row)
        check = ttk.Checkbutton(master, variable=self.vars["canonical_only"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Show side pane", row)
        check = ttk.Checkbutton(master, variable=self.vars["side_pane"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Bold prompt", row)
        check = ttk.Checkbutton(master, variable=self.vars["bold_prompt"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Show input box", row)
        check = ttk.Checkbutton(master, variable=self.vars["input_box"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "AI responses on submit", row)
        check = ttk.Checkbutton(master, variable=self.vars["auto_response"])
        check.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "Text coloring", row)
        options = ['edit', 'read', 'none']
        dropdown = tk.OptionMenu(master, self.vars["coloring"], *options)
        dropdown.grid(row=row, column=1, pady=3)
        row = master.grid_size()[1]
        create_side_label(master, "AI mode", row)
        options = ['default', 'chat', 'dialogue', 'antisummary']
        dropdown = tk.OptionMenu(master, self.vars["gpt_mode"], *options)
        dropdown.grid(row=row, column=1, pady=3)
        create_slider(master, "Font size", self.vars["font_size"], (5, 20))
        create_slider(master, "Line spacing", self.vars["line_spacing"], (0, 20))
        create_slider(master, "Paragraph spacing", self.vars["paragraph_spacing"], (0, 40))

    def apply(self):
        for key, var in self.vars.items():
            self.orig_params[key] = var.get()

class GenerationSettingsDialog(Dialog):
    def __init__(self, parent, orig_params):
        self.orig_params = orig_params
        self.vars = {
            'num_continuations': tk.IntVar,
            'temperature': tk.DoubleVar,
            'top_p': tk.DoubleVar,
            'response_length': tk.IntVar,
            'prompt_length': tk.IntVar,
            "janus": tk.BooleanVar,
            "adaptive": tk.BooleanVar,
            "model": tk.StringVar,
        }
        for key in self.vars.keys():
            self.vars[key] = self.vars[key](value=orig_params[key])
        #self.memory_textbox = None

        Dialog.__init__(self, parent, title="Generation Settings")

    # Creates sliders for each sensitivity slider
    def body(self, master):
        sliders = {
            'num_continuations': (1, 20),
            'temperature': (0., 1.),
            'top_p': (0., 1.),
            'response_length': (1, 1000),
            'prompt_length': (100, 10000),
        }
        for name, value_range in sliders.items():
            create_slider(master, name, self.vars[name], value_range)


        row = master.grid_size()[1]
        create_side_label(master, "Use Janus?", row)
        check = ttk.Checkbutton(master, variable=self.vars["janus"])
        check.grid(row=row, column=1, pady=3)
        create_side_label(master, "Adaptive branching", row+1)
        check2 = ttk.Checkbutton(master, variable=self.vars["adaptive"])
        check2.grid(row=row+1, column=1, pady=3)

        create_combo_box(master, "Model", self.vars["model"], POSSIBLE_MODELS, width=20)

        # create_label(master, "Memory")
        # self.memory_textbox = ScrolledText(master, height=7)
        # self.memory_textbox.grid(row=master.grid_size()[1], column=0, columnspan=2)
        # self.memory_textbox.configure(
        #     font=Font(family="Georgia", size=12),  # Other nice options: Helvetica, Arial, Georgia
        #     spacing1=10,
        #     foreground=text_color(),  # Darkmode
        #     background=bg_color(),
        #     padx=3,
        #     pady=3,
        #     spacing2=5,  # Spacing between lines
        #     spacing3=5,
        #     wrap="word",
        # )
        # self.memory_textbox.insert("1.0", self.orig_params["memory"])

        create_button(master, "Reset", self.reset_variables)


    # Reset all sliders to 50
    def reset_variables(self):
        for key, var in self.vars.items():
            var.set(self.orig_params[key])
        #self.memory_textbox.delete("1.0", "end")
        #self.memory_textbox.insert("1.0", self.orig_params["memory"])


    # Put the slider values into the result field
    def apply(self):
        for key, var in self.vars.items():
            self.orig_params[key] = var.get()
        #self.orig_params["memory"] = self.memory_textbox.get("1.0", 'end-1c')
        self.result = self.orig_params


class ChatSettingsDialog(Dialog):
    def __init__(self, parent, orig_params):
        # print(orig_params)
        self.orig_params = orig_params
        self.AI_name_textbox = None
        self.player_name_textbox = None
        self.context_textbox = None
        self.preset = tk.StringVar
        self.vars = {
            'AI_name': tk.StringVar,
            'player_name': tk.StringVar,
            'context': tk.StringVar,
        }
        for key in self.vars.keys():
            self.vars[key] = self.vars[key](value=orig_params[key])

        Dialog.__init__(self, parent, title="Preferences")

    def body(self, master):
        # print(self.orig_params)
        self.master = master
        row = master.grid_size()[1]
        create_side_label(master, "AI name", row)
        self.AI_name_textbox = TextAware(self.master, height=1)
        self.AI_name_textbox.insert(tk.INSERT, self.vars['AI_name'].get())
        self.AI_name_textbox.grid(row=row, column=1)
        row = master.grid_size()[1]
        create_side_label(master, "Player name", row)
        self.player_name_textbox = TextAware(self.master, height=1)
        self.player_name_textbox.insert(tk.INSERT, self.vars['player_name'].get())
        self.player_name_textbox.grid(row=row, column=1)
        row = master.grid_size()[1]

        create_side_label(master, "Context (prepended to AI input)", row)
        self.context_textbox = TextAware(self.master, height=4)
        self.context_textbox.insert(tk.INSERT, self.vars['context'].get())
        self.context_textbox.grid(row=row, column=1)

        row = master.grid_size()[1]
        create_side_label(master, "Use preset", row)

        # TODO load json
        options = ['GPT-3/researcher', 'chatroulette']
        #self.preset.set(options[0])
        dropdown = tk.OptionMenu(master, self.preset, *options)
        dropdown.grid(row=row, column=1, pady=3)
        button = create_button(master, "Apply", self.apply_preset)
        button.grid(row=row, column=2, sticky='w')

    def apply_preset(self):
        pass

    # TODO save as preset

    def apply(self):
        self.orig_params['AI_name'] = self.AI_name_textbox.get("1.0", 'end-1c')
        self.orig_params['player_name'] = self.player_name_textbox.get("1.0", 'end-1c')
        self.orig_params['context'] = self.context_textbox.get("1.0", 'end-1c')


class VisualizationSettingsDialog(Dialog):
    def __init__(self, parent, orig_params):
        self.orig_params = orig_params
        self.vars = {
            'textwidth': tk.IntVar,
            'leafdist': tk.IntVar,
            'leveldistance': tk.IntVar,
            'textsize': tk.IntVar,
            'horizontal': tk.BooleanVar,
            'displaytext': tk.BooleanVar,
            'showbuttons': tk.BooleanVar,
            'chaptermode': tk.BooleanVar,
        }
        for key in self.vars.keys():
            self.vars[key] = self.vars[key](value=orig_params[key])

        Dialog.__init__(self, parent, title="Visualization Settings")

    # Creates sliders for each sensitivity slider
    def body(self, master):
        sliders = {
            'textwidth': (10, 1000),
            'leafdist': (1, 500),
            'leveldistance': (1, 500),
            'textsize': (1, 25),
        }
        for name, value_range in sliders.items():
            create_slider(master, name, self.vars[name], value_range)

        for name in ['horizontal', 'displaytext', 'showbuttons', 'chaptermode']:
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
    def __init__(self, parent, node, refresh_event):
        self.node = node
        self.img = None
        self.caption = None
        self.viewing = None
        self.master = None
        self.next_button = None
        self.prev_button = None
        self.move_up_button = None
        self.move_down_button = None
        self.delete_button = None
        self.caption_button = None
        self.n = 0
        self.refresh_event = refresh_event
        Dialog.__init__(self, parent, title="Multimedia")

    def body(self, master):
        self.master = master
        button = create_button(master, "Add media", self.add_media)
        button.grid(row=1, column=1, sticky='w')
        #if self.num_media() > 0:
        #img, caption = self.display_image()
        self.create_image()
        self.display_image()
        self.create_buttons()
        self.set_buttons()

    def num_media(self):
        if 'multimedia' in self.node:
            return len(self.node['multimedia'])
        else:
            return 0

    def create_image(self):
        img = tk.PhotoImage(file='static/media/black.png')
        self.img = tk.Label(self.master, image=img, bg=default_color())
        self.img.grid(row=2, column=1)
        # self.img.image.blank()
        # self.img.image = None
        self.caption = tk.Label(self.master, text='', bg=default_color())
        self.caption.grid(row=4, column=1)
        self.viewing = tk.Label(self.master, text=f"{self.n + 1} / {self.num_media()}", bg=default_color())
        self.viewing.grid(row=3, column=1)

    def create_buttons(self):
        self.next_button = create_button(self.master, "Next", lambda: self.traverse(1))
        self.next_button.grid(row=4, column=1, sticky='e')
        self.prev_button = create_button(self.master, "Prev", lambda: self.traverse(-1))
        self.prev_button.grid(row=4, column=1, sticky='w')
        self.move_up_button = create_button(self.master, "Move >", lambda: self.shift(1))
        self.move_up_button.grid(row=5, column=1, sticky='e')
        self.move_down_button = create_button(self.master, "< Move", lambda: self.shift(-1))
        self.move_down_button.grid(row=5, column=1, sticky='w')
        self.caption_button = create_button(self.master, "Change caption", self.change_caption)
        self.caption_button.grid(row=5, column=1)
        self.caption_button.config(width=15)
        self.delete_button = create_button(self.master, "Delete", self.delete_media)
        self.delete_button.grid(row=1, column=1, sticky='e')

    def set_buttons(self):
        if not self.next_button:
            self.create_buttons()
        if self.num_media() > 0:
            self.next_button["state"] = "normal"
            self.prev_button["state"] = "normal"
            self.move_up_button["state"] = "normal"
            self.move_down_button["state"] = "normal"
            self.delete_button["state"] = "normal"
            self.caption_button["state"] = "normal"
        else:
            self.next_button["state"] = "disabled"
            self.prev_button["state"] = "disabled"
            self.move_up_button["state"] = "disabled"
            self.move_down_button["state"] = "disabled"
            self.delete_button["state"] = "disabled"
            self.caption_button["state"] = "disabled"

    def change_caption(self):
        if self.num_media() > 0:
            self.node['multimedia'][self.n]['caption'] = 'new caption'
            self.display_image()

    def repair_type(self):
        if self.num_media() > 0:
            new_multimedia = []
            for media in self.node['multimedia']:
                if isinstance(media, str):
                    new_multimedia.append({'file': media, 'caption': ''})
                elif isinstance(media, dict):
                    new_multimedia.append(media)
                else:
                    print('error invalid type')
            self.node['multimedia'] = new_multimedia

    def display_image(self):
        if not self.img:
            self.create_image()
        if self.num_media() > 0:
            try:
                self.repair_type()
                img = tk.PhotoImage(file=self.node['multimedia'][self.n]['file'])
                caption = self.node['multimedia'][self.n]['caption']
            except TclError:
                return
            self.img.configure(image=img)
            self.img.image = img
            self.caption.configure(text=caption)
            self.viewing.configure(text=f"{self.n + 1} / {self.num_media()}")
        else:
            try:
                self.img.image.blank()
                self.img.image = None
                self.caption.configure(text='')
            except AttributeError:
                return

    def add_media(self):
        options = {
            'initialdir': os.getcwd() + '/static/media'
        }
        filenames = filedialog.askopenfilenames(**options)
        if not filenames:
            return
        if 'multimedia' not in self.node:
            self.node['multimedia'] = []
        for filename in filenames:
            self.node['multimedia'].append({'file': filename, 'caption': ''})
        self.n = self.num_media() - 1
        self.display_image()
        self.set_buttons()
        self.refresh_event()

    def delete_media(self):
        del self.node['multimedia'][self.n]
        if self.n != 0:
            self.n -= 1
        self.display_image()
        self.set_buttons()
        self.refresh_event()

    def traverse(self, interval):
        self.n = (self.n + interval) % self.num_media()
        self.display_image()
        self.set_buttons()

    def shift(self, interval):
        new_index = (self.n + interval) % self.num_media()
        self.node['multimedia'][self.n], self.node['multimedia'][new_index] = self.node['multimedia'][new_index],\
                                                                              self.node['multimedia'][self.n]
        self.n = new_index
        self.display_image()
        self.set_buttons()
