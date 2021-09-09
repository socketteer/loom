from view.panes import Module
import tkinter as tk
from tkinter import ttk
from view.colors import text_color, bg_color, edit_color, vis_bg_color
from util.custom_tks import TextAware
from util.util_tree import tree_subset, limited_branching_tree
from view.icons import Icons
from view.styles import textbox_config
from view.templates import *
from view.tree_vis import round_rectangle
from pprint import pformat, pprint
from gpt import completions_text
import uuid
import threading

icons = Icons()



class Notes(Module):
    def __init__(self, parent, callbacks, state):
        self.menu_frame = None
        self.new_note_button = None
        self.pinned_frame = None
        self.notes_frame = None
        self.notes = NodeWindows(callbacks, buttons=['close', 'go', 'attach', 'archive', 'delete'], init_height=1)
        Module.__init__(self, 'notes', parent, callbacks, state)

    def build(self):
        Module.build(self)
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
    def __init__(self, parent, callbacks, state):
        self.menu_frame = None
        self.children = NodeWindows(callbacks, buttons=['close', 'go', 'edit', 'archive', 'delete'], 
                               buttons_visible=True, 
                               editable=False,
                               init_height=100)
        self.add_child_button = None
        self.toggle_hidden_button = None
        self.show_hidden = False
        Module.__init__(self, 'children', parent, callbacks, state)
 
    def build(self):
        Module.build(self)
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

    def tree_updated(self):
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
        self.children.save_windows()
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

class JanusPlayground(Module):
    def __init__(self, parent, callbacks, state):
        self.pane = None
        self.textbox_frame = None
        self.menu_frame = None
        self.insert_prompt_button = None
        self.generate_button = None
        self.export_button = None
        self.settings_button = None
        self.completions_frame = None
        self.completion_windows = Windows(buttons=['close', 'append', 'attach'])
        self.inline_completions = None
        self.completion_index = 0
        self.inserted_range = None
        Module.__init__(self, 'janus/playground', parent, callbacks, state)


    def build(self):
        Module.build(self)
        self.pane = ttk.Panedwindow(self.frame, orient='vertical')
        self.pane.pack(side='top', fill='both', expand=True)
        self.textbox_frame = ttk.Frame(self.pane)
        self.pane.add(self.textbox_frame, weight=4)
        self.textbox = TextAware(self.textbox_frame, bd=2, height=3, undo=True)
        self.textbox.pack(side='top', fill='both', expand=True)
        self.textboxes.append(self.textbox)
        self.textbox.configure(**textbox_config(bg=edit_color()))
        self.textbox.tag_config("sel", background="black", foreground="white")
        self.textbox.tag_config("generated", font=('Georgia', self.state.preferences['font_size'], 'bold'))
        self.textbox.bind("<Key>", self.key_pressed)
        self.textbox.bind("<Alt-g>", self.inline_generate)
        self.textbox.bind("<Command-g>", self.inline_generate)
        self.textbox.bind("<Alt-period>", self.insert_inline_completion)
        self.textbox.bind("<Command-period>", self.insert_inline_completion)
        self.textbox.focus()
        self.button_frame = ttk.Frame(self.textbox_frame)
        self.button_frame.pack(side='bottom', fill='x')
        self.generate_button = ttk.Button(self.button_frame, text='Insert prompt', image=icons.get_icon("rightarrow-lightgray"),
                                          cursor='hand2', command=self.insert_prompt, compound='left')
        self.generate_button.pack(side='left', expand=True)
        self.generate_button = ttk.Button(self.button_frame, text='Generate', image=icons.get_icon("brain-blue"),
                                          cursor='hand2', command=self.generate, compound='left')
        self.generate_button.pack(side='left', expand=True)
        self.export_button = ttk.Button(self.button_frame, text='Export', cursor='hand2',
                                        command=self.export)
        self.export_button.pack(side='left', expand=True)
        self.settings_button = tk.Label(self.button_frame, image=icons.get_icon("settings-lightgray"), bg=bg_color(),
                                        cursor='hand2')
        self.settings_button.bind("<Button-1>", self.settings)
        self.settings_button.pack(side='left', expand=True)
        self.completions_frame = ttk.Frame(self.pane)
        self.pane.add(self.completions_frame, weight=1)
        self.completion_windows.body(self.completions_frame)

    def replace_selected_text(self, text):
        #selected_text = self.textbox.get("sel.first", "sel.last")
        sel_first = self.textbox.index("sel.first")
        self.textbox.delete("sel.first", "sel.last")
        self.textbox.insert(sel_first, text)
        

    def inline_generate(self, *args):
        # get text up to cursor
        prompt = self.textbox.get("1.0", "insert")
        n = self.state.inline_generation_settings["num_continuations"]
        threading.Thread(target=self.call_model_inline, args=(prompt, n)).start()

    def generate(self, *args):
        prompt = self.textbox.get("1.0", "end-1c")
        n = self.state.generation_settings["num_continuations"]
        threading.Thread(target=self.call_model, args=(prompt, n)).start()

    def call_model_inline(self, prompt, n):
        response, error = self.state.gen(prompt, n, inline=True)
        response_text_list = completions_text(response)
        self.inline_completions = [completion for completion in response_text_list if completion] + [""]
        self.inserted_range = None
        self.insert_inline_completion()

    def call_model(self, prompt, n):
        response, error = self.state.gen(prompt, n)
        response_text_list = completions_text(response)
        for completion in response_text_list:
            self.completion_windows.open_window(completion)

    def key_pressed(self, event):
        if event.keysym == "Alt_L":
            return
        # else:
        #     self.accept_completion()

    def accept_completion(self):
        # untag generated text
        print('accept completion')
        #self.textbox.tag_remove("generated", "1.0", "end")
        self.inserted_range = None

    def insert_inline_completion(self, *args):
        if self.inline_completions:
            # delete text with generated tag
            #self.textbox.tag_delete("generated")
            if self.inserted_range: 
                self.textbox.delete(self.inserted_range[0], self.inserted_range[1])
            completion = self.inline_completions[self.completion_index % len(self.inline_completions)]
            if self.textbox.tag_ranges("sel"):
                self.replace_selected_text(completion)
            else:
                self.textbox.insert("insert", completion)
            self.textbox.tag_add("generated", "insert - %d chars" % len(completion), "insert")
            self.inserted_range = (self.textbox.index("insert - %d chars" % len(completion)), self.textbox.index("insert"))
            self.completion_index += 1

    def export(self, *args):
        pass

    def settings(self, *args):
        pass

    def insert_prompt(self, *args):
        prompt = self.callbacks["Prompt"]["callback"]()
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", prompt)




