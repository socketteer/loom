from view.panes import Module
import tkinter as tk
from tkinter import Canvas, ttk, simpledialog, messagebox
from view.colors import text_color, bg_color, edit_color, vis_bg_color
from util.custom_tks import TextAware
from util.util_tree import tree_subset, limited_branching_tree, limited_distance_tree, flatten_tree, collapsed_wavefunction
from util.react import react_changes, unchanged
from util.canvas_util import move_object
from util.gpt_util import logprobs_to_probs
from view.icons import Icons
from view.styles import textbox_config, code_textbox_config
from components.templates import *
from view.tree_vis import round_rectangle
from pprint import pformat, pprint
from gpt import completions_text, gen
from metaprocess import metaprocesses, execute_metaprocess, save_metaprocess
import uuid
import threading
from tkinter.colorchooser import askcolor
from PIL import Image, ImageTk
import os
import json

from components.block_multiverse import BlockMultiverse

icons = Icons()



class Paint(Module):

    DEFAULT_PEN_SIZE = 5.0
    DEFAULT_COLOR = 'black'


    def __init__(self, callbacks, state):
        self.root = None
        self.undo_button = None
        self.redo_button = None
        self.pen_button = None
        self.brush_button = None
        self.eraser_button = None
        self.size_slider = None
        self.current_color = None
        self.past_opacity_slider = None
        self.add_layer_button = None
        self.clear_button = None
        self.add_media_button = None
        self.save_button = None
        self.save_as_button = None
        self.open_button = None
        self.selected_tool = None
        self.past_veil_opacity = None
        self.future_veil_opacity = None
        self.past_recursive_veil_opacity = tk.DoubleVar()
        self.future_recursive_veil_opacity = None
        self.layer_index = None
        self.c = None
        self.current_line = []
        self.lines = []
        self.undo_lines = []
        self.layers = []
        self.thumbnails = None
        self.layers_frame = None
        working_dir = str(os.getcwd())
        self.blank_file = os.path.join(working_dir, "static/media/blank.png")
        Module.__init__(self, 'paint', callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.root = tk.Frame(self.frame, bg=bg_color())
        self.root.pack(side="left", fill="both", expand=True)

        tk.Grid.rowconfigure(self.root, 1, weight=1)
        # for i in range(6):
        #     tk.Grid.columnconfigure(self.root, i, weight=1)

        self.undo_button = tk.Label(self.root, image=icons.get_icon("undo-white", size=20), bg=bg_color(), cursor="hand2")
        self.undo_button.grid(row=0, column=0)
        self.undo_button.bind("<Button-1>", self.undo)

        #self.redo_button = tk.Label(self.root, image=icons.get_icon("right-white", size=20), bg=bg_color(), cursor="hand2")
        #self.redo_button.grid(row=0, column=1)
        #self.redo_button.bind("<Button-1>", self.redo)


        self.brush_button = tk.Label(self.root, image=icons.get_icon("brush-white", size=20), bg=bg_color(), cursor="hand2")
        self.brush_button.grid(row=0, column=1)
        self.brush_button.bind('<Button-1>', self.use_brush)

        self.eraser_button = tk.Label(self.root, image=icons.get_icon("eraser-white", size=20), bg=bg_color(), cursor="hand2")
        self.eraser_button.grid(row=0, column=2)
        self.eraser_button.bind('<Button-1>', self.use_eraser)

        self.current_color = tk.Label(self.root, image=icons.get_icon("eyedropper-white"), fg=text_color(), cursor='hand2', bd=3)
        self.current_color.grid(row=0, column=3)
        self.current_color.bind('<Button-1>', self.choose_color)


        self.size_slider = tk.Scale(self.root, from_=1, to=10, orient="horizontal")
        self.size_slider.grid(row=0, column=4)
        self.size_slider.set(3)

        self.past_opacity_slider = tk.Scale(self.root, from_=0, to=1, orient="horizontal", resolution=0.1,
                                            variable=self.past_recursive_veil_opacity)
        self.past_opacity_slider.grid(row=0, column=7)
        self.past_opacity_slider.set(0.2)
        self.past_recursive_veil_opacity.trace('w', self.update_past_veil_opacity)

        self.c = tk.Canvas(self.root, bg='white', width=600, height=600)
        self.c.grid(row=1, columnspan=6)
        self.clear_button = ttk.Button(self.root, text='clear', command=self.clear_canvas)
        self.clear_button.grid(row=2, column=0)

        self.add_media_button = ttk.Button(self.root, text='add node media', command=self.add_node_media)
        self.add_media_button.grid(row=2, column=1)

        self.save_button = ttk.Button(self.root, text='save', command=self.save_as_png)
        self.save_button.grid(row=2, column=2)

        self.save_as_button = ttk.Button(self.root, text='save as', command=self.save_as)
        self.save_as_button.grid(row=2, column=3)

        self.open_button = ttk.Button(self.root, text='open', command=self.open)
        self.open_button.grid(row=2, column=4)

        self.layers_frame = tk.Frame(self.root, bg=bg_color())
        self.layers_frame.grid(row=0, column=7, rowspan=3)
        self.thumbnails = Thumbnails(selection_callback=self.select_layer)
        self.thumbnails.body(self.layers_frame, height=450)

        self.add_layer_button = tk.Label(self.layers_frame, image=icons.get_icon("plus-lightgray", size=20), bg=bg_color(), cursor="hand2")
        self.add_layer_button.pack()
        self.add_layer_button.bind('<Button-1>', self.add_layer)


        self.setup()
        #self.root.mainloop()

    def populate_thumbnails(self):
        self.thumbnails.clear()
        self.thumbnails.update_thumbnails([layer['filename'] for layer in self.layers])
        # if 'multimedia' in self.state.selected_node:
        #     self.thumbnails.update_thumbnails([media['file'] for media in self.state.selected_node['multimedia']])

    def setup(self):
        self.clear_canvas()
        self.past_veil_opacity = 1
        self.future_veil_opacity = 1
        #self.past_recursive_veil_opacity = 0
        self.future_recursive_veil_opacity = 0
        #self.layer_index = 0
        self.current_line = []
        self.lines = []
        self.undo_lines = []
        self.layers = []
        self.old_x = None
        self.old_y = None
        self.line_width = self.size_slider.get()
        self.color = self.DEFAULT_COLOR
        #self.eraser_on = False
        #self.active_button = self.pen_button
        self.selected_tool = 'brush'
        self.refresh_color()
        self.refresh_buttons()
        self.open_multimedia()
        self.add_layer()
        self.populate_thumbnails()
        self.change_layer(len(self.layers) - 1)
        self.c.bind('<B1-Motion>', self.paint)
        self.c.bind('<ButtonRelease-1>', self.reset)

    def make_transparent(self, img, opacity=0):
        opacity = int(round(opacity * 255))
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] == 255 and item[1] == 255 and item[2] == 255:
                newData.append((255, 255, 255, opacity))
            else:
                newData.append(item)
        img.putdata(newData)

    # TODO max visible layers
    def update_past_veil_opacity(self, *args):
        past_veil_opacity = self.past_recursive_veil_opacity.get()
        for layer in self.layers:
            self.update_layer_transparency(layer, past_veil_opacity)
            #threading.Thread(target=self.update_layer_transparency, args=(layer, past_veil_opacity)).start()

    def update_layer_transparency(self, layer, opacity):
        img = Image.open(layer['filename'])
        self.make_transparent(img, opacity)
        self.update_layer_image(layer, img)

    def open_multimedia(self):
        if 'multimedia' in self.state.selected_node:
            self.open_layers([media['file'] for media in self.state.selected_node['multimedia']])

    def open(self, transparent=True, *args):
        directory = self.state.tree_dir()
        media_dir = os.path.join(directory, "media")
        filename = filedialog.askopenfilename(initialdir=media_dir, title="Select file",
                                              filetypes=(("png files", "*.png"), ("all files", "*.*")))
        if filename:
            #print(filename)
            self.open_layer(filename, transparent)
            #self.refresh_buttons()

    def add_layer(self):
        # add new blank layer

        self.open_layer(self.blank_file)
        #self.layers.append({'filename': filename, 'img': None, 'canvas_img': None})
        #self.layer_index = len(self.layers) - 1

    def open_layer(self, filename, transparent=True):
        img = Image.open(filename)
        if transparent:
            self.make_transparent(img, opacity=self.past_recursive_veil_opacity.get())
        img = ImageTk.PhotoImage(img)
        new_layer = {'img': img, 'filename': filename}
        # draw layer
        canvas_img = self.c.create_image(0, 0, image=img, anchor=tk.NW)
        new_layer['canvas_img'] = canvas_img
        # add layer to list
        self.layers.append(new_layer)

        #self.change_layer(len(self.layers) - 1)
        #self.layer_index = len(self.layers) - 1
        # move lines in front of layer
        # for line in self.lines:
        #     self.c.lift(line)

    def open_layers(self, filenames):
        for filename in filenames:
            self.open_layer(filename)

    def update_layer_image(self, layer, img):
        img = ImageTk.PhotoImage(img)
        layer['img'] = img
        self.c.itemconfig(layer['canvas_img'], image=img)

    def refresh_layer_image(self, layer, transparent=True):
        filename = layer['filename']
        img = Image.open(filename)
        if transparent:
            self.make_transparent(img, opacity=self.past_recursive_veil_opacity.get())
        self.update_layer_image(layer, img)

    def change_layer(self, idx):
        # TODO keep future layers
       #self.merge_png()
        # show all layers beneath or at idx
        for i in range(0, idx + 1):
            self.c.itemconfigure(self.layers[i]['canvas_img'], state='normal')
        # hide all layers above idx
        for i in range(idx + 1, len(self.layers)):
            self.c.itemconfigure(self.layers[i]['canvas_img'], state='hidden')
        self.layer_index = idx
        self.thumbnails.set_selection(self.layers[idx]['filename'])

    def select_layer(self, filename, *args):
        filename_list = [media['file'] for media in self.state.selected_node['multimedia']]
        if filename in filename_list:
            idx = filename_list.index(filename)
        elif filename == self.blank_file:
            idx = len(self.layers) - 1
        self.change_layer(idx)

    def hide_layer(self, layer=None):
        if layer is None:
            layer = self.layers[self.layer_index]
        self.c.itemconfigure(layer['canvas_img'], state='hidden')

    def show_layer(self, layer=None):
        if layer is None:
            layer = self.layers[self.layer_index]
        self.c.itemconfigure(layer['canvas_img'], state='normal')

    def merge_png(self, layer=None):
        # merges lines with image of current layer and deletes lines from canvas
        if layer is None:
            layer = self.layers[self.layer_index]
        if layer['filename']:
            layer_filename = layer['filename']
            if layer_filename == self.blank_file:
                filename = None
            else:
                filename = layer_filename
            filename = self.save_as_png(filename)
            self.clear_canvas()
            layer['filename'] = filename
            self.refresh_layer_image(layer)

    def pop_layer(self):
        # merges lines with image of current layer, saves, and deletes layer
        pass

    def delete_layer(self, layer=None):
        # deletes layer without saving
        if layer is None:
            layer = self.layers[self.layer_index]
        self.c.delete(layer['canvas_img'])
        self.layers.pop(self.layer_index)

    def clear_layers(self):
        # deletes all layers
        for layer in self.layers:
            self.c.delete(layer['canvas_img'])
        self.layers = []

    def save_as_png(self, transparent=True, filename=None, *args):
        self.c.update()
        directory = self.state.tree_dir()
        media_dir = os.path.join(directory, "media")
        # if "media" folder doesn't exist in directory, create it
        if not os.path.exists(media_dir):
            os.makedirs(media_dir)
        # TODO only save lines and current layer file
        self.c.postscript(file='tmp.ps', colormode='color')
        img = Image.open('tmp.ps')
        img = img.convert('RGBA')
        if transparent:
            self.make_transparent(img)
        if not filename:
            filename = str(uuid.uuid1()) + '.png'
        filename = os.path.join(media_dir, filename)
        img.save(filename, 'png')
        os.remove('tmp.ps')
        return filename            

    def save_as(self):
        # open dialog asking for filename
        directory = self.state.tree_dir()
        media_dir = os.path.join(directory, "media")
        filename = filedialog.asksaveasfilename(initialdir=media_dir, title="Select file",
                                                filetypes=(("png files", "*.png"), ("all files", "*.*")))
        if filename:
            self.save_as_png(filename=filename)

    def add_node_media(self, layer=None, *args):
        # add layer to node media list
        layer = layer if layer else self.layer_index
        # if current layer has a background image, merge with canvas
        if self.layers[self.layer_index]['filename']:
            filename = self.merge_png()
        else:
            filename = self.save_as_png(transparent=True)
        self.callbacks["Add multimedia"]['callback'](filenames=[filename])
        
    def refresh_cursor(self):
        # change cursor icon to correspond to selected tool
        if self.selected_tool == 'pen':
            self.c.config(cursor="pencil")
        elif self.selected_tool == 'brush':
            self.c.config(cursor="pencil")
        elif self.selected_tool == 'eraser':
            self.c.config(cursor="dot")

    def refresh_color(self):
        self.current_color.config(bg=self.color)

    def use_pen(self, event):
        self.selected_tool = 'pen'
        self.refresh_buttons()

    def use_brush(self, event):
        #self.activate_button(self.brush_button)
        self.selected_tool = 'brush'
        self.refresh_buttons()

    def choose_color(self, event):
        self.eraser_on = False
        self.color = askcolor(color=self.color)[1]
        self.refresh_color()

    def use_eraser(self, event):
        self.selected_tool = 'eraser'
        self.refresh_buttons()

    def refresh_buttons(self):
        if self.selected_tool == 'pen':
            #self.pen_button.config(relief='sunken')
            self.brush_button.config(relief='raised')
            self.eraser_button.config(relief='raised')
        elif self.selected_tool == 'brush':
            #self.pen_button.config(relief='raised')
            self.brush_button.config(relief='sunken')
            self.eraser_button.config(relief='raised')
        else:
            #self.pen_button.config(relief='raised')
            self.brush_button.config(relief='raised')
            self.eraser_button.config(relief='sunken')
        self.refresh_cursor()

    def paint(self, event):
        self.line_width = self.size_slider.get()
        paint_color = 'white' if self.selected_tool == 'eraser' else self.color
        if self.old_x and self.old_y:
            self.current_line.append(self.c.create_line(self.old_x, self.old_y, event.x, event.y,
                               width=self.line_width, fill=paint_color,
                               capstyle="round", smooth=True, splinesteps=36))
        self.old_x = event.x
        self.old_y = event.y

    def undo(self, event):
        if len(self.lines) > 0:
            line_arr = self.lines.pop()
            for line in line_arr:
                # save line options
                self.c.delete(line)
            self.undo_lines.append(line_arr)
    
    def redo(self, event):
        if len(self.undo_lines) > 0:
            line_arr = self.undo_lines.pop()
            for line in line_arr:
                self.c.create_line(line)
            self.lines.append(line_arr)

    def reset(self, event):
        self.lines.append(self.current_line)
        self.current_line = []
        self.old_x, self.old_y = None, None

    def clear_canvas(self, *args):
        self.c.delete("all")

    def tree_updated(self):
        self.open_multimedia()
        self.add_layer()
        self.populate_thumbnails()

    def selection_updated(self):
        self.setup()


