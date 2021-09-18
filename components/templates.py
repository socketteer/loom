from re import L
import tkinter as tk
from tkinter import Frame, ttk, filedialog
import uuid
from view.colors import text_color, bg_color, edit_color, default_color
from util.custom_tks import TextAware, ScrollableFrame
from util.react import *
from util.util_tk import create_side_label, create_label, Entry, create_button, create_slider, create_combo_box, create_checkbutton
from tkinter.scrolledtext import ScrolledText
from view.styles import textbox_config
from view.icons import Icons
import time
from util.util_tk import create_side_label, create_label, Entry, create_button, create_slider, create_combo_box, create_checkbutton
import os
import codecs
from PIL import Image, ImageTk
from gpt import POSSIBLE_MODELS
import json
import bisect
from util.util import split_indices

buttons = {'go': 'arrow-green',
           'edit': 'edit-blue',
           'attach': 'leftarrow-lightgray',
           'archive': 'archive-yellow',
           'close': 'minus-lightgray',
           'delete': 'trash-red',
           'append': 'up-lightgray',
           'save': 'save-white'}

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
    def __init__(self, buttons):
        self.windows_pane = None
        self.windows = {}
        self.master = None
        self.scroll_frame = None
        self.buttons = buttons

    def body(self, master):
        self.master = master
        self.scroll_frame = ScrollableFrame(self.master)
        self.scroll_frame.pack(expand=True, fill="both")
        self.windows_pane = tk.PanedWindow(self.scroll_frame.scrollable_frame, orient='vertical')
        self.windows_pane.pack(side='top', fill='both', expand=True)

    def open_window(self, text):
        window_id = str(uuid.uuid1())
        self.windows[window_id] = {'frame': ttk.Frame(self.windows_pane, borderwidth=1)}
        tk.Grid.columnconfigure(self.windows[window_id]['frame'], 1, weight=1)
        for i in range(len(self.buttons)):
            tk.Grid.rowconfigure(self.windows[window_id]['frame'], i, weight=1)
        self.windows_pane.add(self.windows[window_id]['frame'], height=100)
        self.windows[window_id]['textbox'] = TextAware(self.windows[window_id]['frame'], bd=3, undo=True)
        self.windows[window_id]['textbox'].grid(row=0, column=1, rowspan=len(self.buttons), pady=5, sticky=tk.N + tk.S + tk.E + tk.W)
        self.windows[window_id]['textbox'].configure(**textbox_config(bg=edit_color(), pady=1, spacing2=3, spacing1=4))
        self.windows[window_id]['textbox'].insert("1.0", text)

        for i, button in enumerate(self.buttons):
             self.draw_button(i, window_id, button)

    def draw_button(self, row, window_id, button):
        self.windows[window_id][button] = tk.Label(self.windows[window_id]['frame'], image=icons.get_icon(buttons[button]), bg=bg_color(), cursor='hand2')
        self.windows[window_id][button].grid(row=row, column=2, padx=5)
        if button == 'close':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _id=window_id: self.close_window(_id))

    def close_window(self, window_id):
        self.remove_window(window_id)

    def remove_window(self, window_id):
        self.windows_pane.forget(self.windows[window_id]['frame'])
        self.windows[window_id]['frame'].destroy()
        del self.windows[window_id]
    
    def clear_windows(self):
        # self.windows_pane.pack_forget()
        # self.windows_pane.destroy()
        # self.windows_pane = tk.PanedWindow(self.scroll_frame.scrollable_frame, orient='vertical')
        # self.windows_pane.pack(side='top', fill='both', expand=True)
        # self.windows = {}
        for window in self.windows:
            self.remove_window(window)

    def destroy(self):
        self.scroll_frame.pack_forget()
        self.scroll_frame.destroy()


class NodeWindows(Windows):
    def __init__(self, callbacks, buttons, buttons_visible=True, nav_icons_visible=True, editable=True, init_height=1):
        self.callbacks = callbacks
        self.blacklist = []
        self.whitelist = []
        self.buttons_visible = buttons_visible
        self.nav_icons_visible = nav_icons_visible
        self.editable = editable
        self.init_height = init_height
        Windows.__init__(self, buttons)

    def open_window(self, node, insert='end'):
        if node['id'] in self.windows:
            return
        self.windows[node['id']] = {'frame': ttk.Frame(self.windows_pane, borderwidth=1)}
        self.windows[node['id']]['node'] = node
        tk.Grid.columnconfigure(self.windows[node['id']]['frame'], 1, weight=1)
        for i in range(len(self.buttons)):
            tk.Grid.rowconfigure(self.windows[node['id']]['frame'], i, weight=1)
        #  TODO adaptive init height based on text length

        self.windows_pane.add(self.windows[node['id']]['frame'], height=100)
        #self.windows_pane.paneconfig(self.windows[node['id']]['frame'])
        # if insert == 'end':
        #     self.windows_pane.add(self.windows[node['id']]['frame'], weight=1)
        # else:
        #     self.windows_pane.insert(0, self.windows[node['id']]['frame'], weight=1)
        self.windows[node['id']]['textbox'] = TextAware(self.windows[node['id']]['frame'], bd=3, undo=True)
        self.windows[node['id']]['textbox'].grid(row=0, column=1, rowspan=len(self.buttons), pady=5, sticky=tk.N + tk.S + tk.E + tk.W)
        self.windows[node['id']]['textbox'].configure(**textbox_config(bg=edit_color()))
        # bind click event to goto node
        self.windows[node['id']]['textbox'].insert("1.0", node["text"])

        self.windows[node['id']]['textbox'].bind("<FocusOut>", lambda event, _id=node['id']: self.save_edits(_id))
        self.windows[node['id']]['textbox'].bind("<Button-1>", lambda event, _id=node['id']: self.window_clicked(_id))

        if not self.editable:
            self.edit_off(node['id'])
        else:
            self.edit_on(node['id'])
        if self.buttons_visible:
            for i, button in enumerate(self.buttons):
                self.draw_button(i, node['id'], button)
        if self.nav_icons_visible:
            self.draw_nav_icon(node['id'])

    def fix_heights(self):
        for i in range(len(self.windows) - 1):
            self.windows_pane.update_idletasks()
            self.windows_pane.sashpos(i, 100 * (i+1))

    def draw_nav_icon(self, window_id):
        icon = self.callbacks["Nav icon"]["callback"](node=self.windows[window_id]['node'])
        self.windows[window_id]['icon'] = tk.Label(self.windows[window_id]['frame'], image=icon, bg=bg_color())
        self.windows[window_id]['icon'].grid(row=0, column=0, rowspan=len(self.buttons))

    def draw_button(self, row, window_id, button):
        self.windows[window_id][button] = tk.Label(self.windows[window_id]['frame'], image=icons.get_icon(buttons[button]), bg=bg_color(), cursor='hand2')
        self.windows[window_id][button].grid(row=row, column=2, padx=5)
        if button == 'go':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _id=window_id: self.goto_node(_id))
        elif button == 'edit':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _id=window_id: self.toggle_edit(_id))
        elif button == 'attach':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _node=self.windows[window_id]['node']: self.attach_node(_node))
        elif button == 'archive':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _node=self.windows[window_id]['node']: self.archive_node(_node))
        elif button == 'close':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _id=window_id: self.close_window(_id))
        elif button == 'delete':
            self.windows[window_id][button].bind("<Button-1>", lambda event, _node=self.windows[window_id]['node']: self.delete_node(_node))

    def hide_buttons(self):
        for window_id in self.windows:
            for button in self.buttons:
                self.windows[window_id][button].grid_remove()

    def close_window(self, window_id):
        Windows.close_window(self, window_id)
        self.blacklist.append(window_id)

    def window_clicked(self, window_id):
        if self.windows[window_id]['textbox'].cget("state") == 'disabled':
            self.goto_node(window_id)

    def goto_node(self, node_id):
        node = self.windows[node_id]['node']
        self.callbacks["Select node"]["callback"](node=node)

    def save_edits(self, window_id):
        # why does this cause all windows to reload?
        node = self.windows[window_id]['node']
        new_text = self.windows[window_id]['textbox'].get("1.0", 'end-1c')
        self.callbacks["Update text"]["callback"](node=node, text=new_text)

    def save_windows(self):
        for window_id in self.windows:
            self.save_edits(window_id)

    def edit_off(self, window_id):
        if self.windows[window_id]['textbox'].cget("state") == "normal":
            self.windows[window_id]['textbox'].configure(state='disabled', 
                                                        background=bg_color(),
                                                        relief=tk.RAISED)
            self.save_edits(window_id)

    def edit_on(self, window_id):
        if self.windows[window_id]['textbox'].cget("state") == "disabled":
            self.windows[window_id]['textbox'].configure(state='normal', 
                                                         background=edit_color(),
                                                         relief=tk.SUNKEN)
        

    def toggle_edit(self, window_id):
        if self.windows[window_id]['textbox'].cget('state') == 'disabled':
            self.edit_on(window_id)
        else:
            self.edit_off(window_id)

    def focus_textbox(self, window_id):
        self.windows[window_id]['textbox'].focus_set()

    def attach_node(self, node):
        pass

    def archive_node(self, node):
        self.callbacks["Tag"]["callback"](node=node, tag="archived")

    def delete_node(self, node):
        #self.remove_window(node['id'])
        self.callbacks["Delete"]["callback"](node=node)

    def update_windows(self, nodes, insert='end'):
        new_windows, deleted_windows = react_changes(old_components=self.windows.keys(), new_components=[node['id'] for node in nodes])
        for window_id in deleted_windows:
            self.remove_window(window_id)
        new_nodes = [node for node in nodes if node['id'] in new_windows and node['id'] not in self.blacklist]
        for node in new_nodes:
            self.open_window(node, insert=insert)
        #self.fix_heights()

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


