import tkinter as tk
from tkinter import ttk
from view.colors import text_color, bg_color, edit_color, default_color
from util.custom_tks import TextAware, ScrollableFrame
from util.react import *
from tkinter.scrolledtext import ScrolledText
from view.styles import textbox_config
from view.icons import Icons

buttons = {'go': 'arrow-green',
           'edit': 'edit-blue',
           'attach': 'link-black',
           'archive': 'archive-yellow',
           'close': 'minus-lightgray',
           'delete': 'trash-red',}

icons = Icons()


class EvalCode:
    def __init__(self, init_text, callbacks):
        self.code_textbox = None
        self.label = None
        self.init_text = init_text
        self.callbacks = callbacks

    def body(self, master):
        self.label = tk.Label(master, text='**** HUMANS ONLY ****', bg=default_color(), fg=text_color())
        self.label.pack(side=tk.TOP, fill=tk.X)
        self.code_textbox = ScrolledText(master, height=2)
        self.code_textbox.pack(fill=tk.BOTH, expand=True)
        self.code_textbox.configure(**textbox_config(bg='black', font='Monaco'))
        self.code_textbox.insert(tk.INSERT, self.init_text)
        self.code_textbox.focus()

    def apply(self):
        code = self.code_textbox.get("1.0", 'end-1c')
        self.callbacks["Run"]["prev_cmd"] = code
        self.callbacks["Eval"]["callback"](code_string=code)


class Windows:
    def __init__(self, callbacks, buttons, buttons_visible=True, editable=True):
        self.callbacks = callbacks
        self.scroll_frame = None
        self.windows_pane = None
        self.windows = {}
        self.master = None
        self.buttons = buttons
        self.blacklist = []
        self.whitelist = []
        self.buttons_visible = buttons_visible
        self.editable = editable

    def body(self, master):
        self.master = master
        # self.scroll_frame = ScrollableFrame(self.master)
        # self.scroll_frame.pack(expand=True, fill="both")
        self.windows_pane = ttk.PanedWindow(master, orient='vertical', height=300)
        self.windows_pane.pack(side='top', fill='both', expand=True)

    def open_window(self, node):
        if node['id'] in self.windows:
            return
        self.windows[node['id']] = {'frame': ttk.Frame(self.windows_pane, borderwidth=1)}
        self.windows[node['id']]['node'] = node
        tk.Grid.columnconfigure(self.windows[node['id']]['frame'], 0, weight=1)
        for i in range(len(self.buttons)):
            tk.Grid.rowconfigure(self.windows[node['id']]['frame'], i, weight=1)
        self.windows_pane.add(self.windows[node['id']]['frame'], weight=1)
        self.windows[node['id']]['textbox'] = TextAware(self.windows[node['id']]['frame'], bd=3, undo=True)
        self.windows[node['id']]['textbox'].grid(row=0, column=0, rowspan=len(self.buttons), pady=5, sticky=tk.N + tk.S + tk.E + tk.W)
        self.windows[node['id']]['textbox'].configure(**textbox_config(bg=edit_color()))
        self.windows[node['id']]['textbox'].bind("<FocusOut>", lambda event, _id=node['id']: self.save_edits(_id))
        self.windows[node['id']]['textbox'].insert("1.0", node["text"])
        if not self.editable:
            self.edit_off(node['id'])
        else:
            self.edit_on(node['id'])
        if self.buttons_visible:
            for i, button in enumerate(self.buttons):
                self.draw_button(i, node['id'], button)

    def draw_button(self, row, window_id, button):
        self.windows[window_id][button] = tk.Label(self.windows[window_id]['frame'], image=icons.get_icon(buttons[button]), bg=bg_color(), cursor='hand2')
        self.windows[window_id][button].grid(row=row, column=1, padx=5)
        if button == 'go':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _node=self.windows[window_id]['node']: self.goto_node(_node))
        elif button == 'edit':
            self.windows[window_id][button].bind("<Button-1>", lambda event, window_id=window_id: self.toggle_edit(window_id))
        elif button == 'attach':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _node=self.windows[window_id]['node']: self.attach_node(_node))
        elif button == 'archive':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _node=self.windows[window_id]['node']: self.archive_node(_node))
        elif button == 'close':
            self.windows[window_id][button].bind("<Button-1>", lambda event, window_id=window_id: self.close_window(window_id))
        elif button == 'delete':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _node=self.windows[window_id]['node']: self.delete_node(_node))

    def hide_buttons(self):
        for window_id in self.windows:
            for button in self.buttons:
                self.windows[window_id][button].grid_remove()

    def close_window(self, window_id):
        self.remove_window(window_id)
        self.blacklist.append(window_id)

    def remove_window(self, window_id):
        self.windows_pane.forget(self.windows[window_id]['frame'])
        self.windows[window_id]['frame'].destroy()
        del self.windows[window_id]
    
    def clear_windows(self):
        for window in self.windows:
            self.remove_window(window)

    def goto_node(self, node):
        self.callbacks["Select node"]["callback"](node=node)

    def save_edits(self, window_id):
        node = self.windows[window_id]['node']
        new_text = self.windows[window_id]['textbox'].get("1.0", 'end-1c')
        self.callbacks["Update text"]["callback"](node=node, text=new_text)

    def save_windows(self):
        for window_id in self.windows:
            self.save_edits(window_id)

    def edit_off(self, window_id):
        self.windows[window_id]['textbox'].configure(state='disabled', 
                                                     background=bg_color(),
                                                     relief=tk.RAISED)

    def edit_on(self, window_id):
        self.windows[window_id]['textbox'].configure(state='normal', 
                                                     background=edit_color(),
                                                     relief=tk.SUNKEN)

    def toggle_edit(self, window_id):
        if self.windows[window_id]['textbox'].cget('state') == 'disabled':
            self.edit_on(window_id)
        else:
            self.edit_off(window_id)

    def attach_node(self, node):
        pass

    def archive_node(self, node):
        self.callbacks["Tag"]["callback"](node=node, tag="archived")

    def delete_node(self, node):
        #self.remove_window(node['id'])
        self.callbacks["Delete"]["callback"](node=node)

    def update_windows(self, nodes):
        new_windows, deleted_windows = react_changes(old_components=self.windows.keys(), new_components=[node['id'] for node in nodes])
        for window_id in deleted_windows:
            self.remove_window(window_id)
        new_nodes = [node for node in nodes if node['id'] in new_windows and node['id'] not in self.blacklist]
        for node in new_nodes:
            self.open_window(node)

    def update_text(self):
        for window_id in self.windows:
            changed_edit = False
            if self.windows[window_id]['textbox'].cget('state') == 'disabled':
                self.windows[window_id]['textbox'].configure(state='normal')
                changed_edit = True
            self.windows[window_id]['textbox'].delete("1.0", "end")
            self.windows[window_id]['textbox'].insert("1.0", self.callbacks["Text"]["callback"](node_id=window_id))
            if changed_edit:
                self.windows[window_id]['textbox'].configure(state='disabled')
