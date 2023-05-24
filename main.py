#!/usr/bin/env python


import os
import tkinter as tk
import traceback
import argparse
from collections import defaultdict
from pprint import pprint
from tkinter import ttk, messagebox, font

from ttkthemes import ThemedStyle

from controller import Controller
from model import TreeModel, EMPTY_TREE
from util.custom_tks import ClosableNotebook
from util.util import json_open, json_create
from util.util_tk import create_menubar
from view.colors import darkmode
import PIL.Image
import PIL.ImageTk
from copy import deepcopy

class Application:

    # Create the application window
    def __init__(self):
        self.parse_arguments()
        # Create the root
        self.root = tk.Tk()
        self.root.geometry("%dx%d+50+30" % (self.args.width, self.args.height))
        print(4.0 if self.args.high_resolution else self.args.scaling_factor)
        self.root.call('tk', 'scaling', 2.0 if self.args.high_resolution else self.args.scaling_factor)
        self.root.title("Read tree")

        # Use a font that scales with the scaling factor
        fontSize = 12  # base font size before scaling
        scaled_font = font.nametofont("TkDefaultFont")
        scaled_font.configure(size=int(fontSize * self.args.scaling_factor))

        # App icon :). Save or will be garbage collected
        self.icon = PIL.ImageTk.PhotoImage(PIL.Image.open("static/zoneplate.png"))
        self.root.tk.call('wm', 'iconphoto', self.root._w, self.icon)
        # Dark mode
        style = ThemedStyle(self.root)
        if darkmode:
            style.set_theme("black")

        # Create the notebook and add a tab to it
        # self.close_icon = build_notebook_style()
        self.notebook = ClosableNotebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=1)
        self.tabs = []

        # Load app data
        self.app_data_file = os.path.join(os.getcwd(), "data/", ".app_data.json")
        self.app_data = None
        self.initialize_app_state()

        # Bind Button-1 to tab click so tabs can be closed
        self.notebook.bind('<Button-1>', self.tab_click)
        self.notebook.bind()

        # Do final root prep
        self.root.update_idletasks()
        # Put the app into the foreground
        self.root.attributes('-topmost', True)
        self.root.update()
        self.root.attributes('-topmost', False)

    def parse_arguments(self):
        parser = argparse.ArgumentParser(description='Loom Activation Script')

        parser.add_argument('-wd', '--width', default=1200, type=int, help='Window Width')
        parser.add_argument('-ht', '--height', default=675, type=int, help='Window Height')
        parser.add_argument('-sf', '--scaling-factor', default=1.0)
        parser.add_argument('-hr', '--high-resolution', action='store_true', help='hr as in High Resolution')

        self.args = parser.parse_args()

    def initialize_app_state(self):
        try:
            self.app_data = json_open(self.app_data_file)  # if os.path.isfile(self.app_data_file) else {}
            for tab_data in self.app_data["tabs"]:
                self.create_tab(filename=tab_data["filename"])
        except Exception as e:
            print("Failed to load with app data")
            print(str(e))
            print(traceback.format_exc())
            self.app_data = {}

        if len(self.tabs) == 0:
            print("Opening a blank tab")
            self.create_tab()
        self.set_tab_names()


    def update_app_data(self):
        #print('updating app data')
        # for t in self.tabs:
        #     print('filename:', t.state.tree_filename)
        self.set_tab_names()
        self.app_data = {
            "tabs": [
                {"filename": t.state.tree_filename}
                for t in self.tabs
            ]
        }
        json_create(self.app_data_file, self.app_data)


    # Create a tab
    def create_tab(self, filename=None, event=None):
        # if len(self.tabs) > 0:
        #     messagebox.showwarning("Error", "Only use one tab right now. hehe")
        #     return
        tab = Controller(self.root)
        self.tabs.append(tab)
        self.notebook.add(tab.display.frame, text=f"Tab {len(self.tabs)}")
        # Build the menu bar
        self.build_menus()

        tab.state.register_callback(tab.state.io_update, self.update_app_data)
        if filename is not None:
            print("opening", filename)
            tab.state.open_tree(filename)
        else:
            tab.state.load_tree_data(deepcopy(EMPTY_TREE))


    def close_tab(self, event=None, index=None):
        index = self.notebook.index("current") if index is None else index
        self.notebook.forget(index)
        self.tabs.pop(index)
        if len(self.tabs) == 0:
            self.create_tab()


    # If the user clicks a close button, get the tab at that position and close it
    def tab_click(self, event):
        if "close" in event.widget.identify(event.x, event.y):
            index = self.notebook.index(f"@{event.x},{event.y}")
            self.close_tab(index=index)
        self.build_menus()


    def set_tab_names(self):
        for i, t in enumerate(self.tabs):
            name = t.state.name()
            self.notebook.tab(i, text=name)

    # Build the applications menubar
    # TODO Splitting between here and tab is bad. Move this to the tab
    def build_menus(self):
        if hasattr(self, "menu"):
            self.menu.destroy()
        
        menu_list = defaultdict(list, {
            "File": [
                #('New Tab', 'Ctrl+N', '<Control-n>', self.create_tab),
                ('New', None, None, lambda event=None: self.forward_command(Controller.new_tree)),
                ('Open', 'O', None, lambda event=None: self.forward_command(Controller.open_tree)),
                ('Import subtree', 'Ctrl+Shift+O', None, lambda event=None: self.forward_command(Controller.import_tree)),
                ('Save', 'S', None, lambda event=None: self.forward_command(Controller.save_tree)),
                ('Save As...', 'Ctrl+S', '<Control-s>', lambda event=None: self.forward_command(Controller.save_tree_as)),
                ('New tree from node...', None, None,
                 lambda event=None: self.forward_command(Controller.new_from_node)),
                ('Export text', 'Ctrl+Shift+X', '<Control-Shift-KeyPress-X>',
                 lambda event=None: self.forward_command(Controller.export_text)),
                ('Export subtree', 'Ctrl+Alt+X', '<Control-Alt-KeyPress-X>',
                 lambda event=None: self.forward_command(Controller.export_subtree)),
                ('Export simple subtree', None, None,
                 lambda event=None: self.forward_command(Controller.export_simple_subtree)),
                ('Close Tab', None, None, self.close_tab),
                ('Quit', 'Ctrl+Q', '<Control-q>', self.quit_app)
            ]
        })
        for menu, items in self.tabs[self.notebook.index("current")].build_menus().items():
            menu_list[menu].extend(items)
        self.menu = create_menubar(self.root, menu_list)


    # Forward the given command to the current display controller
    def forward_command(self, command):
        if len(self.tabs) == 0:
            messagebox.showwarning("Error", "There is no tree open.")
        else:
            command(self.tabs[self.notebook.index("current")])


    def quit_app(self, event=None):
        self.root.destroy()


    # Let the application run
    def main(self):
        self.root.mainloop()


# Create the display application and run it
if __name__ == "__main__":
    app = Application()
    app.main()