class Thumbnails:
    def __init__(self, selection_callback):
        self.selection_callback = selection_callback
        self.thumbnails = {}
        self.scroll_frame = None
        self.master = None
        self.selected_file = None

    def body(self, master, height=400):
        self.master = master
        self.scroll_frame = ScrollableFrame(master, width=110, height=height)
        self.scroll_frame.pack(side='top', fill='both', expand=True)

    def get_thumbnail(self, filename):
        # open image
        img = Image.open(filename)
        # resize
        img.thumbnail((100, 100), Image.ANTIALIAS)
        # convert to tkinter image
        img = ImageTk.PhotoImage(img)
        return img

    def add_thumbnail(self, filename):
        if filename not in self.thumbnails:
            image = self.get_thumbnail(filename)
            self.thumbnails[filename] = {}
            self.thumbnails[filename]['thumbnail'] = tk.Label(self.scroll_frame.scrollable_frame, image=image, bg="white", cursor='hand2', width=100, bd=5)
            self.thumbnails[filename]['thumbnail'].image = image
            self.thumbnails[filename]['thumbnail'].bind("<Button-1>", lambda event, filename=filename: self.select(filename=filename))
            self.thumbnails[filename]['thumbnail'].pack(side='top', pady=5, padx=5)
            self.build_menu(filename)
            self.thumbnails[filename]['thumbnail'].bind("<Button-3>", lambda event, filename=filename: self.do_popup(event, filename=filename))

    def build_menu(self, filename):
        self.thumbnails[filename]['menu'] = tk.Menu(self.master, tearoff=0)
        self.thumbnails[filename]['menu'].add_command(label="Select", command=lambda filename=filename: self.select(filename=filename)) 

    def do_popup(self, event, filename):
        self.thumbnails[filename]['menu'].tk_popup(event.x_root, event.y_root)
        # try:
        #     self.thumbnails[filename]['menu'].tk_popup(event.x_root, event.y_root)
        # finally:
        #     self.thumbnails[filename]['menu'].grab_release()

    def remove_thumbnail(self, filename):
        if filename in self.thumbnails:
            self.thumbnails[filename]['thumbnail'].destroy()
            del self.thumbnails[filename]

    def clear(self):
        for filename in self.thumbnails:
            self.thumbnails[filename]['thumbnail'].destroy()
        self.thumbnails = {}

    def update_thumbnails(self, image_files):
        new_windows, deleted_windows = react_changes(old_components=self.thumbnails.keys(), new_components=image_files)
        for filename in deleted_windows:
            self.remove_thumbnail(filename)
        for filename in new_windows:
            self.add_thumbnail(filename)
        self.selected_file = list(self.thumbnails.keys())[-1]

    def select(self, filename, *args):
        self.set_selection(filename)
        self.selection_callback(filename=filename)

    def set_selection(self, filename):
        self.thumbnails[self.selected_file]['thumbnail'].configure(relief="flat")
        self.selected_file = filename
        self.thumbnails[filename]['thumbnail'].configure(relief="sunken")

    def scroll_to_selected(self):
        pass

    def scroll_to_end(self):
        pass