class TextEditor(Module):
    def __init__(self, parent, callbacks, state):
        self.textbox = None
        self.export_button = None
        self.attach_button = None
        self.open_button = None
        self.clear_button = None
        self.text = None
        self.button_frame = None
        Module.__init__(self, 'texteditor', parent, callbacks, state)

    def build(self):
        Module.build(self)
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
    def __init__(self, parent, callbacks, state):
        self.edit_button = None
        self.textbox = None
        self.button_frame = None
        Module.__init__(self, 'prompt', parent, callbacks, state)

    def build(self):
        Module.build(self)
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
    def __init__(self, parent, callbacks, state):
        Module.__init__(self, 'run', parent, callbacks, state)
        self.eval_code = EvalCode(self.callbacks["Run"]['prev_cmd'], callbacks)
        self.run_button = None
        self.clear_button = None
        self.button_frame = None

    def build(self):
        Module.build(self)
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
    def __init__(self, parent, callbacks, state):
        Module.__init__(self, 'minimap', parent, callbacks, state)
        self.minimap_pane = None
        self.canvas = None 
        self.node_coords = {}
        self.levels = {}
        self.nodes = {}
        self.lines = {}
        self.preview_textbox = None

    def build(self):
        Module.build(self)
        self.minimap_pane = ttk.PanedWindow(self.frame, orient='vertical')
        self.minimap_pane.pack(side='left', fill='both', expand=True)
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

    def clear(self):
        self.canvas.delete('all')
        self.node_coords = {}
        self.levels = {}
        self.nodes = {}
        self.lines = {}

    def refresh(self):
        self.clear()
        selected_node = self.state.selected_node
        root = self.state.root()
        filtered_tree = tree_subset(root, filter=lambda node:self.callbacks["In nav"]["callback"](node=node))
        ancestry = self.state.ancestry(selected_node)
        pruned_tree = limited_branching_tree(ancestry, filtered_tree, depth_limit=12)
        self.compute_tree_coordinates(pruned_tree, 200, 400, level=0)
        self.center_about_ancestry(ancestry, x_align=200)
        self.center_y(selected_node, 400)
        #self.fix_orientation()
        self.draw_precomputed_tree(pruned_tree)
        self.color_selection(selected_node)

    def compute_tree_coordinates(self, root, x, y, level=0):
        self.node_coords[root["id"]] = (x, y)
        if level not in self.levels:
            self.levels[level] = []
        self.levels[level].append(root["id"])
        level_offset = 80
        leaf_offset = 50
        leaf_position = x
        next_child_position = x
        for child in root['children']:
            leaf_position = next_child_position
            subtree_offset = self.compute_tree_coordinates(child, next_child_position, y + level_offset, level+1)
            leaf_position += subtree_offset
            next_child_position = leaf_position + leaf_offset
        return leaf_position - x

    def fix_orientation(self):
        if self.state.visualization_settings["horizontal"]:
            coords = {}
            # if the tree is horizontal, swap x and y coordinates
            for id, value in self.node_coords.items():
                coords[id] = (value[1], value[0])
            self.node_coords = coords

    def draw_precomputed_tree(self, root):
        root_x, root_y = self.node_coords[root["id"]]
        self.draw_node(root['id'], radius=15, x=root_x, y=root_y)

        for child in root['children']:
            child_x, child_y = self.node_coords[child["id"]]
            self.draw_connector(child['id'], root_x, root_y, child_x, child_y, fill='#000000', width=2, 
                                offset=30, 
                                connections='vertical')
            self.draw_precomputed_tree(child)

    def center_about_ancestry(self, ancestry, x_align, level=0):
        if level >= len(ancestry):
            return
        ancestor = ancestry[level]
        ancestor_x, _ = self.node_coords[ancestor['id']]
        offset = ancestor_x - x_align
        for node_id in self.levels[level]:
            self.node_coords[node_id] = (self.node_coords[node_id][0] - offset, self.node_coords[node_id][1])
        if level + 1 < len(ancestry):
            self.center_about_ancestry(ancestry, x_align, level+1)
        else:
            #shift all deeper levels by same offset
            remaining_levels = [self.levels[i] for i in range(level+1, len(self.levels))]
            for l in remaining_levels:
                for node_id in l:
                    self.node_coords[node_id] = (self.node_coords[node_id][0] - offset, self.node_coords[node_id][1])


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
        ancestry = self.state.ancestry(selected_node)
        # color all ancestry nodes blue
        for node in ancestry:
            self.canvas.itemconfig(self.nodes[node['id']], fill="blue", outline="blue",)
            if node['id'] in self.lines:
                self.canvas.itemconfig(self.lines[node['id']], fill="blue", width=3)

    def select_node(self, node_id):
        self.callbacks["Nav Select"]["callback"](node_id=node_id)


class DebugConsole(Module):
    def __init__(self, parent, callbacks, state):
        Module.__init__(self, "debug", parent, callbacks, state)

    def build(self):
        Module.build(self)
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
    def __init__(self, parent, callbacks, state):
        Module.__init__(self, "input", parent, callbacks, state)
        self.button_frame = None
        self.submit_button = None

    def build(self):
        Module.build(self)
        self.input_box = TextAware(self.frame, bd=3, height=3)
        self.input_box.pack(expand=True, fill='both')
        self.input_box.configure(**textbox_config(bg=edit_color()))
        self.input_box.focus()
        self.textboxes.append(self.input_box)
        self.button_frame = ttk.Frame(self.frame)
        self.button_frame.pack(side='bottom', fill='x')
        self.submit_button = ttk.Button(self.button_frame, text="Submit", command=self.submit)
        self.submit_button.pack(side='right', expand=True)

    def submit(self):
        self.callbacks["Submit"]["callback"](text=self.input_box.get("1.0", "end-1c"))
        self.input_box.delete("1.0", "end")

