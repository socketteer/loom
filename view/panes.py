from tkinter import ttk
import tkinter as tk
from view.colors import bg_color, text_color, edit_color
import PIL
from view.icons import Icons

icons = Icons()


class Pane:
    def __init__(self, parent, orient):
        self.pane = None
        self.parent = parent    
        self.orient = orient
        self.panes = []

    def build_pane(self):
        self.pane = ttk.PanedWindow(self.parent, orient=self.orient)

    # def open(self, weight=1):
    #     self.parent.add(self.pane, weight=weight)

    def destroy(self):
        for pane in self.panes:
            pane.destroy()
        self.panes = []
        self.pane.destroy()
        self.pane = None
    
    def add_pane(self, weight=1):
        child_pane = Pane(self.pane, tk.VERTICAL if self.orient == tk.HORIZONTAL else tk.HORIZONTAL)
        child_pane.build_pane()
        self.panes.append(child_pane)
        self.pane.add(child_pane.pane, weight=weight)
        return child_pane


# This is a pane whose parent is a pane
class NestedPane(Pane):
    def __init__(self, name, parent, orient):
        super().__init__(parent, orient)
        self.name = name
        self.x_button = None
        self.menu_frame = None
        self.close_icon = None
        self.module_menu = None
        self.module_selection = tk.StringVar()
        self.module = None
        self.add_module_button = None

    def build_pane(self, weight=1):
        self.pane = ttk.PanedWindow(self.parent, orient=self.orient)
        self.parent.add(self.pane, weight=weight)

    # TODO also destroy callback
    def build_menu_frame(self, options, selection_callback, destroy_callback):
        self.menu_frame = tk.Frame(self.pane, background=bg_color())
        self.menu_frame.pack(side='top', fill='x')

        # make dropdown for selecting a module
        self.module_selection.set('None')
        self.module_menu = tk.OptionMenu(self.menu_frame, self.module_selection, *options)
        self.module_menu.pack(side='left', expand=True, padx=20)
        self.module_selection.trace('w', lambda a, b, c, pane_name=self.name: selection_callback(pane_name=pane_name))
        
        # self.add_module_button = tk.Button(self.menu_frame, text='Add Module', fg=text_color(), bg=bg_color(), cursor='hand2')
        # self.add_module_button.pack(side='left', padx=20)
        # self.add_module_button.bind('<Button-1>', self.add_module())

        self.close_icon = icons.get_icon('x-lightgray')
        self.x_button = tk.Label(self.menu_frame, text='⨯', fg=text_color(), bg=bg_color(), cursor='hand2')
        self.x_button.pack(side='left', padx=20)
        self.x_button.bind('<Button-1>', lambda event, pane_name=self.name: destroy_callback(pane_name=pane_name))



    def destroy(self, *args):
        if self.module_menu:
            self.module_menu.destroy()
        if self.x_button:
            self.x_button.destroy()
        if self.module_menu:
            self.menu_frame.destroy()
        self.parent.forget(self.pane)
        super().destroy()

    def clear(self):
        if self.module:
            self.module.destroy()

    def add_module(self):
        pass


class Module:
    def __init__(self, name, parent, callbacks, state):
        self.name = name
        self.parent = parent 
        self.frame = None
        self.callbacks = callbacks
        self.state = state
        self.textboxes = []

    def build(self):
        self.frame = ttk.Frame(self.parent.pane, borderwidth=2)
        self.frame.pack(expand=True, fill='both')
    
    def destroy(self):
        self.frame.pack_forget()
        self.frame.destroy()
        self.frame = None
    
    def tree_updated(self):
        pass

    def selection_updated(self):
        pass

    # returns true if any of the module's textboxes are enabled and have focus
    def textbox_has_focus(self):
        for textbox in self.textboxes:
            if self.frame.focus_get() == textbox and textbox.cget('state') == 'normal':
                return True
        return False