class Multimedia:
    def __init__(self, callbacks, state):
        self.img = None
        self.state = state
        self.caption = None
        self.viewing = None
        self.master = None
        self.selected_node_text = None
        self.next_button = None
        self.prev_button = None
        self.move_up_button = None
        self.move_down_button = None
        self.delete_button = None
        self.caption_button = None
        self.n = 0
        self.thumbnails = None
        self.thumbnails_frame = None
        self.callbacks = callbacks
        self.state = state
    
    def body(self, master):
        self.master = master
        #button = create_button(master, "Add media", self.add_media)
        #button.grid(row=1, column=1, sticky='w')
        #tk.Grid.rowconfigure(master, 0, weight=1)
        tk.Grid.rowconfigure(master, 2, weight=1)
        tk.Grid.columnconfigure(master, 1, weight=1)
        self.thumbnails_frame = tk.Frame(self.master)
        self.thumbnails_frame.grid(row=0, column=3)
        self.thumbnails = Thumbnails(selection_callback=self.select_file)
        self.thumbnails.body(self.thumbnails_frame)
        self.populate_thumbnails()
        self.create_image()
        self.create_buttons()
        self.refresh()

    def refresh(self):
        self.populate_thumbnails()
        self.display_image()
        self.set_buttons()
        self.set_node_text()

    def populate_thumbnails(self):
        self.thumbnails.clear()
        if 'multimedia' in self.state.selected_node:
            self.thumbnails.update_thumbnails([media['file'] for media in self.state.selected_node['multimedia']])

    def num_media(self):
        if 'multimedia' in self.state.selected_node:
            return len(self.state.selected_node['multimedia'])
        else:
            return 0

    def create_image(self):
        img = tk.PhotoImage(file='static/media/black.png')
        self.img = tk.Label(self.master, image=img, bg="white")
        self.img.grid(row=0, column=1)
        self.caption = tk.Label(self.master, text='', bg=default_color())
        self.caption.grid(row=1, column=0, columnspan=3)
        self.selected_node_text = TextAware(self.master)
        self.selected_node_text.config(state='disabled', **textbox_config())
        self.selected_node_text.grid(row=2, column=0, columnspan=4)
        #self.viewing = tk.Label(self.master, text=f"{self.n + 1} / {self.num_media()}", bg=default_color())
        #self.viewing.grid(row=3, column=1)

    def create_buttons(self):
        self.prev_button = tk.Label(self.master, image=icons.get_icon("left-white", size=25), bg=bg_color(), cursor="hand2")
        self.prev_button.grid(row=0, column=0)
        self.prev_button.bind("<Button-1>", lambda event: self.traverse(1))
        self.next_button = tk.Label(self.master, image=icons.get_icon("right-white", size=25), bg=bg_color(), cursor="hand2")
        self.next_button.grid(row=0, column=2)
        self.next_button.bind("<Button-1>", lambda event: self.traverse(-1))
        # self.next_button = create_button(self.master, "Next", lambda: self.traverse(1))
        # self.next_button.grid(row=4, column=1, sticky='e')
        # self.prev_button = create_button(self.master, "Prev", lambda: self.traverse(-1))
        # self.prev_button.grid(row=4, column=1, sticky='w')
        # self.move_up_button = create_button(self.master, "Move >", lambda: self.shift(1))
        # self.move_up_button.grid(row=5, column=1, sticky='e')
        # self.move_down_button = create_button(self.master, "< Move", lambda: self.shift(-1))
        # self.move_down_button.grid(row=5, column=1, sticky='w')
        # self.caption_button = create_button(self.master, "Change caption", self.change_caption)
        # self.caption_button.grid(row=5, column=1)
        # self.caption_button.config(width=15)
        # self.delete_button = create_button(self.master, "Delete", self.delete_media)
        # self.delete_button.grid(row=1, column=1, sticky='e')

    def set_buttons(self):
        if not self.next_button:
            self.create_buttons()
        if self.num_media() > 0:
            self.next_button.grid()
            self.prev_button.grid()
            # self.next_button["state"] = "normal"
            # self.prev_button["state"] = "normal"
            # self.move_up_button["state"] = "normal"
            # self.move_down_button["state"] = "normal"
            # self.delete_button["state"] = "normal"
            # self.caption_button["state"] = "normal"
        else:
            self.next_button.grid_remove()
            self.prev_button.grid_remove()
            # self.next_button["state"] = "disabled"
            # self.prev_button["state"] = "disabled"
            # self.move_up_button["state"] = "disabled"
            # self.move_down_button["state"] = "disabled"
            # self.delete_button["state"] = "disabled"
            # self.caption_button["state"] = "disabled"

    def set_node_text(self):
        self.selected_node_text.config(state='normal')
        self.selected_node_text.delete("1.0", "end")
        self.selected_node_text.insert("1.0", self.callbacks["Text"]["callback"](node_id=self.state.selected_node_id))
        self.selected_node_text.config(state='disabled')

    def change_caption(self):
        if self.num_media() > 0:
            self.state.selected_node['multimedia'][self.n]['caption'] = 'new caption'
            self.display_image()

    # def repair_type(self):
    #     if self.num_media() > 0:
    #         new_multimedia = []
    #         for media in self.state.selected_node['multimedia']:
    #             if isinstance(media, str):
    #                 new_multimedia.append({'file': media, 'caption': ''})
    #             elif isinstance(media, dict):
    #                 new_multimedia.append(media)
    #             else:
    #                 print('error invalid type')
    #         self.state.selected_node['multimedia'] = new_multimedia

    def display_image(self):
        if not self.img:
            self.create_image()
        if self.num_media() > 0:
            try:
                #self.repair_type()
                img = tk.PhotoImage(file=self.state.selected_node['multimedia'][self.n]['file'])
                caption = self.state.selected_node['multimedia'][self.n]['caption']
            except tk.TclError:
                return
            self.img.configure(image=img)
            self.img.image = img
            self.caption.configure(text=caption)
            #self.viewing.configure(text=f"{self.n + 1} / {self.num_media()}")
        else:
            try:
                self.img.image.blank()
                self.img.image = None
                self.caption.configure(text='')
            except AttributeError:
                return

    def add_media(self):
        tree_dir = self.state.tree_dir()
        # if media folder not in tree directory, create it
        if not os.path.isdir(tree_dir + '/media'):
            os.mkdir(tree_dir + '/media')
        options = {
            'initialdir': tree_dir + '/media',
        }
        filenames = filedialog.askopenfilenames(**options)
        if not filenames:
            return
        self.callbacks["Add multimedia"]["callback"](filenames=filenames)
        self.n = self.num_media() - 1
        self.display_image()
        self.set_buttons()

    def delete_media(self):
        del self.state.selected_node['multimedia'][self.n]
        if self.n != 0:
            self.n -= 1
        self.populate_thumbnails()
        self.display_image()
        self.set_buttons()

    def traverse(self, interval):
        self.n = (self.n + interval) % self.num_media()
        self.display_image()
        self.set_buttons()

    def shift(self, interval):
        new_index = (self.n + interval) % self.num_media()
        self.state.selected_node['multimedia'][self.n], self.state.selected_node['multimedia'][new_index] = self.state.selected_node['multimedia'][new_index],\
                                                                              self.state.selected_node['multimedia'][self.n]
        self.n = new_index
        self.display_image()
        self.set_buttons()

    def select_file(self, filename, *args):
        filename_list = [media['file'] for media in self.state.selected_node['multimedia']]
        self.n = filename_list.index(filename)
        self.display_image()
        self.set_buttons()
        