class Notes(Module):
    def __init__(self, callbacks, state):
        self.menu_frame = None
        self.new_note_button = None
        self.pinned_frame = None
        self.notes_frame = None
        self.notes = NodeWindows(callbacks, state, buttons=['close', 'go', 'attach', 'archive', 'delete'], max_height=1)
        Module.__init__(self, 'notes', callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.menu_frame = ttk.Frame(self.frame)
        self.menu_frame.pack(side='top')
        self.new_note_button = tk.Label(self.menu_frame, image=icons.get_icon("plus-lightgray"), bg=bg_color(), cursor='hand2')
        self.new_note_button.bind("<Button-1>", self.new_note)
        self.new_note_button.pack(side='right')
        self.pinned_frame = ttk.Frame(self.frame)
        self.notes_frame = ttk.Frame(self.frame)
        self.notes_frame.pack(side='top', fill='both', expand=True)
        self.notes.body(self.notes_frame)
        self.tree_updated()

    # called by controller events
    def tree_updated(self):
        pinned_notes = self.callbacks["Pinned"]["callback"]()
        floating_notes = self.callbacks["Get floating notes"]["callback"]()
        self.notes.update_windows(pinned_notes + floating_notes)
        #self.notes.update_windows(pinned_notes + floating_notes, insert='front')
        self.notes.update_text()
        self.textboxes = [window['textbox'] for window in self.notes.windows.values()]

    def selection_updated(self):
        self.notes.save_windows()
        self.tree_updated()

    def new_note(self, *args):
        new_note = self.callbacks["New note"]["callback"]()


class Children(Module):
    def __init__(self, callbacks, state):
        self.menu_frame = None
        self.add_child_button = None
        self.toggle_hidden_button = None
        self.show_hidden = False
        Module.__init__(self, 'children', callbacks, state)
        self.children = NodeWindows(callbacks, state, buttons=['close', 'go', 'edit', 'archive', 'delete'],
                                    buttons_visible=True,
                                    editable=False,
                                    max_height=100,
                                    toggle_tag=self.toggle_tag)


    def build(self, parent):
        Module.build(self, parent)
        self.children.body(self.frame)
        self.menu_frame = ttk.Frame(self.frame)
        self.menu_frame.pack(side='bottom')
        self.add_child_button = tk.Label(self.menu_frame, image=icons.get_icon("plus-lightgray"), bg=bg_color(), cursor='hand2')
        self.add_child_button.bind("<Button-1>", self.add_child)
        self.add_child_button.pack(side='left', padx=20)
        self.tree_updated()

    def destroy_show_hidden_button(self):
        if self.toggle_hidden_button:
            self.toggle_hidden_button.pack_forget()
            self.toggle_hidden_button.destroy()
        self.toggle_hidden_button = None

    def create_show_hidden_button(self):
        self.toggle_hidden_button = tk.Label(self.menu_frame, bg=bg_color(), fg=text_color(), cursor='hand2')
        self.toggle_hidden_button.bind("<Button-1>", self.toggle_hidden)
        self.toggle_hidden_button.pack(side='left', padx=20)
        self.toggle_hidden_button["compound"] = tk.LEFT

    def toggle_tag(self):
        return self.settings()['toggle_tag']

    def tree_updated(self):
        # if not self.children.windows_pane:
        #     self.build()
        if not self.children.scroll_frame:
            print('not built')
            return
        self.children.save_windows()
        children = self.callbacks["Get children"]["callback"]()
        self.children.update_windows(children)
        self.children.update_text()
        num_hidden = len(self.callbacks["Hidden children"]["callback"]())
        self.textboxes = [window['textbox'] for window in self.children.windows.values()]

        if not self.toggle_hidden_button:
            self.create_show_hidden_button()
        if not self.show_hidden:
            if num_hidden > 0:
                self.toggle_hidden_button['image'] = icons.get_icon("visible-lightgray")
                self.toggle_hidden_button['text'] = f' reveal {num_hidden} hidden children'
            else:
                self.destroy_show_hidden_button()
        else:
            self.toggle_hidden_button['image'] = icons.get_icon("invisible-lightgray")
            self.toggle_hidden_button['text'] = f' hide {num_hidden} hidden children'
            
    def selection_updated(self):
        #self.children.save_windows()
        self.tree_updated()

    def add_child(self, *args):
        child = self.callbacks["New Child"]["callback"](update_selection=False)
        #pprint(self.children.windows)
        self.children.edit_on(child['id'])
        self.children.focus_textbox(child['id'])
        
        

    def toggle_hidden(self, *args):
        self.show_hidden = not self.show_hidden
        if self.show_hidden:
            self.callbacks["Show hidden children"]["callback"]()
        else:
            self.callbacks["Hide invisible children"]["callback"]()


class ReadChildren(Module):
    def __init__(self, callbacks, state):
        self.children = []
        self.scroll_frame = None
        self.continue_option = None
        Module.__init__(self, 'read children', callbacks, state)
    
    def build(self, parent):
        Module.build(self, parent)
        self.scroll_frame = ScrollableFrame(self.frame)
        self.scroll_frame.pack(side='top', fill='both', expand=True)
        self.refresh()

    def add_child(self, node):
        child_text = self.state.get_text_attribute(node, 'child_preview')
        child_text = child_text if child_text else node['text'][:150]
        child_label = tk.Label(self.scroll_frame.scrollable_frame, text=child_text, bg=bg_color(), fg=text_color(), cursor='hand2', 
                               anchor='w', justify='left', font=('Georgia', 12),
                               image=icons.get_icon('arrow-white', 16), compound=tk.LEFT, padx=10)
        child_label.bind("<Button-1>", lambda event, node=node: self.callbacks["Select node"]["callback"](node=node))
        child_label.bind("<Button-2>", lambda event, node=node: self.context_menu(event=event, node=node))
        child_label.bind("<Button-3>", lambda event, node=node: self.context_menu(event=event, node=node))
        child_label.pack(side='top', fill='x', expand=True, pady=10)
        self.children.append(child_label)

    def build_continue_option(self, text="continue"):
        self.continue_option = tk.Label(self.scroll_frame.scrollable_frame, text=text, bg=bg_color(), fg=text_color(), cursor='hand2',
                               anchor='w', justify='left', font=('Georgia', 12),
                               image=icons.get_icon('arrow-white', 16), compound=tk.LEFT, padx=10)
        self.continue_option.bind("<Button-1>", lambda event: self.walk())
        self.continue_option.pack(side='top', fill='x', expand=True, pady=10)

    def walk(self):
        self.callbacks["Walk"]["callback"](node=self.state.selected_node)

    def filter(self):
        filter_option = self.settings()['filter']
        if filter_option == 'all':
            return None
        elif filter_option == 'in_nav':
            return lambda node: self.callbacks["In nav"]["callback"](node=node)
        else:
            return lambda node: self.state.has_tag(node=node, tag=filter_option)

    def show_continue(self):
        condition = self.settings()['show_continue']
        if condition == 'always':
            return True
        elif condition == 'never':
            return False
        elif condition == 'no alternatives':
            return len(self.children) == 0
        else:
            # TODO
            return True 


    def show_options(self):
        condition = self.settings()['show_options']
        if condition == 'always':
            return True 
        elif condition == 'never':
            return False 
        else:
            return self.state.has_tag(node=self.state.selected_node, tag=condition)


    def refresh(self):
        if self.scroll_frame:
            children_options = self.callbacks["Get children"]["callback"](filter=self.filter()) if self.show_options() else []
            possible_children = self.callbacks["Get children"]["callback"]()
            for child in self.children:
                child.pack_forget()
            self.children = []
            for child in children_options:
                self.add_child(child)

            if self.show_continue() and possible_children:
                if not self.continue_option:
                    self.build_continue_option()
            else:
                if self.continue_option:
                    self.continue_option.pack_forget()
                    self.continue_option = None


    def context_menu(self, event, node):
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="Edit preview text", command=lambda: self.callbacks["Edit in module"]["callback"](node=node, create_attribute='child_preview'))
        menu.tk_popup(event.x_root, event.y_root)


    def selection_updated(self):
        self.refresh()
    
    def tree_updated(self):
        self.refresh()
        #pass



