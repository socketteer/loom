import os
import tkinter as tk
from tkinter import TclError, filedialog, ttk
from tkinter.font import Font
from tkinter.scrolledtext import ScrolledText

from gpt import POSSIBLE_MODELS
from util.custom_tks import Dialog
from util.util_tk import create_side_label, create_label, Entry, create_button, create_slider, create_combo_box
from view.colors import default_color, text_color, bg_color, PROB_1, PROB_2, PROB_3, PROB_4, PROB_5, PROB_6
import math

class InfoDialog(Dialog):
    def __init__(self, parent, data_dict):
        self.data_dict = data_dict
        Dialog.__init__(self, parent, title="Information", cancellable=False)

    def body(self, master):
        for label_text, data_text in self.data_dict.items():
            create_side_label(master, label_text)
            create_label(master, data_text, row=master.grid_size()[1]-1, col=1, padx=15)


class NodeInfoDialog(Dialog):
    def __init__(self, parent, node):
        self.node = node
        Dialog.__init__(self, parent, title="Node Metadata", cancellable=False)

    def body(self, master):
        if "meta" in self.node:
            meta = self.node["meta"]
            create_side_label(master, "origin")
            if "origin" in meta:
                create_label(master, meta["origin"], row=master.grid_size()[1] - 1, col=1, padx=15)
            else:
                create_label(master, "unknown", row=master.grid_size()[1] - 1, col=1, padx=15)

            if "generation" in meta:
                create_side_label(master, "prompt")
                prompt_text = tk.Text(master)
                prompt_text.grid(row=master.grid_size()[1] - 1, column=1)
                prompt_text.insert(tk.INSERT, meta["generation"]["prompt"])
                prompt_text.configure(state='disabled')
                # makes text copyable
                prompt_text.bind("<Button>", lambda event: prompt_text.focus_set())

                create_side_label(master, "original generated text")
                gen_text = tk.Text(master)
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
                    index_offset = position - len(meta["generation"]["prompt"])
                    token_length = len(meta["generation"]["logprobs"]["tokens"][i])
                    if prob >= 0.8:
                        gen_text.tag_add("prob_1", f"1.0 + {index_offset} chars",
                                         f"1.0 + {index_offset + token_length} chars")
                    elif prob >= 0.6:
                        gen_text.tag_add("prob_2", f"1.0 + {index_offset} chars",
                                         f"1.0 + {index_offset + token_length} chars")
                    elif prob >= 0.4:
                        gen_text.tag_add("prob_3", f"1.0 + {index_offset} chars",
                                         f"1.0 + {index_offset + token_length} chars")
                    elif prob >= 0.2:
                        gen_text.tag_add("prob_4", f"1.0 + {index_offset} chars",
                                         f"1.0 + {index_offset + token_length} chars")
                    elif prob >= 0.05:
                        gen_text.tag_add("prob_5", f"1.0 + {index_offset} chars",
                                         f"1.0 + {index_offset + token_length} chars")
                    else:
                        gen_text.tag_add("prob_6", f"1.0 + {index_offset} chars",
                                         f"1.0 + {index_offset + token_length} chars")

                gen_text.configure(state='disabled')

                # makes text copyable
                gen_text.bind("<Button>", lambda event: gen_text.focus_set())
                create_side_label(master, "model")
                create_label(master, meta["generation"]["model"], row=master.grid_size()[1] - 1, col=1, padx=15)



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


class MemoryDialog(Dialog):
    def __init__(self, parent, node, get_memory):
        self.node = node
        self.memory_textbox = None
        self.get_memory = get_memory
        Dialog.__init__(self, parent, title="Memory")

    def body(self, master):
        create_label(master, "Memory (prepended to AI input)")
        self.memory_textbox = ScrolledText(master, height=7)
        self.memory_textbox.grid(row=master.grid_size()[1], column=0, columnspan=2)
        self.memory_textbox.configure(
            font=Font(family="Georgia", size=12),  # Other nice options: Helvetica, Arial, Georgia
            spacing1=10,
            foreground=text_color(),  # Darkmode
            background=bg_color(),
            padx=3,
            pady=3,
            spacing2=5,  # Spacing between lines
            spacing3=5,
            wrap="word",
        )
        self.memory_textbox.insert("1.0", self.get_memory(self.node))

    def apply(self):
        self.node["memory"] = self.memory_textbox.get("1.0", 'end-1c')


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
        self.memory_textbox = None

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

        create_label(master, "Memory")
        self.memory_textbox = ScrolledText(master, height=7)
        self.memory_textbox.grid(row=master.grid_size()[1], column=0, columnspan=2)
        self.memory_textbox.configure(
            font=Font(family="Georgia", size=12),  # Other nice options: Helvetica, Arial, Georgia
            spacing1=10,
            foreground=text_color(),  # Darkmode
            background=bg_color(),
            padx=3,
            pady=3,
            spacing2=5,  # Spacing between lines
            spacing3=5,
            wrap="word",
        )
        self.memory_textbox.insert("1.0", self.orig_params["memory"])

        create_button(master, "Reset", self.reset_variables)


    # Reset all sliders to 50
    def reset_variables(self):
        for key, var in self.vars.items():
            var.set(self.orig_params[key])
        self.memory_textbox.delete("1.0", "end")
        self.memory_textbox.insert("1.0", self.orig_params["memory"])


    # Put the slider values into the result field
    def apply(self):
        for key, var in self.vars.items():
            self.orig_params[key] = var.get()
        self.orig_params["memory"] = self.memory_textbox.get("1.0", 'end-1c')
        self.result = self.orig_params


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

        for name in ['horizontal', 'displaytext', 'showbuttons']:
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