class CollapsableFrame(tk.Frame):
    def __init__(self, master, image='', title='', expand=True, **kwargs):
        tk.Frame.__init__(self, master, **kwargs)
        #self.master = master
        self.expand = expand
        if title or image: 
            self.title = tk.Label(self, text=title, image=image, compound='left', bg=bg_color(), fg=text_color())
            self.title.grid(row=0, column=0, sticky='w')
        self.hide_button = tk.Label(self, text="-", cursor="hand2", fg=text_color(), bg=bg_color(), font=("Helvetica", 16))
        self.hide_button.grid(row=0, column=2)
        self.hide_button.bind("<Button-1>", lambda event: self.toggle())
        self.collapsable_frame = tk.Frame(self)
        self.collapsable_frame.grid(row=1, column=0, columnspan=3, sticky='nsew')
        tk.Grid.columnconfigure(self, 0, weight=1)
        if self.expand:
            tk.Grid.rowconfigure(self, 1, weight=1)

    def hide(self):
        self.update_idletasks()
        if self.collapsable_frame.winfo_ismapped():
            self.collapsable_frame.grid_remove()
            self.hide_button.configure(text="+")
            self.pack_configure(expand=False)

    def show(self):
        self.update_idletasks()
        if not self.collapsable_frame.winfo_ismapped():
            self.collapsable_frame.grid(row=1, column=0, columnspan=3, sticky='nsew')
            self.hide_button.configure(text="-")
            if self.expand:
                self.pack_configure(expand=True)

    def toggle(self):
        if self.collapsable_frame.winfo_ismapped():
            self.hide()
        else:
            self.show()
        

class TextAttribute:
    def __init__(self, master, attribute_name, read_callback=None, write_callback=None, delete_callback=None, expand=False, parent_module=None, height=3, **kwargs):
        self.master = master
        self.read_callback = read_callback
        self.write_callback = write_callback
        self.delete_callback = delete_callback
        self.parent_module = parent_module

        self.frame = CollapsableFrame(master, title=attribute_name, expand=expand, bg=bg_color())

        if self.delete_callback:
            self.delete_button = tk.Label(self.frame, image=icons.get_icon("trash-red"), cursor="hand2", bg=bg_color())
            self.delete_button.grid(row=0, column=1, padx=10)
            self.delete_button.bind("<Button-1>", lambda event: self.delete_callback())

        self.textbox = TextAware(self.frame.collapsable_frame, height=height, **kwargs)
        self.textbox.pack(fill='both', expand=True)

        self.textbox.configure(**textbox_config(bg=edit_color()))

        self.textbox.bind("<Button>", lambda event: self.textbox.focus_set())
        self.textbox.bind("<FocusOut>", lambda event: self.write())
        self.textbox.bind("<Key>", self.key_pressed)
        if self.parent_module:
            self.parent_module.textboxes.append(self.textbox)
    
    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def hide(self):
        self.frame.hide()

    def show(self):
        self.frame.show()

    def destroy(self):
        if self.parent_module:
            self.parent_module.textboxes.remove(self.textbox)
        self.frame.pack_forget()
        self.frame.destroy()

    def write(self):
        if self.write_callback:
            text = self.get()
            self.write_callback(text=text)

    def read(self):
        if self.read_callback:
            text = self.read_callback()
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", text)

    def get(self):
        return self.textbox.get("1.0", "end-1c")

    def key_pressed(self, event):
        # if key is tab, break
        if event.keysym == 'Tab':
            self.master.focus()
            return "break"