class JanusPlayground(Module):
    def __init__(self, callbacks, state):
        self.generation_frame = None
        self.pane = None
        self.settings_frame = None
        self.settings_control = None
        self.inline_settings_control = None
        self.textbox_frame = None
        self.menu_frame = None
        self.insert_prompt_button = None
        self.generate_button = None
        self.eval_prompt_button = None
        self.export_button = None
        self.settings_button = None
        self.completions_frame = None
        self.completion_windows = Windows(state=state, callbacks=callbacks, buttons=['close', 'append', 'attach'])
        self.inline_completions = None
        self.completion_index = 0
        self.model_response = None
        #self.inserted_range = None
        Module.__init__(self, 'janus/playground', callbacks, state)


    def build(self, parent):
        Module.build(self, parent)
        self.generation_frame = ttk.Frame(self.frame)
        self.generation_frame.pack(side='left', fill='both', expand=True)
        self.settings_frame = ttk.Frame(self.frame)
        self.settings_frame.pack(side='left', fill='both', expand=True)
        self.pane = ttk.Panedwindow(self.generation_frame, orient='vertical')
        self.pane.pack(side='top', fill='both', expand=True)
        self.textbox_frame = ttk.Frame(self.pane)
        self.pane.add(self.textbox_frame, weight=4)

        self.textbox = LoomTerminal(self.textbox_frame, bd=2, height=3)
        self.textbox.pack(side='top', fill='both', expand=True)
        self.textboxes.append(self.textbox)
        self.textbox.configure(**textbox_config(bg=edit_color()))
        #self.textbox.tag_config("generated", font=('Georgia', self.state.preferences['font_size'], 'bold'))
        
        self.textbox.bind("<Key>", self.key_pressed)
        self.textbox.bind("<Alt-i>", self.inline_generate)
        self.textbox.bind("<Command-i>", self.inline_generate)
        self.textbox.bind("<Alt-period>", lambda event: self.insert_inline_completion(step=1))
        self.textbox.bind("<Alt-comma>", lambda event: self.insert_inline_completion(step=-1))
        self.textbox.bind("<Command-period>", lambda event: self.insert_inline_completion(step=1))
        self.textbox.bind("<Command-comma>", lambda event: self.insert_inline_completion(step=-1))
        self.textbox.bind("<Button-2>", self.open_counterfactuals)
        self.textbox.bind("<Button-3>", self.open_counterfactuals)

        self.textbox.focus()
        self.button_frame = ttk.Frame(self.textbox_frame)
        self.button_frame.pack(side='bottom', fill='x')
        self.generate_button = ttk.Button(self.button_frame, text='Insert prompt', image=icons.get_icon("rightarrow-lightgray"),
                                          cursor='hand2', command=self.insert_prompt, compound='left')
        self.generate_button.pack(side='left', expand=True)
        self.generate_button = ttk.Button(self.button_frame, text='Generate', image=icons.get_icon("brain-blue"),
                                          cursor='hand2', command=lambda: self.generate(mode='completions'), compound='left')
        self.generate_button.pack(side='left', expand=True)
        self.eval_prompt_button = ttk.Button(self.button_frame, text='Evaluate prompt', image=icons.get_icon("chart-blue"),
                                             cursor='hand2', command=lambda: self.generate(mode='eval'), compound='left')
        self.eval_prompt_button.pack(side='left', expand=True)
        self.export_button = ttk.Button(self.button_frame, text='Export', cursor='hand2',
                                        command=self.export)
        self.export_button.pack(side='left', expand=True)
        self.settings_button = tk.Label(self.button_frame, image=icons.get_icon("settings-lightgray"), bg=bg_color(),
                                        cursor='hand2')
        self.settings_button.bind("<Button-1>", self.toggle_settings)
        self.settings_button.pack(side='left', expand=True)
        self.completions_frame = ttk.Frame(self.pane)
        self.pane.add(self.completions_frame, weight=1)
        self.completion_windows.body(self.completions_frame)


    def inline_generate(self, *args):
        self.textbox.inline_generate(self.state.inline_generation_settings, self.state.model_config)

    def generate(self, mode='completions', *args):
        prompt = self.textbox.get("1.0", "end-1c")
        settings = self.state.generation_settings
        config = self.state.model_config
        if mode == 'completions':
            # disable generate button
            self.generate_button.configure(state='disabled')
            threading.Thread(target=self.call_model, args=(prompt, settings, config)).start()
        elif mode == 'eval':
            # disable eval button
            self.eval_prompt_button.configure(state='disabled')
            threading.Thread(target=self.call_model_prompt, args=(prompt, settings, config)).start()

    def call_model(self, prompt, settings, model_config):
        response, error = gen(prompt, settings, model_config)
        self.generate_button.configure(state='normal')
        self.textbox.model_response = response
        self.textbox.process_logprobs()
        response_text_list = completions_text(response)
        for completion in response_text_list:
            self.completion_windows.open_window(completion)

    def call_model_prompt(self, prompt, settings, model_config):
        self.textbox.call_model_prompt(prompt, settings, model_config)
        self.eval_prompt_button.configure(state='normal')

    def call_model_inline(self, prompt, settings, selected_range):
        self.textbox.call_model_inline(prompt, settings, selected_range)

    def process_logprobs(self):
        self.textbox.process_logprobs()

    def insert_inline_completion(self, step=1, *args):
        self.textbox.insert_inline_completion(step)

    def open_counterfactuals(self, event):
        return self.textbox.open_alt_dropdown(event)

    def key_pressed(self, event):
        if event.keysym == "Alt_L":
            return

    def export(self, *args):
        pass

    # TODO this goes off the side
    def toggle_settings(self, *args):
        if not self.settings_control:
            self.settings_label = tk.Label(self.settings_frame, text="Generation settings", bg=bg_color())
            self.settings_label.pack(side='top', expand=True)
            self.settings_control = GenerationSettings(orig_settings=self.state.generation_settings,
                                                       realtime_update=True)
            self.settings_control.body(master=self.settings_frame)
            self.inline_settings_label = tk.Label(self.settings_frame, text="Inline generation settings", bg=bg_color())
            self.inline_settings_label.pack(side='top', expand=True)
            self.inline_settings_control = GenerationSettings(orig_settings=self.state.inline_generation_settings,
                                                              realtime_update=True)
            self.inline_settings_control.body(master=self.settings_frame)
        else:
            self.settings_label.destroy()
            self.settings_control.destroy()
            self.settings_control = None
            self.inline_settings_label.destroy()
            self.inline_settings_control.destroy()
            self.inline_settings_control = None


    def insert_prompt(self, *args):
        prompt = self.callbacks["Prompt"]["callback"]()
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", prompt)


