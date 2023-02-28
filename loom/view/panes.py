from tkinter import ttk
import tkinter as tk
from loom.view.colors import bg_color, text_color
from loom.view.icons import Icons

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
    def __init__(self, name, parent, orient, module_options, module_selection_callback, module_window_destroy_callback, hide_pane_callback):
        super().__init__(parent, orient)
        self.name = name
        self.frame = None
        self.pane = None
        self.menu_frame = None

        self.x_button = None
        self.close_icon = None
        self.add_module_button = None
        self.module_windows = []

        self.module_selection_callback = module_selection_callback
        self.module_window_destroy_callback = module_window_destroy_callback
        self.module_options = module_options
        self.hide_pane_callback = hide_pane_callback
        self.hidden = None

    def build_pane(self, weight):
        self.frame = ttk.Frame(self.parent)
        self.parent.add(self.frame, weight=weight)
        self.menu_frame = ttk.Frame(self.frame)#, background=bg_color())
        self.menu_frame.pack(side='top', fill='x')
        
        self.add_module_button = tk.Label(self.menu_frame, image=icons.get_icon("plus-lightgray"), bg=bg_color(), cursor='hand2')
        self.add_module_button.bind('<Button-1>', self.add_empty_module_window)
        #self.add_module_button = tk.Button(self.menu_frame, text='Add Module', fg=text_color(), bg=bg_color(), cursor='hand2')
        self.add_module_button.pack(side='left', padx=20)
        #self.add_module_button.bind('<Button-1>', self.add_module_window)

        self.close_icon = icons.get_icon('x-lightgray')
        self.x_button = tk.Label(self.menu_frame, text='-', fg=text_color(), bg=bg_color(), cursor='hand2')
        self.x_button.pack(side='right', padx=20)
        self.x_button.bind('<Button-1>', lambda event, pane=self: self.hide_pane_callback(pane=self))#lambda event, pane_name=self.name: destroy_callback(pane_name=pane_name))

        self.pane = ttk.PanedWindow(self.frame, orient=self.orient)
        self.pane.pack(side='top', fill='both', expand=True)
        self.hidden = False
        
    def hide(self):
        if not self.hidden:
            self.parent.forget(self.frame)
            self.hidden = True

    def show(self):
        if self.hidden:
            self.parent.add(self.frame)
            self.hidden = False

    def destroy(self, *args):
        # if self.module_menu:
        #     self.module_menu.destroy()
        if self.x_button:
            self.x_button.destroy()
        # if self.module_menu:
        #     self.menu_frame.destroy()
        self.parent.forget(self.frame)
        self.frame.destroy()

        super().destroy()

    def clear(self):
        pass

    def add_empty_module_window(self, *args):
        new_module_window = ModuleWindow(self)
        self.module_windows.append(new_module_window)
        new_module_window.build(self.module_options, self.module_selection_callback, self.module_window_destroy_callback)
        return new_module_window
        
    def add_module(self, module):
        new_module_window = self.add_empty_module_window()
        new_module_window.change_module(module)

    def module_names(self):
        return [window.module_name() for window in self.module_windows]


class ModuleWindow:
    def __init__(self, parent):
        self.parent = parent
        self.frame = None
        self.menu_frame = None
        self.module_menu = None  
        self.module_selection = tk.StringVar()
        self.module = None
        self.close_button = None
        #self.index = index

    def build(self, options, selection_callback, destroy_callback):
        self.frame = ttk.Frame(self.parent.pane, borderwidth=2, relief='sunken')#, height=1, background=bg_color())
        self.parent.pane.add(self.frame, weight=1)

        self.menu_frame = ttk.Frame(self.frame)
        self.menu_frame.pack(side='top', fill='x', expand=False)
        # make dropdown for selecting a module
        self.module_selection.set('None')
        self.module_menu = tk.OptionMenu(self.menu_frame, self.module_selection, *options)
        self.module_menu.pack(side='left', expand=True, padx=20)
        self.module_selection.trace('w', lambda a, b, c, module_window=self: selection_callback(module_window=module_window))

        self.close_icon = icons.get_icon('x-lightgray')
        self.x_button = tk.Label(self.menu_frame, text='⨯', fg=text_color(), bg=bg_color(), cursor='hand2')
        self.x_button.pack(side='right', padx=20)
        self.x_button.bind('<Button-1>', lambda event, module_window=self: destroy_callback(module_window=module_window))

    def destroy(self):
        self.parent.module_windows.remove(self)
        self.parent.pane.forget(self.frame)
        self.frame.destroy()
        self.frame = None

    def clear(self):
        if self.module:
            self.module.destroy()
            self.module = None

    def pane_name(self):
        return self.parent.name

    def module_name(self):
        return self.module.name if self.module else None

    def set_selection(self, module_name):
        self.module_selection.set(module_name)

    def change_module(self, module):
        self.clear()
        self.module = module
        self.module.build(parent=self)
        self.set_selection(module.name)


class Module:
    def __init__(self, name, callbacks, state):
        self.name = name
        self.frame = None
        self.parent = None
        self.callbacks = callbacks
        self.state = state
        self.textboxes = []
        #self.settings = self.state.module_settings[name] if name in self.state.module_settings else {}

    def settings(self):
        return self.state.module_settings[self.name] if self.name in self.state.module_settings else {}

    def build(self, parent):
        self.parent = parent
        self.frame = ttk.Frame(self.parent.frame, borderwidth=2)
        self.frame.pack(expand=True, fill='both', side="top")
    
    def destroy(self):
        self.frame.pack_forget()
        self.frame.destroy()
        self.frame = None

    def window(self):
        return self.parent

    def tree_updated(self):
        pass

    def selection_updated(self):
        pass

    # returns true if any of the module's textboxes are enabled and have focus
    def textbox_has_focus(self):
        #print(self.name)
        #print(self.frame)
        for textbox in self.textboxes:
            if self.frame.focus_get() == textbox and textbox.cget('state') == 'normal':
                return True
        return False