class SmartText(TextAware):
    """
    alternatives:
    {
        alts : [{'text': string, ?'probability': float}],
        replace_range: [start, end]
    }
    """
    def __init__(self, *args, **kwargs):
        TextAware.__init__(self, *args, **kwargs)
        
        self.bind("<Key>", self.key_pressed)
        self.bind("<Button>", lambda event: self.focus_set())
        self.bind("<Button>", self.button_pressed)
        self.bind("<Escape>", self.clear_temp_tags)
        #self.bind("<Button-1>", lambda event: self.clear_temp_tags())
        self.tag_configure("sel", background="black", foreground="white")
        self.tag_configure("insert", background="black", foreground="white")
        self.tag_configure("alternate", background="#222222", foreground="white",
                           font=('Georgia', 12, 'italic'))
        self.tag_raise("sel")
        self.tag_raise("insert")
        self.alternatives = []

    def key_pressed(self, event):
        pass

    def button_pressed(self, event):
        pass
    
    def clear_temp_tags(self, event):
        self.tag_remove("insert", "1.0", "end")
        self.tag_remove("alternate", "1.0", "end")

    def select_range(self, start, end):
        self.tag_range("sel", start, end)
    
    def tag_range(self, tag, start, end):
        self.tag_remove(tag, "1.0", tk.END)
        self.tag_add(tag, f"1.0 + {start} chars", f"1.0 + {end} chars")
        self.tag_raise(tag)

    def get_range(self, start, end):
        return self.get(f"1.0 + {start} chars", f"1.0 + {end} chars")

    def char_index(self, index):
        return len(self.get("1.0", index))

    def selected_text(self):
        return self.get("sel.first", "sel.last")

    def selected_range(self):
        return len(self.get("1.0", "sel.first")), len(self.get("1.0", "sel.last"))

    def fix_selection(self):
        # round selection positions to include full words (spaces are grouped at the beginning of the word - no training spaces!)
        # TODO option to disable...
        start, end = self.selected_range()
        indices = list(split_indices(self.get("1.0", "end-1c")))
        word_end_indices = [0]
        word_start_indices = []
        for i in indices:
            word_end_indices.append(i[1][1])
            word_start_indices.append(i[1][0])
        rounded_start_index = word_end_indices[bisect.bisect_right(word_end_indices, start) - 1]
        # check if rounded start index is before a newline, use word_start_indices instead
        if self.get(f"1.0 + {rounded_start_index} chars") == "\n":
            rounded_start_index = word_start_indices[bisect.bisect_right(word_start_indices, start) - 1]
        rounded_end_index = word_end_indices[bisect.bisect_left(word_end_indices, end)]
        self.select_range(rounded_start_index, rounded_end_index)

    def fix_insertion(self):
        # if insertion cursor is preceded by space, move it to the end of the previous word
        new_position = self.fix_insertion_position(tk.INSERT)
        self.mark_set(tk.INSERT, new_position)

    def fix_insertion_position(self, position):
        if self.get(f"{position}-1c") == " ":
            return f"{position}-1c"
        # if the next character is a space or punctuation, move it to the next position
        if self.get(f"{position}+1c") in (" ", "\n", ",", ".", ";", ":", "!", "?", "-"):
            return f"{position}+1c"

    def replace_selected(self, new_text, tag=None):
        # if textbox is disabled, configure it to be enabled
        start, end = self.selected_range()
        self.replace_range(start, end, new_text, tag=tag)

    def replace_tag(self, new_text, old_tag, new_tag=None):
        ranges = self.tag_ranges(old_tag)
        start = ranges[0]
        end = ranges[1]
        self.replace_range_tk(start, end, new_text, tag=new_tag)

    def replace_range_tk(self, start_idx, end_idx, new_text, tag=None):
        changed_state = False
        if self.cget("state") == "disabled":
            self.configure(state="normal")
            changed_state = True
        self.delete(start_idx, end_idx)
        if tag:
            self.insert(start_idx, new_text, tag)
        else:
            self.insert(start_idx, new_text)
        if changed_state:
            self.configure(state="disabled")

    def replace_range(self, start, end, new_text, tag=None):
        changed_state = False
        if self.cget("state") == "disabled":
            self.configure(state="normal")
            changed_state = True
        self.delete(f"1.0 + {start} chars", f"1.0 + {end} chars")
        if tag:
            self.insert(f"1.0 + {start} chars", new_text, tag)
        else:
            self.insert(f"1.0 + {start} chars", new_text)
        if changed_state:
            self.configure(state="disabled")
        self.fix_ranges(start=start, old_end=end, new_end=start+len(new_text))

    def selected_inputs(self):
        inputs = {}
        inputs['past_context'] = self.get("1.0", "sel.first")
        inputs['input'] = self.selected_text()
        inputs['future_context'] = self.get("sel.last", "end")
        return inputs

    def alt_dropdown(self, alt_dict, show_probs=True):
        start_pos = alt_dict['replace_range'][0]
        end_pos = alt_dict['replace_range'][1]
        # select range
        #self.select_range(start_pos, end_pos)
        self.tag_range("alternate", start_pos, end_pos)
        # get x y coordinates of start_pos
        start_index = self.index(f"1.0 + {start_pos} chars")
        x, y = self.count("1.0", start_index, "xpixels", "ypixels")
        # TODO adjust based on font size
        x = x + self.winfo_rootx() + 5
        y = y + self.winfo_rooty() + 45
        # get Text scroll position
        scroll_pos = self.yview()[0]
        # get Text height
        text_height = self.winfo_height()
        scroll_offset = int(round(scroll_pos * text_height))

        y = y - scroll_offset

        # create dropdown menu
        menu = tk.Menu(self, tearoff=0)

        current_text = self.get(f"1.0 + {start_pos} chars", f"1.0 + {end_pos} chars")
        
        for alt in alt_dict['alts']:
            text = repr(alt['text'])
            color = "blue" if text == current_text else "white"
            if 'prob' in alt and show_probs:
                text += f" ({alt['prob']:.3f})"
            menu.add_command(label=text, foreground=color, 
                             command=lambda alt=alt: self.replace_range(start_pos, 
                                                                        end_pos, 
                                                                        alt['text'],
                                                                        tag="alternate"))

        menu.add_separator()
        # display current text

        menu.tk_popup(x, y)
    
    def fix_ranges(self, start, old_end, new_end):
        """
        fix text ranges for alternatives after a substitution.
        """
        shift = new_end - old_end
        for alt in self.alternatives:
            if alt['replace_range'][0] > start:
                alt['replace_range'][0] += shift
            if alt['replace_range'][1] >= start:
                alt['replace_range'][1] += shift


    def get_alt_dict(self, position):
        for alt_dict in self.alternatives:
            if alt_dict['replace_range'][0] <= position <= alt_dict['replace_range'][1]:
                return alt_dict
        return None

    def open_alt_dropdown(self, event):
        position = len(self.get("1.0", tk.CURRENT))
        alt_dict = self.get_alt_dict(position)
        if alt_dict:
            self.alt_dropdown(alt_dict)


#################################
#   Settings
#################################

class Settings:
    def __init__(self, orig_params, realtime_update=False, parent_module=None):
        self.orig_params = orig_params
        self.realtime_update = realtime_update
        self.parent_module = parent_module
        self.vars = {}
        self.textboxes = {}
        self.frame = None
        self.master = None

    def body(self, master):
        self.master = master
        self.frame = ttk.Frame(self.master)
        self.frame.pack(fill=tk.BOTH, expand=True)

    def init_vars(self):
        for key in self.vars.keys():
            self.vars[key] = self.vars[key](value=self.orig_params[key])
            self.vars[key].trace("w", lambda a, b, c, key=key: self.set_var(key=key))
    
    def set_var(self, key):
        if self.realtime_update:
            self.write()

    def write(self):
        for key in self.vars.keys():
            self.orig_params[key] = self.vars[key].get()

    def reset_vars(self):
        for key in self.vars.keys():
            self.vars[key].set(self.orig_params[key])

    def key_pressed(self, event):
        if event.keysym == 'Tab' or event.keysym == 'Return':
            self.frame.focus()
            return "break"

    def create_textbox(self, name, label_text=None):
        row = self.frame.grid_size()[1]
        label_text = label_text if label_text else name + ' text'
        create_side_label(self.frame, label_text, row)
        self.textboxes[name] = TextAware(self.frame, height=1, width=20)
        self.textboxes[name].grid(row=row, column=1)
        self.textboxes[name].bind("<Key>", self.key_pressed)
        self.textboxes[name].bind("<FocusOut>", lambda event, name=name: self.get_text(key=name))
        if self.parent_module:
            self.parent_module.textboxes.append(self.textboxes[name])

    def get_text(self, key):
        self.vars[key].set(self.textboxes[key].get(1.0, "end-1c"))


    def create_dropdown(self, var, label_text, options):
        row = self.frame.grid_size()[1]
        create_side_label(self.frame, label_text, row)
        dropdown = tk.OptionMenu(self.frame, self.vars[var], *options)
        dropdown.grid(row=row, column=1, pady=3)

    def destroy(self):
        self.frame.pack_forget()
        self.frame.destroy()