class TextEditor(Module):
    def __init__(self, callbacks, state):
        self.textbox = None
        self.export_button = None
        self.attach_button = None
        self.open_button = None
        self.clear_button = None
        self.text = None
        self.button_frame = None
        Module.__init__(self, 'texteditor', callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.textbox = TextAware(self.frame, bd=2, height=3, undo=True)
        self.textboxes.append(self.textbox)
        self.textbox.pack(side='top', fill='both', expand=True)
        self.textbox.configure(**textbox_config(bg=edit_color()))
        self.textbox.focus()
        self.textbox.bind("<FocusOut>", lambda event: self.save_text)
        self.button_frame = ttk.Frame(self.frame)
        self.button_frame.pack(side='bottom', fill='x')
        self.export_button = ttk.Button(self.button_frame, text='Export', command=self.export)
        self.export_button.pack(side='left', padx=5)
        self.open_button = ttk.Button(self.button_frame, text='Open', command=self.open)
        self.open_button.pack(side='left', padx=5)
        self.clear_button = ttk.Button(self.button_frame, text='Clear', command=self.clear)
        self.clear_button.pack(side='left', padx=5)
        self.attach_button = ttk.Button(self.button_frame, text='Attach to tree', command=self.attach)
        self.attach_button.pack(side='left', padx=5)

    def clear(self, *args):
        self.text = None
        self.textbox.delete("1.0", "end")

    def open(self, *args):
        pass

    def attach(self, *args):
        pass

    def export(self, *args):
        pass

    def save_text(self):
        self.text = self.textbox.get("1.0", 'end-1c')

    def tree_updated(self):
        pass

    def selection_updated(self):
        pass


class Prompt(Module):
    def __init__(self, callbacks, state):
        self.edit_button = None
        self.textbox = None
        self.button_frame = None
        Module.__init__(self, 'prompt', callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.textbox = TextAware(self.frame, bd=2, height=3, undo=True)
        self.textboxes.append(self.textbox)
        self.textbox.pack(side='top', fill='both', expand=True)
        self.textbox.configure(**textbox_config())
        self.textbox.configure(state='disabled')
        self.button_frame = ttk.Frame(self.frame)
        self.button_frame.pack(side='bottom', fill='x')
        self.edit_button = ttk.Button(self.button_frame, text='Edit', command=self.edit)
        self.edit_button.pack(side='left', padx=5)
        self.tree_updated()

    def edit(self, *args):
        pass

    def tree_updated(self):
        prompt = self.callbacks["Prompt"]["callback"]()
        self.textbox.configure(state='normal')
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", prompt)
        self.textbox.configure(state='disabled')

    def selection_updated(self):
        self.tree_updated()

class Run(Module):
    def __init__(self, callbacks, state):
        Module.__init__(self, 'run', callbacks, state)
        self.eval_code = EvalCode(self.callbacks["Run"]['prev_cmd'], callbacks)
        self.run_button = None
        self.clear_button = None
        self.button_frame = None

    def build(self, parent):
        Module.build(self, parent)
        self.eval_code.body(self.frame)
        self.textboxes.append(self.eval_code.code_textbox)
        self.button_frame = ttk.Frame(self.frame)
        self.button_frame.pack(side='bottom', fill='x')
        self.clear_button = ttk.Button(self.button_frame, text='Clear', command=self.clear)
        self.clear_button.pack(side='left', padx=5, expand=True)
        self.run_button = ttk.Button(self.button_frame, text='Run', command=self.run)
        self.run_button.pack(side='left', padx=5, expand=True)

    def run(self, *args):
        self.eval_code.apply()

    def clear(self, *args):
        self.eval_code.code_textbox.delete("1.0", "end")


class MiniMap(Module):
    def __init__(self, callbacks, state):
        Module.__init__(self, 'minimap', callbacks, state)
        self.settings_frame = None
        self.minimap_pane = None
        self.canvas = None 
        self.node_coords = {}
        self.levels = {}
        self.nodes = {}
        self.lines = {}
        self.old_node_coords = {}
        self.preview_textbox = None
        self.selected_node = None

    def build(self, parent):
        Module.build(self, parent)
        self.settings_frame = CollapsableFrame(self.frame, title='Minimap settings', bg=bg_color())
        self.minimap_settings = MinimapSettings(orig_params=self.state.module_settings['minimap'], 
                                              user_params=self.state.user_module_settings.get('minimap', {}), 
                                              state=self.state, realtime_update=True, parent_module=self)
        self.minimap_settings.body(self.settings_frame.collapsable_frame)
        self.settings_frame.pack(side='top', fill='both', expand=True)
        self.settings_frame.hide()
        self.minimap_pane = ttk.PanedWindow(self.frame, orient='vertical')
        self.minimap_pane.pack(side='top', fill='both', expand=True)
        self.canvas = tk.Canvas(self.minimap_pane, bg=vis_bg_color())
        self.minimap_pane.add(self.canvas, weight=5)
        #self.canvas.pack(side='top', fill='both', expand=True)
        self.preview_textbox = TextAware(self.minimap_pane, bd=3, height=2)
        self.textboxes.append(self.preview_textbox)
        self.minimap_pane.add(self.preview_textbox, weight=1)
        #self.preview_textbox.pack(side='top', fill='both', expand=True)
        self.preview_textbox.configure(**textbox_config())
        self.preview_textbox.configure(state='disabled', relief='raised')
        self.bind_mouse_events()
        self.refresh()
    
    def tree_updated(self):
        self.refresh()

    def selection_updated(self):
        self.refresh()

    def bind_mouse_events(self):
        def scroll_start(event):
            self.canvas.scan_mark(event.x, event.y)

        def scroll_move(event):
            self.canvas.scan_dragto(event.x, event.y, gain=1)

        self.canvas.bind("<ButtonPress-1>", scroll_start)
        self.canvas.bind("<B1-Motion>", scroll_move)

    def cache(self):
        self.old_node_coords = self.node_coords
        self.old_selected_node = self.selected_node

    def clear(self):
        self.canvas.delete('all')
        self.nodes = {}
        self.lines = {}
        self.reset()
    
    def reset(self):
        self.node_coords = {}
        self.levels = {}


    def refresh(self):
        #print(self.settings())
        self.selected_node = self.state.selected_node
        # self.cache()
        # if self.old_selected_node != self.selected_node:
        #     self.clear()
        # self.reset()
        self.clear()
        root = self.state.root()
        filtered_tree = tree_subset(root, filter=lambda node:self.callbacks["In nav"]["callback"](node=node))
        # FIXME using generate_conditional_tree for filtered_dict causes ancestry out of range error - why?
        filtered_dict = {d['id']: d for d in flatten_tree(filtered_tree)}
        self.ancestry = self.state.ancestry(self.selected_node)
        center_subtree = False
        if self.settings()['prune_mode'] == 'ancestry_dist':
            pruned_tree = limited_branching_tree(self.ancestry, filtered_tree, depth_limit=self.settings()['path_length_limit'])
        elif self.settings()['prune_mode'] == 'selection_dist':
            pruned_tree = limited_distance_tree(filtered_tree, self.selected_node, distance_limit=self.settings()['path_length_limit'], 
                                                node_dict=filtered_dict)
            self.ancestry = self.ancestry[-(self.settings()['path_length_limit'] + 1):]
        elif self.settings()['prune_mode'] == 'wavefunction_collapse':
            pruned_tree = collapsed_wavefunction(self.ancestry, filtered_tree, self.selected_node, depth_limit=self.settings()['path_length_limit'])
            center_subtree = True
        elif self.settings()['prune_mode'] == 'in_nav':
            pruned_tree = filtered_tree
        elif self.settings()['prune_mode'] == 'open_in_nav':
            pruned_tree = tree_subset(filtered_tree, filter=lambda node:self.state.is_root(node) or self.callbacks["Node open"]["callback"](node=self.state.parent(node)))
        else:
            pruned_tree = filtered_tree
        self.compute_tree_coordinates(pruned_tree, 200, 400, level=0)
        self.center_about_ancestry(self.ancestry, x_align=200, center_subtree=center_subtree)
        self.center_y(self.selected_node, 400)
        self.fix_orientation()
        # if self.old_node_coords and self.old_selected_node == self.selected_node:
        #     print('moving nodes')
        #     self.move_nodes()
        # else:
        #     print('draw precomputed')
        self.draw_precomputed_tree(pruned_tree)
        # print('selected node:', self.selected_node)
        self.color_selection(self.selected_node)

    def compute_tree_coordinates(self, root, x, y, level=0):
        self.node_coords[root["id"]] = (x, y)
        if level not in self.levels:
            self.levels[level] = []
        self.levels[level].append(root["id"])
        level_offset = self.settings()['level_offset']
        leaf_offset = self.settings()['leaf_offset']
        leaf_position = x
        next_child_position = x
        for child in root['children']:
            leaf_position = next_child_position
            subtree_offset = self.compute_tree_coordinates(child, next_child_position, y + level_offset, level+1)
            leaf_position += subtree_offset
            next_child_position = leaf_position + leaf_offset
        return leaf_position - x

    def fix_orientation(self):
        if self.settings()["horizontal"]:
            coords = {}
            # if the tree is horizontal, swap x and y coordinates
            for id, value in self.node_coords.items():
                coords[id] = (value[1], value[0])
            self.node_coords = coords

    def draw_precomputed_tree(self, root):
        root_x, root_y = self.node_coords[root["id"]]
        self.draw_node(root['id'], radius=self.settings()['node_radius'], x=root_x, y=root_y)

        for child in root['children']:
            child_x, child_y = self.node_coords[child["id"]]
            self.draw_connector(child['id'], root_x, root_y, child_x, child_y, fill='#000000', width=self.settings()['line_thickness'], 
                                offset=self.settings()['leaf_offset']*5/8,
                                connections='horizontal' if self.settings()['horizontal'] else 'vertical')
            self.draw_precomputed_tree(child)

    def move_nodes(self):
        added_ids, deleted_ids = react_changes(old_components=self.old_node_coords.keys(), new_components=self.node_coords.keys())
        persisting_ids = unchanged(old_components=self.old_node_coords.keys(), new_components=self.node_coords.keys())
        for node_id in persisting_ids:
            old_x, old_y = self.old_node_coords[node_id]
            new_x, new_y = self.node_coords[node_id]
            #dy = new_y - old_y
            #dx = new_x - old_x
            #self.canvas.move(self.nodes[node_id], dx, dy)
            move_object(self.canvas, self.nodes[node_id], (new_x, new_y))


    # TODO center remaining subtree based on extreme x values
    def center_about_ancestry(self, ancestry, x_align, level=0, center_subtree=False):
        if level >= len(ancestry):
            return
        ancestor = ancestry[level]
        ancestor_x, _ = self.node_coords[ancestor['id']]
        offset = ancestor_x - x_align
        for node_id in self.levels[level]:
            self.node_coords[node_id] = (self.node_coords[node_id][0] - offset, self.node_coords[node_id][1])
        if level + 1 < len(ancestry):
            self.center_about_ancestry(ancestry, x_align, level+1, center_subtree)
        else:
            #shift all deeper levels by same offset
            remaining_levels = [self.levels[i] for i in range(level+1, len(self.levels))]
            for l in remaining_levels:
                # center remaning levels based on extreme x coordinates
                x_offsets = [self.node_coords[node_id][0] for node_id in l]
                if center_subtree:
                    x_min = min(x_offsets)
                    x_max = max(x_offsets)
                    x_mid = (x_min + x_max)/2 - x_min
                else:
                    x_mid = 0
                for node_id in l:
                    self.node_coords[node_id] = (self.node_coords[node_id][0] - offset - x_mid, self.node_coords[node_id][1])


    def center_y(self, selected_node, y_align):
        y = self.node_coords[selected_node["id"]][1]
        offset = y - y_align
        for node_id in self.node_coords:
            self.node_coords[node_id] = (self.node_coords[node_id][0], self.node_coords[node_id][1] - offset)

    def draw_circle(self, radius, x, y):
        return self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="black", activefill="white", activeoutline="white", outline="black")

    def draw_connector(self, child_id, x1, y1, x2, y2, fill, width=1, activefill=None, offset=0, smooth=True, connections='horizontal'):
        if connections=='horizontal':
            self.lines[child_id] = self.canvas.create_line(x1, y1, x1 + offset, y1, x2 - offset, y2, x2, y2, smooth=smooth,
                                                fill=fill,
                                                activefill=activefill,
                                                width=width)
        else:
            self.lines[child_id] = self.canvas.create_line(x1, y1, x1, y1 + offset, x2, y2 - offset, x2, y2, smooth=smooth,
                                                fill=fill,
                                                activefill=activefill,
                                                width=width)
        self.canvas.tag_lower(self.lines[child_id])


    def draw_node(self, node_id, radius, x, y):
        node = self.draw_circle(radius, x, y)
        self.nodes[node_id] = node
        self.canvas.tag_bind(node, "<Button-1>", lambda event, node_id=node_id: self.select_node(node_id))
        self.canvas.tag_bind(node, "<Enter>", lambda event, node_id=node_id: self.display_text(node_id))
        self.canvas.tag_bind(node, "<Leave>", self.clear_text)

    def display_text(self, node_id):
        text = self.callbacks["Text"]["callback"](node_id=node_id)
        self.preview_textbox.configure(state="normal")
        self.preview_textbox.delete(1.0, "end")
        self.preview_textbox.insert(1.0, text)
        self.preview_textbox.configure(state="disabled")

    def clear_text(self, *args):
        self.preview_textbox.configure(state="normal")
        self.preview_textbox.delete(1.0, "end")
        self.preview_textbox.configure(state="disabled")

    def color_selection(self, selected_node):
        # color all ancestry nodes blue
        for node in self.ancestry:
            self.canvas.itemconfig(self.nodes[node['id']], fill="blue", outline="blue",)
            if node['id'] in self.lines:
                self.canvas.itemconfig(self.lines[node['id']], fill="blue", width=self.settings()['line_thickness'] + 1)

    def select_node(self, node_id):
        self.callbacks["Nav Select"]["callback"](node_id=node_id, open=True)


class DebugConsole(Module):
    def __init__(self, callbacks, state):
        Module.__init__(self, "debug", callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.debug_box = TextAware(self.frame, bd=3, height=3)
        self.debug_box.pack(expand=True, fill='both')
        self.debug_box.configure(
            foreground='white',
            background='black',
            wrap="word",
        )
        self.debug_box.configure(state="disabled")
        self.debug_box.bind("<Button>", lambda event: self.debug_box.focus_set())

    def write(self, message):
        self.debug_box.configure(state="normal")
        self.debug_box.insert("end-1c", '\n')
        self.debug_box.insert("end-1c", pformat(message))
        self.debug_box.configure(state="disabled")


class Input(Module):
    def __init__(self, callbacks, state):
        Module.__init__(self, "input", callbacks, state)
        self.button_frame = None
        #self.undo_button = None
        #self.retry_button = None
        self.submit_button = None

    def build(self, parent):
        Module.build(self, parent)
        self.input_box = TextAware(self.frame, bd=3, height=1, undo=True)
        self.input_box.pack(expand=True, fill='both')
        self.input_box.configure(**textbox_config(bg=edit_color()))
        self.input_box.focus()
        self.textboxes.append(self.input_box)
        self.button_frame = ttk.Frame(self.frame)
        self.button_frame.pack(side='bottom', fill='x')
        self.submit_button = ttk.Button(self.button_frame, text="Submit", image=icons.get_icon("arrow-white"), compound='right', command=self.submit)
        self.submit_button.pack(side='right')

    def submit(self):
        text = self.input_box.get("1.0", "end-1c")
        modified_text = self.apply_template(text)
        self.callbacks["Submit"]["callback"](text=modified_text, auto_response=self.settings().get("auto_response", True))
        self.input_box.delete("1.0", "end")

    def apply_template(self, input):
        if 'submit_template' in self.settings():
            return eval(f'f"""{self.settings()["submit_template"]}"""')
        else:
            return input



class Media(Module):
    def __init__(self, callbacks, state):
        Module.__init__(self, "media", callbacks, state)
        self.multimedia = Multimedia(callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.multimedia.body(self.frame)

    def tree_updated(self):
        if self.multimedia.master:# and self.multimedia.viewing:
            self.multimedia.refresh()

    def selection_updated(self):
        if self.multimedia.master:# and self.multimedia.viewing:
            self.multimedia.refresh()


# TODO unpin edit node id when edit closed
class Edit(Module):
    def __init__(self, callbacks, state):
        Module.__init__(self, "edit", callbacks, state)
        self.node_label = None
        #self.text = {}
        self.text_attributes = {}
        self.add_text_attribute_button = None
        self.textboxes_frame = None
        #self.buttons_frame = None
        self.node = None
        self.done_editing_button = None
        self.templates_frame = None
        self.template_checkbox = None
        self.templates_dropdown = None
        self.template_bool = tk.BooleanVar()
        self.template_preset = tk.StringVar()

    def build(self, parent):
        Module.build(self, parent)
        self.node_label = ttk.Label(self.frame)
        self.node_label.pack(side='top', pady=10)
        self.node_label.configure(cursor="hand2")
        self.node_label.bind("<Button-1>", self.toggle_pin)

        self.templates_frame = ttk.Frame(self.frame)
        self.templates_frame.pack(side='top', fill='x')
        self.template_checkbox = tk.Checkbutton(self.templates_frame, text="Template", variable=self.template_bool, onvalue=True, 
                                                 offvalue=False, command=self.write_template)
        self.template_checkbox.pack(side='left')

        template_presets = ['children_list']
        self.templates_dropdown = tk.OptionMenu(self.templates_frame, self.template_preset, None, *template_presets)
        self.templates_dropdown.pack(side='left')
        self.template_preset.trace("w", self.template_preset_changed)

        self.textboxes_frame = ttk.Frame(self.frame)
        self.textboxes_frame.pack(side='top', fill='both', expand=True)

        self.add_text_attribute_button = tk.Label(self.frame, text="Add Text Attribute", cursor="hand2", fg=text_color(), bg=bg_color(), relief="raised")

        self.add_text_attribute_button.pack(side='bottom', pady=10)
        self.add_text_attribute_button.bind("<Button-1>", lambda event: self.add_text_attribute(event))
        # self.done_editing_button = ttk.Button(self.buttons_frame, text="Done Editing", command=self.done_editing)
        # self.done_editing_button.pack(side='bottom', expand=True, pady=10)
        self.rebuild_textboxes()
        self.refresh_template()

    def template_preset_changed(self, *args):
        template = self.template_preset.get()
        if template == 'none':
            return 
        elif template == 'children_list':
            node_id = self.node['id']
            self.text_attributes['text'].textbox.insert(tk.END,
                                                        f"{{self.children_text(self.node('{node_id}'), filter=lambda node, self=self: self.has_tag(node=node, tag='example'))}}\n")
            self.save_all()
            self.template_checkbox.select()
            self.write_template()
            

    def toggle_pin(self, *args):
        if self.settings()['node_id']:
            if self.settings()['node_id'] != self.state.selected_node_id:
                self.done_editing()
            else:
                self.settings()['node_id'] = None
                self.node_label.configure(image="")
        else:
            self.settings()['node_id'] = self.state.selected_node['id']
            self.node_label.configure(image=icons.get_icon('pin-red'), compound="left")

    def done_editing(self):
        self.save_all()
        # unpin edit node id
        self.settings()['node_id'] = None
        self.rebuild_textboxes()
        # TODO close pane

    def rebuild_textboxes(self):
        if self.text_attributes:
            for text_attribute in self.text_attributes:
                self.text_attributes[text_attribute].destroy()
        self.text_attributes = {}
        self.textboxes = []

        self.node = self.state.node(self.settings()['node_id']) if self.settings()['node_id'] else self.state.selected_node
        self.node_label.configure(text=f"editing node: {self.node['id']}")
        pinned = self.settings()['node_id'] is not None
        if pinned: 
            self.node_label.configure(image=icons.get_icon('pin-red'), compound="left")
        else:
            self.node_label.configure(image='')


        self.text_attributes['text'] = TextAttribute(master=self.textboxes_frame, attribute_name="text", 
                                                     read_callback=lambda: self.callbacks["Text"]["callback"](node_id=self.node['id'], raw=True),
                                                     write_callback=self.save_text,
                                                     expand=True,
                                                     parent_module=self,
                                                     max_height=30)
        self.text_attributes['text'].pack(side='top', fill='both', expand=True, pady=10)
        #self.text_attributes['text'].update()

        if 'text_attributes' in self.node:
            for attribute in self.node['text_attributes']:
                self.text_attributes[attribute] = TextAttribute(master=self.textboxes_frame, attribute_name=attribute, 
                                                                read_callback=lambda attribute=attribute: self.callbacks["Get text attribute"]["callback"](attribute=attribute, node=self.node),
                                                                write_callback=lambda text, attribute=attribute: self.save_text_attribute(attribute_name=attribute, text=text),
                                                                delete_callback=lambda attribute=attribute: self.delete_text_attribute(attribute),
                                                                expand=True,
                                                                parent_module=self)
                self.text_attributes[attribute].pack(side='top', fill='both', expand=True, pady=10)

        self.update()


    def refresh_template(self):
        self.template_preset.set(None)
        if self.node.get('template', False):
            self.template_checkbox.select()
        else:
            self.template_checkbox.deselect()

    def write_template(self):
        # TODO use callbacks
        self.node['template'] = self.template_bool.get()
        self.state.tree_updated()

    def update(self):
        for text_attribute in self.text_attributes:
            self.text_attributes[text_attribute].read()

    def save_all(self):
        for text_attribute in self.text_attributes:
            self.text_attributes[text_attribute].write()

    # todo catch json decode errors
    def write_frame(self, text):
        if text:
            frame = json.loads(text)
        else:
            frame = {}
        self.state.set_frame(self.node, frame)

    def read_frame(self):
        return json.dumps(self.state.get_frame(self.node))

    def delete_text_attribute(self, attribute_name):
        self.state.remove_text_attribute(self.node, attribute_name)
        self.text_attributes[attribute_name].destroy()
        del self.text_attributes[attribute_name]

    def add_text_attribute(self, event):
        # presets:
        # active_append: shows in story frame when node is selected after node text
        # nav_preview: preview text shown in nav tree
        # child_preview: text shown in child preview in read mode
        # active_template: f string template applied to text only when node is active
        # template: f string template always applied to text (but not sent to language model)
        # alt_text: text which displays in alt textbox when node is active
        # custom
        
        # open menu to select attribute type
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="active_append", command=lambda: self.new_attribute("active_append"))
        menu.add_command(label="nav_preview", command=lambda: self.new_attribute("nav_preview"))
        menu.add_command(label="child_preview", command=lambda: self.new_attribute("child_preview"))
        menu.add_command(label="active_template", command=lambda: self.new_attribute("active_template"))
        menu.add_command(label="template", command=lambda: self.new_attribute("template"))
        menu.add_command(label="alt_text", command=lambda: self.new_attribute("alt_text"))
        menu.add_command(label="custom", command=lambda: self.add_text_attribute_custom())
        # open menu to select attribute name
        menu.tk_popup(event.x_root, event.y_root)

    def save_text(self, text):
        self.callbacks["Update text"]["callback"](node=self.node, text=text)

    def save_text_attribute(self, attribute_name, text):
        self.state.add_text_attribute(self.node, attribute_name, text)

    def selection_updated(self):
        if not self.settings()['node_id']:
            self.save_all()
            self.rebuild_textboxes()
            self.refresh_template()

    def tree_updated(self):
        self.update()

    def add_text_attribute_custom(self):
        # popup window to get attribute name
        name = simpledialog.askstring("Custom Text Attribute", "Enter attribute name:")
        if name:
            # check if attribute already exists
            self.new_attribute(name)

    def new_attribute(self, name):
        if 'text_attributes' in self.node and name in self.node['text_attributes']:
            messagebox.showinfo("Custom Text Attribute", "Attribute already exists.")
            return
        self.state.add_text_attribute(self.node, name, '')
        self.text_attributes[name] = TextAttribute(master=self.textboxes_frame, attribute_name=name, 
                                                    read_callback=lambda: self.callbacks["Get text attribute"]["callback"](attribute=name, node=self.node),
                                                    write_callback=lambda text, attribute=name: self.save_text_attribute(attribute_name=attribute, text=text),
                                                    delete_callback=lambda attribute=name: self.delete_text_attribute(attribute),
                                                    expand=True,
                                                    parent_module=self)
        self.text_attributes[name].pack(side='top', fill='both', expand=True)
        self.text_attributes[name].read()


# TODO make adjustable pane
# TODO show past and future inputs but hide by default if not used by template
class Transformers(Module):
    def __init__(self, callbacks, state):
        self.scroll_frame = None
        self.input_editors = {}
        self.inputs = {}
        self.inputs_frame = None
        #self.template_frame = None
        self.template = None
        self.template_editor = None
        self.prompt = None
        self.prompt_frame = None
        #self.prompt_label = None
        self.prompt_literal_textbox = None
        self.buttons_frame = None
        self.load_template_button = None
        self.save_template_button = None
        self.generate_button = None
        self.generation_settings_frame = None
        self.generation_settings = None
        self.generation_settings_dashboard = None
        self.completions_frame = None
        self.completion_windows = None
        self.state = state
        self.callbacks = callbacks
        Module.__init__(self, "transformers", callbacks, state)
        
    def build(self, parent):
        Module.build(self, parent)
        #self.scroll_frame = ScrollableFrame(self.frame, height=500)
        #self.scroll_frame.pack(side='top', fill='both', expand=True)
        #self.frame.bind("<Button-1>", lambda e: self.frame.focus)
        self.generation_settings = self.state.generation_settings.copy()
        self.buttons_frame = tk.Frame(self.frame, bg=bg_color())
        self.buttons_frame.pack(side='top', fill='x', expand=False)
        self.load_template_button = ttk.Button(self.buttons_frame, text="Load template", command=self.load_template)
        self.load_template_button.pack(side='left')
        self.save_template_button = ttk.Button(self.buttons_frame, text="Save template", command=self.save_template)
        self.save_template_button.pack(side='left')

        self.inputs_frame = tk.Frame(self.frame, bg=bg_color())
        self.inputs_frame.pack(side='top', fill='both', expand=True)

        self.template_editor = TextAttribute(master=self.frame, attribute_name="template", 
                                             read_callback=lambda: self.read_template(), 
                                             write_callback=lambda text: self.write_template(text=text), 
                                             expand=True, parent_module=self)
        self.template_editor.pack(side='top', fill='both', expand=True)

        self.prompt_frame = CollapsableFrame(self.frame, title='prompt', expand=True, bg=bg_color())
        self.prompt_frame.pack(side='top', fill='both', expand=True)

        self.prompt_literal_textbox = TextAware(self.prompt_frame.collapsable_frame, bd=2, height=3, undo=True,
                                                relief='raised')
        self.prompt_literal_textbox.pack(side='top', fill='both', expand=True)
        self.prompt_literal_textbox.configure(**textbox_config())
        self.prompt_literal_textbox.configure(state='disabled')

        self.generation_settings_frame = CollapsableFrame(self.frame, title='Generation settings', bg=bg_color())
        self.generation_settings_dashboard = SpecialGenerationSettings(orig_params=self.generation_settings, state=self.state,
                                                                       realtime_update=True, parent_module=self)
        self.generation_settings_dashboard.body(self.generation_settings_frame.collapsable_frame)
        self.generation_settings_frame.pack(side='top', fill='both', expand=True)

        self.generate_button = ttk.Button(self.frame, text="Generate", image=icons.get_icon('brain-blue'), compound='left', command=self.generate)
        self.generate_button.pack(side='top', expand=False)
        
        self.completions_frame = CollapsableFrame(self.frame, title='Completions', bg=bg_color())
        self.completion_windows = Windows(state=self.state, callbacks=self.callbacks, buttons=['close', 'save'])
        self.completion_windows.body(self.completions_frame.collapsable_frame)
        self.completions_frame.pack(side='top', fill='both', expand=True)

        self.generation_settings_frame.hide()
        self.completions_frame.hide()

        # self.completion_windows.body(self.completions_frame)
        self.load_default_template()

    def load_default_template(self):
        default_tempate = {
            'inputs': ['input'],
            'template': '{inputs["input"]}',
            'generation_settings': { 'model': 'curie' }
        }
        self.open_template(default_tempate)

    def reset(self):
        for input in self.input_editors:
            self.input_editors[input].destroy()
        self.inputs = {}
        self.input_editors = {}
        self.template = None

    def open_template(self, template):
        """
        template format:
        {
            inputs: [ string ]
            template: f-string
            generation_settings: {}

        }
        """
        self.reset()
        self.template = template
        self.set_empty_inputs()
        for input in template['inputs']:
            self.input_editors[input] = TextAttribute(master=self.inputs_frame, attribute_name=input, 
                                                      read_callback=lambda: self.read_input(input),
                                                      write_callback=lambda text, input=input:self.write_input(input=input, text=text), 
                                                      delete_callback=lambda input=input: self.remove_input(input), 
                                                      expand=True, 
                                                      max_height=10,
                                                      parent_module=self)
            self.input_editors[input].pack(side='top', fill='both', expand=True)

        self.read_all()
        #self.write_all()
        self.update_prompt()

    def set_empty_inputs(self):
        for input in self.template['inputs']:
            self.inputs[input] = ""

    def read_input(self, input):
        return self.inputs[input]

    def write_input(self, input, text):
        self.inputs[input] = text
        self.update_prompt()

    def read_template(self):
        return self.template['template']

    def write_template(self, text):
        self.template['template'] = text
        self.update_prompt()

    def read_generation_settings(self):
        if 'generation_settings' in self.template:
            self.generation_settings.update(self.template['generation_settings'])
        #print(self.generation_settings)
        #self.generation_settings_dashboard.read()
        #self.generation_settings_dashboard.read_orig_params()
        self.generation_settings_dashboard.reset_vars()

    def write_generation_settings(self):
        self.template['generation_settings'] = self.generation_settings

    def read_all(self):
        for input in self.input_editors:
            self.input_editors[input].read()
        self.template_editor.read()
        self.template_editor.textbox.see(tk.END)
        self.read_generation_settings()

    def write_all(self):
        for input in self.input_editors:
            self.input_editors[input].write()
        self.template_editor.write()
        self.write_generation_settings()
        self.update_prompt()

    def remove_input(self, input):
        self.input_editors[input].destroy()
        self.template['inputs'].remove(input)
        del self.input_editors[input]
        del self.inputs[input]
        self.update_prompt()

    def add_input(self, input):
        self.input_editors[input] = TextAttribute(master=self.inputs_frame, attribute_name=input, 
                                                  write_callback=lambda text, input=input:self.write_input(input=input, text=text), 
                                                  delete_callback=lambda input=input: self.remove_input(input), 
                                                  expand=True,
                                                  parent_module=self)
        self.input_editors[input].pack(side='top', fill='both', expand=True)
        self.template['inputs'].append(input)
        self.read_all()
        self.update_prompt()

    def update_prompt(self, *args):
        # TODO database
        inputs = self.inputs 
        try:
            self.prompt = eval(f'f"""{self.template["template"]}"""')
        except KeyError as e:
            print(f'missing input: {e}')
            return
        self.prompt_literal_textbox.configure(state='normal')
        self.prompt_literal_textbox.delete(1.0, tk.END)
        self.prompt_literal_textbox.insert(tk.END, self.prompt)
        self.prompt_literal_textbox.configure(state='disabled')
        self.prompt_literal_textbox.see(tk.END)

    def open_template_file(self, file_path):
        with open(file_path) as f:
            template = json.load(f)
        self.open_template(template)

    def load_template(self):
        file_path = filedialog.askopenfilename(
            initialdir="./config/transformers",
            title="Select prompt template",
            filetypes=[("Json files", ".json")]
        )
        if file_path:
            self.open_template_file(file_path)
            
    def save_template(self):
        self.write_all()
        file_path = filedialog.asksaveasfilename(
            initialdir="./config/transformers",
            title="Save prompt template",
            filetypes=[("Json files", ".json")]
        )

        if file_path:
            with open(file_path, 'w') as f:
                json.dump(self.template, f)

    def open_inputs(self, inputs):
        self.inputs = inputs
        self.read_all()
        self.update_prompt()

    def generate(self):
        self.write_all()
        prompt = self.prompt
        n = self.generation_settings["num_continuations"]
        threading.Thread(target=self.call_model, args=(prompt, n)).start()

    def call_model(self, prompt, n):
        response, error = gen(prompt, self.generation_settings, self.state.model_config)
        response_text_list = completions_text(response)
        self.completions_frame.show()
        for completion in response_text_list:
            self.completion_windows.open_window(completion)

class MetaProcess(Module):
    def __init__(self, callbacks, state):
        Module.__init__(self, "metaprocess", callbacks, state)
        self.metaprocess_name = tk.StringVar(value = "author attribution")

        self.metaprocess_specification_field = None
        self.buttons_frame = None

        self.run_button = None
        self.refresh_button = None


        self.input_field = None
        # self.output_field = None
        self.completions_frame = None
        self.completion_windows = None
        self.output_probability_field = None
        self.input_frame = None
        self.input = None
        self.aux_input_field = None
        self.aux_input = None
        self.output = None
        self.process_log_frame = None
        self.process_log_field = None
        self.process_log = None

        self.process_selector = None
        self.new_metaprocess_button = None
        self.clone_metaprocess_button = None
        self.save_button = None
        self.top_row = None
        self.state = state
        self.callbacks = callbacks
        

    def build(self, parent):
        Module.build(self, parent)

        self.generation_settings = self.state.generation_settings.copy()

        self.top_row = tk.Frame(self.frame, bg=bg_color())
        self.top_row.pack(side='top', fill='x', expand=False)

        self.process_selector = tk.OptionMenu(self.top_row, self.metaprocess_name, *metaprocesses.keys(), command=self.load_metaprocess)
        self.process_selector.pack(side='left', fill='x', expand=True)

        self.new_metaprocess_button = ttk.Button(self.top_row, text="New", command=self.new_metaprocess)
        self.new_metaprocess_button.pack(side='left', fill='x', expand=False)

        self.save_button = ttk.Button(self.top_row, text="Save", command=self.save_metaprocess)
        self.save_button.pack(side='left', fill='x', expand=False)

        self.clone_metaprocess_button = ttk.Button(self.top_row, text="Clone", command=lambda: self.new_metaprocess(data=metaprocesses[self.metaprocess_name.get()]))
        self.clone_metaprocess_button.pack(side='left', fill='x', expand=False)

        self.metaprocess_specification_field = TextAttribute(master=self.frame, 
                                                            attribute_name="metaprocess specification",
                                                            read_callback=self.set_metaprocess_spec, 
                                                            write_callback=self.update_metaprocess,
                                                            expand=True,
                                                            parent_module=self, max_height=30)
        self.metaprocess_specification_field.pack(side='top', fill='both', expand=True)




        self.input_frame = CollapsableFrame(self.frame, title='Branch input ("input")', bg=bg_color())
        self.input_frame.pack(side='top', fill='both', expand=True)

        self.input_field = TextAware(self.input_frame.collapsable_frame, bd=2, height=3, undo=True, relief='raised')
        self.input_field.pack(side='top', fill='both', expand=True)
        # self.input_field.body(self.input_frame.collapsable_frame)
        self.input_field.configure(**textbox_config())
        self.input_field.configure(state='disabled')

        self.aux_input_field = TextAttribute(master=self.frame, attribute_name='Auxiliary input ("aux_input")',
                                read_callback=self.set_aux_input,
                                write_callback=self.update_aux_input,
                                expand=True,
                                parent_module=self, max_height=20)
        self.aux_input_field.pack(side='top', fill='both', expand=True)


        self.buttons_frame = tk.Frame(self.frame, bg=bg_color())
        self.buttons_frame.pack(side='top', fill='x', expand=False)

        self.run_button = ttk.Button(self.buttons_frame, text="Run", command=self.run)
        self.run_button.pack(side='left', fill='x', expand=True)

        self.refresh_button = ttk.Button(self.buttons_frame, text="Refresh", command=self.refresh)
        self.refresh_button.pack(side='left', fill='x', expand=False)

        self.process_log_frame = CollapsableFrame(self.frame, title='Process log', bg=bg_color())
        self.process_log_frame.pack(side='top', fill='both', expand=True)
        self.process_log_field = TextAware(self.process_log_frame.collapsable_frame, bd=2, height=4, undo=True, relief='raised')
        self.process_log_field.pack(side='top', fill='both', expand=True)
        self.process_log_field.configure(**textbox_config(            
            fg='white',
            bg='black'))
        self.process_log_field.configure(state='disabled')

        self.output_probability_field = tk.Label(self.frame, text="Probability:", bg=bg_color(), fg=text_color())
        self.output_probability_field.pack(side='top', fill='x', expand=False)

        self.completions_frame = CollapsableFrame(self.frame, title='Completions', bg=bg_color())
        self.completion_windows = Windows(state=self.state, callbacks=self.callbacks, buttons=['close', 'attach'])
        self.completion_windows.body(self.completions_frame.collapsable_frame)
        self.completions_frame.pack(side='top', fill='both', expand=True)

        self.input_frame.hide()
        self.process_log_frame.hide()
        self.completions_frame.hide()

        self.load_metaprocess("author attribution")


    def load_metaprocess(self, metaprocess_name):
        self.metaprocess_name.set(metaprocess_name)
        self.metaprocess_specification_field.read()

    def set_metaprocess_spec(self):
        metaprocess_data = metaprocesses[self.metaprocess_name.get()]
        return json.dumps(metaprocess_data, indent=4)

    def update_metaprocess(self, text):
        metaprocess_data = json.loads(text)
        metaprocesses[self.metaprocess_name.get()] = metaprocess_data

    def set_aux_input(self):
        return self.aux_input
    
    def update_aux_input(self, text):
        self.aux_input = text

    def new_metaprocess(self, data=None):
        new_metaprocess_data = {}
        # popup window to get attribute name
        name = simpledialog.askstring("New Metaprocess", "Enter metaprocess name:")

        if(data == None):
            new_metaprocess_data = {
                # "name": "new metaprocess",
                "description": "description",
                "input_transform":"lambda input: input[-2000:]",
                "prompt_template":"lambda input, aux_input: f\"Text: '{input}'\\nContains {aux_input}? (Yes/No):\"",
                "output_transform":"lambda output: get_judgement_probability(output)",
                "output_type": "probability",
                "generation_settings": {
                    "engine": "davinci",
                    "max_tokens": 1,
                    "logprobs": 10
                }
            }
        else:
            new_metaprocess_data = data.copy()

        metaprocesses[name] = new_metaprocess_data
        self.process_selector['menu'].add_command(label=name, command=lambda: self.load_metaprocess(name))
        self.load_metaprocess(name)

    def save_metaprocess(self):
        save_metaprocess(self.metaprocess_name.get(), metaprocesses[self.metaprocess_name.get()])
        messagebox.showinfo(title=None, message="Saved!")


    def run(self):
        # self.output = metaprocesses[self.metaprocess_name.get()](self.input)
        self.refresh()
        self.output, self.process_log = execute_metaprocess(self.metaprocess_name.get(), self.input, self.aux_input)

        self.completion_windows.clear_windows()

        self.process_log_field.configure(state='normal')
        self.process_log_field.delete(1.0, tk.END)
        self.process_log_field.insert(tk.END, json.dumps(self.process_log, indent=4))
        self.process_log_field.configure(state='disabled')

        if(type(self.output) == list):
            self.completions_frame.show()
            for completion in self.output:
                self.completion_windows.open_window(completion)
        else:
            self.completions_frame.hide()
            self.output_probability_field.configure(text=f"Probability: {self.output}")

    def refresh(self):
        self.input = self.state.ancestry_text(self.state.selected_node)

        self.input_field.configure(state='normal')
        self.input_field.delete(1.0, tk.END)
        self.input_field.insert(tk.END, self.input)
        self.input_field.configure(state='disabled')

    
    def selection_updated(self):
        self.refresh()

    def tree_updated(self):
        self.refresh()
        


class GenerationSettings(Module):
    def __init__(self, callbacks, state):
        self.settings_control = None
        Module.__init__(self, "generation settings", callbacks, state)
    
    def build(self, parent):
        Module.build(self, parent)
        self.settings_control = FullGenerationSettings(orig_params=self.state.generation_settings,
                                                       user_params=self.state.user_generation_settings,
                                                       state=self.state,
                                                       realtime_update=True, parent_module=self)
        self.settings_control.body(self.frame)

    # TODO update


# TODO able to edit nodes that aren't selected
# make more general attributes class
class FrameEditor(Module):
    def __init__(self, callbacks, state):
        self.frame_editor = None
        self.preset_dropdown = None 
        self.save_preset_button = None
        self.presets = None
        self.preset = None
        self.state_viewer = None
        self.write_to_user_frame_button = None
        Module.__init__(self, "frame editor", callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.frame_editor = TextAttribute(master=self.frame, attribute_name="frame",
                                          read_callback=self.read_frame, 
                                          write_callback=self.write_frame,
                                          expand=True,
                                          parent_module=self, max_height=30)
        self.frame_editor.pack(side='top', fill='both', expand=True, pady=10)
        self.frame_editor.textbox.configure(**code_textbox_config())
    
        # TODO make collapsible
        self.state_viewer = TextAttribute(master=self.frame, attribute_name='state', bd=2, max_height=30, expand=True,
                                                relief='raised')
        self.state_viewer.pack(side='top', fill='both', expand=True)
        self.state_viewer.textbox.configure(**code_textbox_config(bg='#222222'))
        self.state_viewer.textbox.configure(state='disabled')

        self.preset_dropdown = tk.OptionMenu(self.frame, self.preset, "Select preset...")
        self.preset_dropdown.pack(side='top', pady=10)
        self.preset = tk.StringVar()
        self.get_presets()
        self.set_presets()
        self.preset.trace('w', self.apply_preset)

        self.write_to_user_frame_button = tk.Button(self.frame, text="Copy to user frame", command=self.write_to_user_frame)
        self.write_to_user_frame_button.pack(side='top', pady=10)

        self.frame_editor.read()
        self.get_state()
    

    def set_presets(self):
        options = self.presets.keys()
        menu = self.preset_dropdown['menu']
        menu.delete(0, 'end')
        for option in options:
            menu.add_command(label=option, command=tk._setit(self.preset, option))
        # set menu to default

    def get_presets(self):
        # load presets from json file
        with open('./config/interfaces/interfaces.json') as f:
            self.presets = json.load(f)

    def apply_preset(self, *args):
        preset_name = self.preset.get()
        if preset_name in self.presets:
            preset = self.presets[preset_name]
            preset_text = json.dumps(preset, indent=4)
            self.frame_editor.textbox.delete(1.0, tk.END)
            self.frame_editor.textbox.insert(tk.END, preset_text)
            self.write_frame(preset_text)

    def get_state(self):
        state = self.state.state
        self.state_viewer.textbox.configure(state='normal')
        self.state_viewer.textbox.delete(1.0, tk.END)
        self.state_viewer.textbox.insert(tk.END, json.dumps(state, indent=4))
        self.state_viewer.textbox.configure(state='disabled')

    # todo catch json decode errors
    def write_frame(self, text):
        if text:
            frame = json.loads(text)
        else:
            frame = {}
        self.state.set_frame(self.state.selected_node, frame)
        self.get_state()
        self.state.tree_updated()

    def write_to_user_frame(self):
        frame_text = json.loads(self.frame_editor.textbox.get(1.0, tk.END))
        self.state.set_user_frame(frame_text)

    def read_frame(self):
        return json.dumps(self.state.get_frame(self.state.selected_node), indent=4)

    def selection_updated(self):
        self.frame_editor.read()
        self.get_state()


# TODO toggle enabled/disabled
# automatically minimize disabled entries
class Memories(Module):
    def __init__(self, callbacks, state):
        self.memory_editor = None
        Module.__init__(self, "memories", callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.memory_editor = AttributesEditor(attribute_category="memory",
                                              get_attributes_callback=self.get_memories,
                                              attribute_name_callback_template=self.get_memory_name,
                                              read_callback_template=self.read_memory,
                                              write_callback_template=self.write_memory,
                                              delete_callback_template=self.delete_memory,
                                              visibility_callback_template=self.toggle_visibility,
                                              add_attribute_callback=self.add_memory,
                                              parent_module=self,
                                              max_height=3)
        self.memory_editor.build(self.frame)

    def get_memories(self):
        return self.state.memories

    def get_memory_name(self, memory_id):
        memory = self.state.memories[memory_id]
        return memory['name'] if 'name' in memory else memory['text'][:20]

    def read_memory(self, memory_id):
        return self.state.memories[memory_id]['text']

    def write_memory(self, memory_id, text):
        self.state.update_memory(memory_id, update={'text': text})

    def delete_memory(self, memory_id):
        self.state.delete_memory(memory_id)

    def toggle_visibility(self, memory_id):
        pass

    def add_memory(self):
        pass

    def refresh(self):
        self.memory_editor.refresh()

    def read(self):
        self.memory_editor.read_all()

    def selection_updated(self):
        self.refresh()

    def tree_updated(self):
        self.refresh()
        self.read()


    
class Vars(Module):
    def __init__(self, callbacks, state):
        self.vars_editor = None
        Module.__init__(self, "vars", callbacks, state)

    def build(self, parent):
        Module.build(self, parent)
        self.vars_editor = AttributesEditor(attribute_category="variable",
                                            get_attributes_callback=self.get_vars,
                                            read_callback_template=self.read_var,
                                            write_callback_template=self.write_var,
                                            delete_callback_template=self.delete_var,
                                            add_attribute_callback=self.add_var,
                                            parent_module=self)
        self.vars_editor.build(self.frame)

    def get_vars(self):
        return self.state.vars

    def read_var(self, var_id):
        return self.state.vars[var_id]

    def write_var(self, var_id, text):
        # TODO use create var function
        self.state.update_var(self.state.selected_node, var_id, text)

    def delete_var(self, var_id):
        self.state.delete_var(var_id)

    def add_var(self):
        # TODO add as default in attributeEditor class
        name = simpledialog.askstring("New variable", "Variable name:")
        if name:
            self.state.create_var(self.state.selected_node, name)
        self.refresh()

    def refresh(self):
        self.vars_editor.refresh()

    def read(self):
        self.vars_editor.read_all()

    def selection_updated(self):
        self.refresh()
        self.read()

    def tree_updated(self):
        self.refresh()
        self.read()



class Wavefunction(Module):
    def __init__(self, callbacks, state):
        self.wavefunction = None
        self.buttons_frame = None
        self.config_frame = None
        # config: model, max_depth, threshold
        self.model = tk.StringVar()
        self.threshold = tk.DoubleVar()
        self.max_depth = tk.IntVar()
        self.max_depth_slider = None
        self.threshold_slider = None
        self.model_dropdown = None
        # buttons: propagate, clear, center, add path to tree, save image
        self.propagate_button = None
        self.clear_button = None
        self.add_path_button = None
        self.reset_zoom_button = None
        self.save_image_button = None
        self.model_list = ["ada", "ada", "babbage", "curie", "davinci", "text-davinci-002", "text-davinci-003", "code-davinci-002", "gpt-neo-1-3b", "gpt-neo-2-7b", "gpt-j-6b", "gpt-neo-20b"]
        
        self.ground_truth_textbox = None
        Module.__init__(self, 'wavefunction', callbacks, state)


    def build(self, parent):
        Module.build(self, parent)
        self.config_frame = ttk.Frame(self.frame)
        self.config_frame.pack(side=tk.TOP, fill=tk.X)
        model_label = ttk.Label(self.config_frame, text="Model:")
        model_label.pack(side=tk.LEFT)
        self.model_dropdown = ttk.OptionMenu(self.config_frame, self.model, *self.model_list)
        self.model_dropdown.pack(side=tk.LEFT, padx=10)

        max_depth_label = ttk.Label(self.config_frame, text="Depth")
        max_depth_label.pack(side=tk.LEFT)
        self.max_depth_slider = tk.Scale(self.config_frame, from_=1, to=7, orient=tk.HORIZONTAL, variable=self.max_depth, sliderlength=5, bg=bg_color())
        self.max_depth_slider.pack(side=tk.LEFT, padx=10)

        threshold_label = ttk.Label(self.config_frame, text="Cutoff")
        threshold_label.pack(side=tk.LEFT)
        self.threshold_slider = tk.Scale(self.config_frame, from_=0.0, to=0.25, resolution="0.01", orient=tk.HORIZONTAL, variable=self.threshold, sliderlength=5, bg=bg_color())
        self.threshold_slider.pack(side=tk.LEFT, padx=10)
    
        self.wavefunction = BlockMultiverse(self.frame)
        self.wavefunction.frame.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

        self.ground_truth_textbox = TextAware(self.frame, height=1, bd=2, undo=True)
        self.ground_truth_textbox.pack(side=tk.TOP, expand=False, fill=tk.X)
        self.ground_truth_textbox.configure(
            foreground=text_color(),
            background=edit_color(),
            wrap="word",
        )

        self.textboxes.append(self.ground_truth_textbox)

        self.buttons_frame = ttk.Frame(self.frame)
        self.buttons_frame.pack(side='bottom', fill='x')
        self.propagate_button = ttk.Button(self.buttons_frame, text="Propagate", compound='right', command=self.propagate)
        self.propagate_button.pack(side='left')
        self.clear_button = ttk.Button(self.buttons_frame, text="Clear", compound='right', command=self.clear)
        self.clear_button.pack(side='left')
        self.reset_zoom_button = ttk.Button(self.buttons_frame, text="Reset zoom", compound='right', command=self.reset_zoom)
        self.reset_zoom_button.pack(side='left')
        self.add_path_button = ttk.Button(self.buttons_frame, text="Add path to tree", compound='right', command=self.add_path)
        self.add_path_button.pack(side='left')
        self.save_image_button = ttk.Button(self.buttons_frame, text="Save image", compound='right', command=self.save_image)
        self.save_image_button.pack(side='left')
        
        self.set_config()
    

    def set_config(self):
        current_model = self.state.generation_settings['model']
        self.model.set(current_model if current_model in self.model_list else "ada")
        self.max_depth.set(3)
        self.threshold.set(0.1)
        

    def propagate(self):
        if self.wavefunction.active_wavefunction():
            active_node = self.wavefunction.active_info()
            start_position = (active_node['x'], active_node['y'])
            multiverse, ground_truth, prompt = self.state.generate_greedy_multiverse(max_depth=self.max_depth.get(), 
                                                                                prompt=active_node['prefix'],
                                                                                unnormalized_amplitude=active_node['amplitude'],
                                                                                ground_truth=self.ground_truth_textbox.get(1.0, tk.END),
                                                                                threshold=self.threshold.get(),
                                                                                engine=self.model.get())
        else:
            start_position = (0, 0)
            multiverse, ground_truth, prompt = self.state.generate_greedy_multiverse(max_depth=self.max_depth.get(), 
                                                                                ground_truth=self.ground_truth_textbox.get(1.0, tk.END),
                                                                                threshold=self.threshold.get(),
                                                                                engine=self.model.get()
                                                                                )
                                                                      
        self.wavefunction.draw_multiverse(multiverse=multiverse, ground_truth=ground_truth,
                                                start_position=start_position, prompt=prompt)

    def clear(self):
        self.wavefunction.clear_multiverse()

    def reset_zoom(self):
        self.wavefunction.reset_view()

    def add_path(self):
        if self.wavefunction.active_wavefunction():
            active_node = self.wavefunction.active_info()
            prompt=active_node['prefix']
            new_child = self.state.create_child(self.state.selected_node, expand=True)
            new_child['text'] = prompt
            self.state.tree_updated(add=[new_child['id']])

    def save_image(self):
        prompt = self.state.default_prompt(quiet=True, node=self.state.selected_node)
        self.wavefunction.save_as_png(f'{prompt[-20:]}_{self.model.get()}.png')

    def tree_updated(self):
        pass

    def selection_updated(self):
        self.clear()
