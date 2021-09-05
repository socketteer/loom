import tkinter as tk
from tkinter import ttk
from view.colors import text_color, bg_color, edit_color, default_color
from util.custom_tks import TextAware
from tkinter.scrolledtext import ScrolledText
from view.styles import textbox_config


def run_init(self, init_text):
    self.code_textbox = None
    self.label = None
    self.init_text = init_text

def run_body(self, master):
    self.label = tk.Label(master, text='**** HUMANS ONLY ****', bg=default_color(), fg=text_color())
    self.label.pack(side=tk.TOP, fill=tk.X)
    self.code_textbox = ScrolledText(master, height=2)
    self.code_textbox.pack(fill=tk.BOTH, expand=True)
    self.code_textbox.configure(**textbox_config(bg='black', font='Monaco'))
    self.code_textbox.insert(tk.INSERT, self.init_text)
    self.code_textbox.focus()

def run_apply(self):
    code = self.code_textbox.get("1.0", 'end-1c')
    self.callbacks["Run"]["prev_cmd"] = code
    self.callbacks["Eval"]["callback"](code_string=code)