class FrameSettings(Settings):
    def __init__(self, orig_params, user_params, settings_key, state, realtime_update=False, parent_module=None):
        Settings.__init__(self, orig_params, realtime_update, parent_module)
        self.user_params = user_params
        self.settings_key = settings_key
        self.state = state
        self.updates = {}
        self.pin_buttons = {}

    def set_var(self, key):
        if key not in self.updates:
            self.pin_var(key)
        else:
            self.updates[key] = self.vars[key].get()
        Settings.set_var(self, key)
        
    def unpin_var(self, key):
        # unpin button
        # reset var to original value
        # remove from updates dict
        if key in self.pin_buttons:
            self.vars[key].set(self.orig_params[key])
            self.updates.pop(key)
            self.pin_buttons[key].configure(image=icons.get_icon("square-black"))

    def pin_var(self, key):
        # pin button
        # add to updates dict
        if key in self.pin_buttons:
            self.pin_buttons[key].configure(image=icons.get_icon("pin-red"))
            self.updates[key] = self.vars[key].get()

    def toggle_pin(self, key):
        if key in self.updates:
            self.unpin_var(key)
        else:
            self.pin_var(key)

    def write(self):
        # overrides Settings.write()
        self.write_user_frame()

    def write_user_frame(self):
        # write updates to user state
        print('writing user frame')
        print(self.updates)
        self.state.set_user_frame_partial(value=self.updates, path=[self.settings_key])

    def write_to_frame(self):
        # write updates to node frame and remove pins & remove from user state
        self.state.set_frame_partial(node=self.state.selected_node, value=self.updates, path=[self.settings_key])        
        for key in self.pin_buttons.keys():
            self.unpin_var(key)
            self.vars[key].set(self.orig_params[key])
        self.updates = {}

    def set_pins(self):
        # pin variables that are in user state
        # and add to updates dict
        for key in self.vars.keys():
            if key in self.user_params:
                self.pin_var(key)

    def reset_vars(self):
        Settings.reset_vars(self)
        self.set_pins()

    def build_pin_button(self, key, row=None):
        row = row if row else self.frame.grid_size()[1] - 1
        self.pin_buttons[key] = tk.Label(self.frame, image=icons.get_icon("square-black"),
                                         cursor="hand2")
        self.pin_buttons[key].grid(row=row, column=2)
        self.pin_buttons[key].bind("<Button-1>", lambda event, key=key: self.toggle_pin(key))


class ExportOptions(Settings):
    def __init__(self, orig_params, realtime_update=False, parent_module=None):
        Settings.__init__(self, orig_params, realtime_update, parent_module)
        self.vars = {
            'subtree_only': tk.BooleanVar,
            'visible_only': tk.BooleanVar,
            'root_frame': tk.BooleanVar,
            'frames': tk.BooleanVar,
            'tags': tk.BooleanVar,
            'text_attributes': tk.BooleanVar,
            'multimedia': tk.BooleanVar,
            'chapters': tk.BooleanVar
        }

    def body(self, master):
        Settings.body(self, master)
        self.init_vars()
        create_checkbutton(self.frame, "Subtree only", "subtree_only", self.vars)
        create_checkbutton(self.frame, "Visible only", "visible_only", self.vars)
        create_checkbutton(self.frame, "Export root frame", "root_frame", self.vars)
        create_checkbutton(self.frame, "Export frames", "frames", self.vars)
        create_checkbutton(self.frame, "Export tags", "tags", self.vars)
        create_checkbutton(self.frame, "Export text attributes", "text_attributes", self.vars)
        create_checkbutton(self.frame, "Export multimedia", "multimedia", self.vars)
        create_checkbutton(self.frame, "Export chapters", "chapters", self.vars)


class Preferences(FrameSettings):
    def __init__(self, orig_params, user_params, state, realtime_update=False, parent_module=None):
        FrameSettings.__init__(self, orig_params, user_params, "preferences", state, realtime_update, parent_module)
        self.vars = {
            "reverse": tk.BooleanVar,

            "nav_tag": tk.StringVar,
            "walk": tk.StringVar,

            "bold_prompt": tk.BooleanVar,
            "coloring": tk.StringVar,
            "font_size": tk.IntVar,
            "line_spacing": tk.IntVar,
            "paragraph_spacing": tk.IntVar,

            "autosave": tk.BooleanVar,
            "model_response": tk.StringVar,
            
            "prob": tk.BooleanVar,
        }
        self.write_to_frame_button = None
        self.init_vars()

    def body(self, master):
        FrameSettings.body(self, master)
        create_label(self.frame, "Nav tree")

        create_checkbutton(self.frame, "Reverse node order", "reverse", self.vars)
        self.build_pin_button("reverse")

        create_label(self.frame, "Navigation")

        self.create_dropdown("nav_tag", "A/D to navigate tag", self.state.tags.keys())
        self.build_pin_button("nav_tag")

        self.create_dropdown("walk", "Walk", ['descendents', 'leaves', 'uniform'])
        self.build_pin_button("walk")

        create_label(self.frame, "Story frame")

        create_checkbutton(self.frame, "Bold prompt", "bold_prompt", self.vars)
        self.build_pin_button("bold_prompt")

        self.create_dropdown("coloring", "Text coloring", ['edit', 'read', 'none'])
        self.build_pin_button("coloring")

        create_slider(self.frame, "Font size", self.vars["font_size"], (5, 20))
        self.build_pin_button("font_size")

        create_slider(self.frame, "Line spacing", self.vars["line_spacing"], (0, 20))
        self.build_pin_button("line_spacing")

        create_slider(self.frame, "Paragraph spacing", self.vars["paragraph_spacing"], (0, 40))
        self.build_pin_button("paragraph_spacing")

        create_label(self.frame, "Saving")

        create_checkbutton(self.frame, "Autosave", "autosave", self.vars)
        self.build_pin_button("autosave")

        self.create_dropdown("model_response", "Save model response?", ['backup', 'save', 'discard'])
        self.build_pin_button("model_response")

        create_label(self.frame, "Generation")
        
        create_checkbutton(self.frame, "Show logprobs as probs", "prob", self.vars)
        self.build_pin_button("prob")

        self.write_to_frame_button = tk.Button(self.frame, text="Write to frame", command=self.write_to_frame)
        self.write_to_frame_button.grid(row=self.frame.grid_size()[1], column=1, pady=3)

        self.set_pins()
    

def generation_settings_init(self):
    self.vars = {
            "model": tk.StringVar,
            'num_continuations': tk.IntVar,
            'temperature': tk.DoubleVar,
            'top_p': tk.DoubleVar,
            'response_length': tk.IntVar,
            'prompt_length': tk.IntVar,
            'logprobs': tk.IntVar,
            'stop': tk.StringVar,
            'logit_bias': tk.StringVar,
        }
    self.textboxes = {'stop': None,
                    'logit_bias': None}
    self.init_vars()


def full_generation_settings_init(self):
    additional_vars = {
            'start': tk.StringVar,
            'restart': tk.StringVar,
            'global_context': tk.StringVar,
            'template': tk.StringVar,
            'post_template': tk.StringVar,
            'preset': tk.StringVar,
        }
    for key in additional_vars.keys():
        self.vars[key] = additional_vars[key](value=self.orig_params[key])
        self.vars[key].trace("w", lambda a, b, c, key=key: self.set_var(key=key))
    
    self.textboxes.update({'start': None,
                            'restart': None,})

    self.context_textbox = None
    self.template_label = None
    self.template_filename_label = None
    self.preset_dropdown = None


def generation_settings_body(self, build_pins=False):
    create_combo_box(self.frame, "model", self.vars["model"], POSSIBLE_MODELS, width=15)
    if build_pins:
        self.build_pin_button("model")

    sliders = {
        'num_continuations': (1, 20),
        'temperature': (0., 1.),
        'top_p': (0., 1.),
        'response_length': (1, 1000),
        'prompt_length': (100, 10000),
        'logprobs': (0, 100),
    }
    for name, value_range in sliders.items():
        create_slider(self.frame, name, self.vars[name], value_range)
        if build_pins:
            self.build_pin_button(name)

    for name in self.textboxes:
        self.create_textbox(name)
        if build_pins:
            self.build_pin_button(name)
    self.set_textboxes()
    if build_pins:
        self.set_pins()


def generation_settings_templates_body(self, build_pins=False):

    # TODO use grid
    # self.context_frame = CollapsableFrame(self.frame, title="global prepended context", bg=bg_color())
    # self.context_frame.pack(side="top", fill="both", expand=True, pady=10)
    row = self.frame.grid_size()[1]
    self.context_textbox = TextAware(self.frame, height=4, width=30)
    self.context_textbox.configure(**textbox_config())
    self.context_textbox.grid(row=row, column=0, columnspan=2)
    self.context_textbox.bind("<Key>", self.key_pressed)
    self.context_textbox.bind("<FocusOut>", lambda event: self.get_context())
    self.set_context()
    if self.parent_module:
        self.parent_module.textboxes.append(self.context_textbox)
    if build_pins:
        self.build_pin_button('global_context')

    # self.templates_frame = CollapsableFrame(self.frame, title="templates", bg=bg_color())
    # self.templates_frame.pack(side="top", fill="both", expand=True, pady=10)

    row = self.frame.grid_size()[1]
    self.template_label = create_side_label(self.frame, "template")
    self.template_filename_label = create_side_label(self.frame, self.vars['template'].get(), row=row, col=1)
    self.vars['template'].trace("w", self.set_template)
    if build_pins:
        self.build_pin_button('template')

    row = self.frame.grid_size()[1]
    self.preset_label = create_side_label(self.frame, "preset")
    
    # load presets into options
    with open('./config/generation_presets/presets.json') as f:
        self.presets_dict = json.load(f)

    # if custom presets json exists, also append it to presets dict and options
    if os.path.isfile('./config/generation_presets/custom_presets.json'):
        with open('./config/generation_presets/custom_presets.json') as f:
            self.presets_dict.update(json.load(f))

    # when the preset changes, apply the preset
    self.vars['preset'].trace('w', self.apply_preset)

    self.preset_dropdown = tk.OptionMenu(self.frame, self.vars["preset"], "Select preset...")
    self.preset_dropdown.grid(row=row, column=1)
    self.set_options()
    if build_pins:
        self.build_pin_button('preset')

    row = self.frame.grid_size()[1]
    create_button(self.frame, "Load template", self.load_template, column=0, width=12)
    create_button(self.frame, "Save preset", self.save_preset, column=0)
    #create_button(master, "Reset", self.reset_variables)

    if build_pins:
        self.write_to_frame_button = tk.Button(self.frame, text="Write to frame", command=self.write_to_frame)
        self.write_to_frame_button.grid(row=self.frame.grid_size()[1], column=1, pady=3)

    if build_pins:
        self.set_pins()


class SpecialGenerationSettings(Settings):
    def __init__(self, orig_params, realtime_update=False, parent_module=None):
        Settings.__init__(self, orig_params, realtime_update, parent_module)
        generation_settings_init(self)

    def body(self, master):
        Settings.body(self, master)
        generation_settings_body(self, build_pins=False)

    def reset_vars(self):
        Settings.reset_vars(self)
        self.set_textboxes()

    def set_textboxes(self):
        for name in self.textboxes:
            self.textboxes[name].delete(1.0, "end")
            self.textboxes[name].insert(1.0, self.decode(name))

    def decode(self, name):
        decoded_string = codecs.decode(self.vars[name].get(), "unicode-escape")
        repr_string = repr(decoded_string)
        repr_noquotes = repr_string[1:-1]
        return repr_noquotes


class GenerationSettings(FrameSettings, SpecialGenerationSettings):
    def __init__(self, orig_params, user_params=None, state=None, realtime_update=False, parent_module=None):
        FrameSettings.__init__(self, orig_params, user_params, "generation_settings", state, realtime_update, parent_module)
        generation_settings_init(self)
        #init_generation_settings(self)
        #self.init_vars()

    def body(self, master):
        FrameSettings.body(self, master)
        generation_settings_body(self, build_pins=True)

    def write(self):
        FrameSettings.write(self)


class SpecialFullGenerationSettings(SpecialGenerationSettings):
    def __init__(self, orig_params, realtime_update=False, parent_module=None):
        SpecialGenerationSettings.__init__(self, orig_params, realtime_update, parent_module)
        full_generation_settings_init(self)

    def body(self, master):
        FrameSettings.body(self, master)
        generation_settings_body(self, build_pins=False)
        generation_settings_templates_body(self, build_pins=False)

    def set_context(self):
        self.context_textbox.delete(1.0, "end")
        self.context_textbox.insert(1.0, self.vars['global_context'].get())

    def get_context(self):
        self.vars['global_context'].set(self.context_textbox.get(1.0, "end-1c"))

    def set_template(self, *args):
        self.template_filename_label.config(text=self.vars['template'].get())

    def load_template(self):
        file_path = filedialog.askopenfilename(
            initialdir="./config/prompts",
            title="Select prompt template",
            filetypes=[("Text files", ".txt")]
        )
        if file_path:
            filename = os.path.splitext(os.path.basename(file_path))[0]
            self.vars['template'].set(filename)

    def set_options(self):
        options = [p['preset'] for p in self.presets_dict.values()]
        menu = self.preset_dropdown['menu']
        menu.delete(0, 'end')
        for option in options:
            menu.add_command(label=option, command=tk._setit(self.vars['preset'], option))

    def get_all(self):
        for key in self.textboxes:
            self.get_text(key)
        self.get_context()

    def settings_copy(self):
        settings = {}
        for key in self.vars.keys():
            settings[key] = self.vars[key].get()
        return settings

    def apply_preset(self, *args):
        new_preset = self.presets_dict[self.vars["preset"].get()]
        for key, value in new_preset.items():
            self.vars[key].set(value)
        self.set_textboxes()
        self.set_context()

    def save_preset(self, *args):
        preset_name = tk.simpledialog.askstring("Save preset", "Enter preset name")
        if preset_name is None:
            return
        
        self.get_all()
        settings_copy = self.settings_copy()
        settings_copy['preset'] = preset_name
        self.presets_dict[preset_name] = settings_copy

        self.set_options()
        self.vars['preset'].set(preset_name)

        # make custom_presets json if it doesn't exist
        if not os.path.isfile('./config/generation_presets/custom_presets.json'):
            with open('./config/generation_presets/custom_presets.json', 'w') as f:
                json.dump({}, f)
        # append new presets to json
        with open('./config/generation_presets/custom_presets.json') as f:
            custom_dict = json.load(f)
        custom_dict[preset_name] = self.presets_dict[preset_name]
        with open('./config/generation_presets/custom_presets.json', 'w') as f:
            json.dump(custom_dict, f)


class FullGenerationSettings(FrameSettings, SpecialFullGenerationSettings):
    def __init__(self, orig_params, user_params=None, state=None, realtime_update=False, parent_module=None):
        FrameSettings.__init__(self, orig_params, user_params, "generation_settings", state, realtime_update, parent_module)
        generation_settings_init(self)
        full_generation_settings_init(self)

    def body(self, master):
        FrameSettings.body(self, master)
        generation_settings_body(self, build_pins=True)
        generation_settings_templates_body(self, build_pins=True)

    def write(self):
        FrameSettings.write(self)

# class FullGenerationSettings(GenerationSettings):
#     def __init__(self, orig_params, user_params, state, realtime_update=False, parent_module=None):
#         GenerationSettings.__init__(self, orig_params, user_params, state, realtime_update=realtime_update, parent_module=parent_module)
#         additional_vars = {
#             'start': tk.StringVar,
#             'restart': tk.StringVar,
#             'global_context': tk.StringVar,
#             'template': tk.StringVar,
#             'post_template': tk.StringVar,
#             'preset': tk.StringVar,
#         }
#         for key in additional_vars.keys():
#             self.vars[key] = additional_vars[key](value=self.orig_params[key])
#             self.vars[key].trace("w", lambda a, b, c, key=key: self.set_var(key=key))
        
#         self.textboxes.update({'start': None,
#                                'restart': None,})

#         self.context_textbox = None
#         self.template_label = None
#         self.template_filename_label = None
#         self.preset_dropdown = None
#         self.write_to_frame_button = None

#     def body(self, master):
#         GenerationSettings.body(self, master)

#         self.write_to_frame_button = tk.Button(self.frame, text="Write to frame", command=self.write_to_frame)
#         self.write_to_frame_button.grid(row=self.frame.grid_size()[1], column=1, pady=3)

#         # TODO use grid
#         self.context_frame = CollapsableFrame(master, title="global prepended context", bg=bg_color())
#         self.context_frame.pack(side="top", fill="both", expand=True, pady=10)
#         self.context_textbox = TextAware(self.context_frame.collapsable_frame, height=4, width=30)
#         self.context_textbox.configure(**textbox_config())
#         self.context_textbox.pack(side="top", fill="both", expand=True)
#         self.context_textbox.bind("<Key>", self.key_pressed)
#         self.context_textbox.bind("<FocusOut>", lambda event: self.get_context())
#         self.set_context()
#         #self.build_pin_button('global_context')

#         self.templates_frame = CollapsableFrame(master, title="templates", bg=bg_color())
#         self.templates_frame.pack(side="top", fill="both", expand=True, pady=10)

#         self.template_label = create_side_label(self.templates_frame.collapsable_frame, "template")
#         self.template_filename_label = create_side_label(self.templates_frame.collapsable_frame, self.vars['template'].get(), row=0, col=1)
#         self.vars['template'].trace("w", self.set_template)
#         #self.build_pin_button('template')

#         create_side_label(self.templates_frame.collapsable_frame, "preset", row=2, col=0)
        
#         # load presets into options
#         with open('./config/generation_presets/presets.json') as f:
#             self.presets_dict = json.load(f)

#         # if custom presets json exists, also append it to presets dict and options
#         if os.path.isfile('./config/generation_presets/custom_presets.json'):
#             with open('./config/generation_presets/custom_presets.json') as f:
#                 self.presets_dict.update(json.load(f))

#         # when the preset changes, apply the preset
#         self.vars['preset'].trace('w', self.apply_preset)

#         self.preset_dropdown = tk.OptionMenu(self.templates_frame.collapsable_frame, self.vars["preset"], "Select preset...")
#         self.preset_dropdown.grid(row=2, column=1)
#         self.set_options()
#         #self.build_pin_button('preset')

#         create_button(self.templates_frame.collapsable_frame, "Load template", self.load_template, row=1, column=0, width=12)
#         create_button(self.templates_frame.collapsable_frame, "Save preset", self.save_preset, row=3, column=0)
#         #create_button(master, "Reset", self.reset_variables)

#         # TODO these don't work
#         # if context is empty, hide the frame
#         if not self.vars['global_context'].get():
#             self.context_frame.hide()
        
#         # if preset is default, hide the frame
#         if self.vars['preset'].get() == 'Default':
#             self.templates_frame.hide()

#         #self.set_pins()

#     def set_context(self):
#         self.context_textbox.delete(1.0, "end")
#         self.context_textbox.insert(1.0, self.vars['global_context'].get())

#     def get_context(self):
#         self.vars['global_context'].set(self.context_textbox.get(1.0, "end-1c"))

#     def set_template(self, *args):
#         self.template_filename_label.config(text=self.vars['template'].get())

#     def load_template(self):
#         file_path = filedialog.askopenfilename(
#             initialdir="./config/prompts",
#             title="Select prompt template",
#             filetypes=[("Text files", ".txt")]
#         )
#         if file_path:
#             filename = os.path.splitext(os.path.basename(file_path))[0]
#             self.vars['template'].set(filename)

#     def set_options(self):
#         options = [p['preset'] for p in self.presets_dict.values()]
#         menu = self.preset_dropdown['menu']
#         menu.delete(0, 'end')
#         for option in options:
#             menu.add_command(label=option, command=tk._setit(self.vars['preset'], option))

#     def get_all(self):
#         for key in self.textboxes:
#             self.get_text(key)
#         self.get_context()

#     def settings_copy(self):
#         settings = {}
#         for key in self.vars.keys():
#             settings[key] = self.vars[key].get()
#         return settings

#     def apply_preset(self, *args):
#         new_preset = self.presets_dict[self.vars["preset"].get()]
#         for key, value in new_preset.items():
#             self.vars[key].set(value)
#         self.set_textboxes()
#         self.set_context()

#     def save_preset(self, *args):
#         preset_name = tk.simpledialog.askstring("Save preset", "Enter preset name")
#         if preset_name is None:
#             return
        
#         self.get_all()
#         settings_copy = self.settings_copy()
#         settings_copy['preset'] = preset_name
#         self.presets_dict[preset_name] = settings_copy

#         self.set_options()
#         self.vars['preset'].set(preset_name)

#         # make custom_presets json if it doesn't exist
#         if not os.path.isfile('./config/generation_presets/custom_presets.json'):
#             with open('./config/generation_presets/custom_presets.json', 'w') as f:
#                 json.dump({}, f)
#         # append new presets to json
#         with open('./config/generation_presets/custom_presets.json') as f:
#             custom_dict = json.load(f)
#         custom_dict[preset_name] = self.presets_dict[preset_name]
#         with open('./config/generation_presets/custom_presets.json', 'w') as f:
#             json.dump(custom_dict, f)
