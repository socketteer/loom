import tkinter
import tkinter.font as tkf
import json
import math
from tkinter import ttk

from util.util_tree import node_ancestry
from util.custom_tks import TextAware
from PIL import ImageTk, Image
from colors import vis_bg_color, visited_node_bg_color, unvisited_node_bg_color,inactive_text_color,\
    active_text_color, selected_line_color, active_line_color, inactive_line_color, BLUE, expand_button_color, \
    edit_color


# TODO add to vis params
fixed_level_width = False
# TODO automatically calculate
collapsed_offset = 50
smooth_line_offset = 50
leaf_padding = 50
min_edit_box_height = 100


class TreeVis:
    def __init__(self, parent_frame, select_node_func, save_edits_func, vis_settings, state):
        self.parent_frame = parent_frame
        self.select_node_func = select_node_func
        self.save_edits_func = save_edits_func
        self.vis_settings = vis_settings
        self.state = state

        self.frame = None
        self.canvas = None
        self.textbox = None
        self.textbox_id = None
        self.editing_node_id = None
        self.node_coords = {}
        self.showtext = True
        self.root = None
        self.selected_node = None
        self.overflow_display = 'PAGE' #'FULL' or 'SCROLL' or 'PAGE'

        self.icons = {}
        self.resize_icon_events = []
        self.old_icons = []

        self.text_hidden = False
        self.buttons_hidden = False
        self.textbox_events = {}

        #TODO instead of root width, long textboxes should have scrollbars (possible?)
        #if not possible, multiple pages (!)
        self.root_width = self.vis_settings['textwidth']
        self.font = "Georgia"

        self.init_icons()

        self.build_canvas()
        self.scroll_ratio = 1
        self.bind_mouse_controls()


    def init_icon(self, icon_name, filename, size=18):
        self.icons[icon_name] = {}
        self.icons[icon_name]["size"] = size
        self.icons[icon_name]["img"] = (Image.open(f"./static/icons/{filename}"))
        self.icons[icon_name]["icon"] = ImageTk.PhotoImage(self.icons[icon_name]["img"].resize((self.icons[icon_name]['size'],
                                                                                                self.icons[icon_name]['size'])))

    def init_icons(self):
        self.init_icon("star", "star-48.png", 18)
        self.init_icon("empty_star", "empty_star-gray-48.png", 18)
        self.init_icon("children", "children-green-48.png", 18)
        self.init_icon("subtree", "subtree-green-48.png", 18)
        self.init_icon("ancestry", "ancestry-black-48.png", 18)
        self.init_icon("edit", "edit-blue-48.png", 16)
        self.init_icon("close", "minus-black-48.png", 14)
        self.init_icon("collapse_subtree", "collapse-black-48.png", 16)
        self.init_icon("collapse_children", "collapse-left-black-48.png", 14)
        self.init_icon("merge_parent", "leftarrow-lightgray-48.png", 16)
        self.init_icon("merge_children", "rightarrow-lightgray-48.png", 16)
        self.init_icon("add_link", "add-link-lightgray-48.png", 16)
        self.init_icon("change_link", "broken-link-lightgray-48.png", 16)
        self.init_icon("read", "read-lightgrey-48.png", 16)
        self.init_icon("info", "stats-lightgrey-48.png", 16)
        self.init_icon("delete", "delete-red-48.png", 16)
        self.init_icon("generate", "brain-blue-48.png", 18)
        self.init_icon("memory", "memory-blue-48.png", 18)
        self.init_icon("add_parent", "plus_left-blue-48.png", 16)
        self.init_icon("add_child", "plus-blue-48.png", 16)
        self.init_icon("shift_up", "up-lightgray-48.png", 16)
        self.init_icon("shift_down", "down-lightgray-48.png", 16)

    def build_canvas(self):
        self.frame = ttk.Frame(self.parent_frame)
        background_color = vis_bg_color()
        self.canvas = tkinter.Canvas(self.frame, bg=background_color)
        self.canvas.bind('<Double-Button-1>', lambda event: self.delete_textbox())

        hbar = tkinter.Scrollbar(self.frame, orient=tkinter.HORIZONTAL)
        hbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        hbar.config(command=self.canvas.xview)

        vbar = tkinter.Scrollbar(self.frame, orient=tkinter.VERTICAL)
        vbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        vbar.config(command=self.canvas.yview)

        self.canvas.config(
            xscrollcommand=hbar.set,
            yscrollcommand=vbar.set
        )
        self.canvas.pack(side=tkinter.LEFT, expand=True, fill=tkinter.BOTH)



    def bind_mouse_controls(self):
        # FIXME
        # def _on_mousewheel(event):
        #     self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # self.frame.bind_all("<MouseWheel>", _on_mousewheel)
        # self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # This is what enables scrolling with the mouse:
        def scroll_start(event):
            self.canvas.scan_mark(event.x, event.y)

        def scroll_move(event):
            self.canvas.scan_dragto(event.x, event.y, gain=1)

        self.canvas.bind("<ButtonPress-1>", scroll_start)
        self.canvas.bind("<B1-Motion>", scroll_move)

        # windows zoom
        def zoomer(event):
            if event.delta > 0:
                zoom_in(event)
                self.scroll_ratio *= 1.1
                self.canvas.scale("all", event.x, event.y, 1.1, 1.1)
            elif event.delta < 0:
                zoom_out(event)
                self.scroll_ratio *= 0.9
                self.canvas.scale("all", event.x, event.y, 0.9, 0.9)
            self.canvas.configure(scrollregion=self.canvas_bbox_padding(self.canvas.bbox("all")))
            self.fix_text_zoom()
            self.fix_image_zoom()

        # # linux zoom
        def zoom_in(event):
            self.scroll_ratio *= 1.1
            self.canvas.scale("all", event.x, event.y, 1.1, 1.1)
            self.canvas.configure(scrollregion=self.canvas_bbox_padding(self.canvas.bbox("all")))
            self.fix_text_zoom()
            self.fix_image_zoom()

        def zoom_out(event):
            self.scroll_ratio *= 0.9
            self.canvas.scale("all", event.x, event.y, 0.9, 0.9)
            self.canvas.configure(scrollregion=self.canvas_bbox_padding(self.canvas.bbox("all")))
            # self.showtext = event.text > 0.8
            self.fix_text_zoom()
            self.fix_image_zoom()

        # Mac and then linux scrolls
        self.canvas.bind("<MouseWheel>", zoomer)
        self.canvas.bind("<Button-4>", zoom_in)
        self.canvas.bind("<Button-5>", zoom_out)

        # Hack to make zoom work on Windows
        # root.bind_all("<MouseWheel>", zoomer)


    def fix_text_zoom(self):
        size = self.get_text_size()
        if size == 0:
            if not self.text_hidden:
                self.text_hidden = True
                for item in self.canvas.find_withtag("text"):
                    self.canvas.itemconfigure(item, state='hidden')
        else:
            if self.text_hidden:
                self.text_hidden = False
                for item in self.canvas.find_withtag("text"):
                    self.canvas.itemconfigure(item, state='normal')
            for item in self.canvas.find_withtag("text"):
                self.canvas.itemconfig(item, font=(self.font, size),
                                       width=self.get_width(item))


    def fix_image_zoom(self):
        approx_size = math.floor(self.scroll_ratio * 18)
        if approx_size < 5:
            if not self.buttons_hidden:
                self.buttons_hidden = True
                for item in self.canvas.find_withtag("image"):
                    self.canvas.itemconfigure(item, state='hidden')
        else:
            if self.buttons_hidden:
                self.buttons_hidden = False
                for item in self.canvas.find_withtag("image"):
                    self.canvas.itemconfigure(item, state='normal')
            for icon in self.icons:
                new_size = math.floor(self.scroll_ratio * self.icons[icon]["size"])
                self.old_icons.append(self.icons[icon]["icon"])
                self.icons[icon]["icon"] = ImageTk.PhotoImage(self.icons[icon]["img"].resize((new_size, new_size)))
            for resize_event in self.resize_icon_events:
                resize_event()



    # TODO save default widths (because some nodes have different widths)
    def get_width(self, item):
        #width = int(self.canvas.itemcget(item, "width"))
        width = self.vis_settings['textwidth']
        return math.floor(width * self.scroll_ratio)


    def get_text_size(self):
        return math.floor(self.vis_settings['textsize'] * self.scroll_ratio)

    #################################
    #   Drawing
    #################################


    def draw(self, root_node, selected_node, center_on_selection=False):
        # print(self.vis_settings)
        self.canvas.delete('data')
        self.root = root_node
        self.selected_node = selected_node
        self.delete_textbox()

        # TODO change this
        if not self.root.get('open', False):
            self.collapse_all()

        if not self.selected_node.get('open', False):
            #TODO also expand ancestors
            self.expand_node(self.selected_node)

        tree_structure_map = self.calc_tree_structure(root_node, self.selected_node)
        self.node_coords = {}
        self.resize_icon_events = []

        self.draw_node(root_node, 100, 100, tree_structure_map, self.selected_node["id"])

        self.canvas.scale("all", 0, 0, self.scroll_ratio, self.scroll_ratio)

        region = self.canvas_bbox_padding(self.canvas.bbox("all"))
        self.canvas.configure(scrollregion=region)
        self.fix_text_zoom()
        self.fix_image_zoom()

        if center_on_selection:
            if self.selected_node["id"] in self.node_coords:
                self.center_view_on_canvas_coords(*self.node_coords[self.selected_node["id"]])
            else:
                print('error: not in node coords')


    def refresh_selection(self, root_node, selected_node):
        self.selected_node = selected_node
        if not self.selected_node.get("open", False):
            self.expand_node(self.selected_node)
            self.draw(self.root, self.selected_node)
            return
        self.delete_textbox()
        tree_structure_map = self.calc_tree_structure(root_node, self.selected_node)
        for node_id, structure in tree_structure_map.items():
            if self.state.tree_node_dict[node_id].get("open", False):
                if structure['active']:

                    self.canvas.itemconfig(f'text-{node_id}', fill=active_text_color())
                    if node_id == self.selected_node["id"]:
                        self.canvas.itemconfig(f'box-{node_id}', outline=selected_line_color(), width=2)
                        self.canvas.itemconfig(f'lines-{node_id}', fill=selected_line_color(), width=2)
                        self.canvas.itemconfig(f'ghostlines-{node_id}', fill=selected_line_color())
                    else:
                        self.canvas.itemconfig(f'box-{node_id}', outline=active_line_color(), width=1)
                        self.canvas.itemconfig(f'lines-{node_id}', fill=active_line_color(), width=1)
                else:
                    self.canvas.itemconfig(f'lines-{node_id}', fill=inactive_line_color(), width=1)
                    self.canvas.itemconfig(f'ghostlines-{node_id}', fill=inactive_line_color())
                    self.canvas.itemconfig(f'text-{node_id}', fill=inactive_text_color())
                    self.canvas.itemconfig(f'box-{node_id}', outline=inactive_line_color(), width=1)
                if self.state.tree_node_dict[node_id].get("visited", False):
                    fill = visited_node_bg_color()
                else:
                    fill = unvisited_node_bg_color()
                self.canvas.itemconfig(f'box-{node_id}', fill=fill)


        if self.selected_node["id"] in self.node_coords:
            self.center_view_on_canvas_coords(*self.node_coords[self.selected_node["id"]])


    def draw_node(self, node, nodex, nodey, tree_structure_map, selected_id):
        # Draw textbox
        self.node_coords[node["id"]] = (nodex, nodey)

        if not node.get("open", False):
            bbox = self.draw_expand_node_button(node, nodex, nodey)
            return

        display_text = self.vis_settings['displaytext'] and self.showtext
        if display_text:
            bbox = self.draw_textbox(node, nodex, nodey, tree_structure_map, selected_id)
            offset = 10
        else:
            bbox = (nodex, nodey, nodex, nodey)
            offset = 0

        textheight = bbox[3] - bbox[1]
        textwidth = bbox[2] - bbox[0]
        width_diff = self.vis_settings['textwidth'] - textwidth \
            if (self.vis_settings['displaytext'] and fixed_level_width) else 0

        # Draw children with increasing offsets
        child_offset = 0
        child_offset_collapsed = 0
        for child in node['children']:
            if self.vis_settings["horizontal"]:
                childx = nodex + self.vis_settings['leveldistance'] + textwidth + width_diff
                childy = nodey + (child_offset * self.vis_settings['leafdist'])\
                         + (child_offset_collapsed * collapsed_offset)
                parentx = nodex + textwidth
                parenty = nodey
            else:
                childx = nodex + (child_offset * self.vis_settings['leafdist'])\
                         + (child_offset_collapsed * collapsed_offset)
                childy = nodey + self.vis_settings['leveldistance'] + textheight

                parentx = nodex
                parenty = nodey + textheight


            self.draw_node(child, childx, childy, tree_structure_map, selected_id)
            child_offset = child_offset + tree_structure_map[child["id"]]['offset']
            child_offset_collapsed += tree_structure_map[child["id"]]['offset2']

            # Draw line to child
            if tree_structure_map[child["id"]] == selected_id:
                color = selected_line_color()
                width = 2
            else:
                color = active_line_color() if tree_structure_map[child["id"]]['active'] else inactive_line_color()
                width = 2 if tree_structure_map[child["id"]]['active'] else 1

            self.draw_line(parentx - offset, parenty - offset, childx - offset, childy - offset,
                           name=f'lines-{child["id"]}',
                           fill=color, activefill=BLUE, width=width, offset=smooth_line_offset, smooth=True,
                           method=lambda event, node_id=child["id"]: self.select_node_func(node_id=node_id))

        #TODO lightmode
        if "ghostchildren" in node:
            parentx = nodex + textwidth
            parenty = nodey
            for ghost_id in node["ghostchildren"]:
                ghost = self.state.tree_node_dict.get(ghost_id, None)
                if ghost is None:
                    continue
                if ghost.get("open", False) and ghost["id"] in self.node_coords:
                    ghostx, ghosty = self.node_coords[ghost["id"]]
                    if tree_structure_map[ghost["id"]] == selected_id:
                        color = active_line_color()
                    else:
                        color = inactive_line_color()
                    self.draw_line(parentx - offset, parenty - offset, ghostx - offset, ghosty - offset,
                                   name=f'ghostlines-{ghost["id"]}',
                                   fill=color, activefill=BLUE, offset=smooth_line_offset, smooth=True,
                                   method=lambda event, node_id=ghost["id"]: self.select_node_func(node_id=node_id))
                else:
                    #print("drew collapsed ghostchild")
                    #TODO fix position
                    self.draw_line(parentx - offset, parenty - offset,
                                   parentx + self.vis_settings["leveldistance"] - offset,
                                   parenty - offset,
                                   name=f'ghostlines-{ghost["id"]}',
                                   fill=inactive_line_color(), activefill=BLUE, offset=smooth_line_offset, smooth=True,
                                   method=lambda event, node_id=ghost["id"]: self.select_node_func(node_id=node_id))
                    self.draw_expand_node_button(ghost, parentx + self.vis_settings["leveldistance"], parenty, ghost=True)
                    return


    def draw_line(self, x1, y1, x2, y2, fill, name, width=1, activefill=None, offset=0, smooth=True ,method=None):

        if smooth:
            line_id = self.canvas.create_line(x1, y1, x1 + offset, y1, x2 - offset, y2, x2, y2, smooth=smooth,
                                              fill=fill,
                                              activefill=activefill,
                                              width=width,
                                              tags=[f'{name}', 'data', 'lines'])
        else:
            line_id = self.canvas.create_line(x1, y1, x2, y2,
                                              fill=fill,
                                              activefill=activefill,
                                              width=width,
                                              tags=[f'{name}', 'data', 'lines'])
        if method is not None:
            self.canvas.tag_bind(f'{name}', "<Button-1>", method)
        self.canvas.tag_lower(line_id)


    def split_text(self, node):
        text = node['text']
        font = tkinter.font.Font(font=self.font)
        text_width = font.measure(text)
        lineheight = font.metrics('linespace')
        max_lines = math.floor((self.vis_settings['leafdist'] - leaf_padding) / lineheight)
        lines_estimate = text_width / self.vis_settings['textwidth']
        try:
            new_text_len = int(math.floor(len(text) * max_lines / lines_estimate))
        except ZeroDivisionError:
            return text
        text = node['text'][:new_text_len]
        return text


    def draw_textbox(self, node, nodex, nodey, tree_structure_map, selected_id):
        text_color = active_text_color() if tree_structure_map[node["id"]]['active'] else inactive_text_color()
        width = self.root_width if node['id'] == self.root['id'] else self.vis_settings['textwidth']
        text = self.split_text(node) if self.overflow_display == 'PAGE' else node['text']
        text_id = self.canvas.create_text(
            nodex, nodey, fill=text_color, activefill=BLUE,
            font=(self.font, self.get_text_size()),
            width=width,
            text=text,
            tags=[f'text-{node["id"]}', 'data', 'text'],
            anchor=tkinter.NW
        )
        padding = (-10, -10, 10, 10)
        bbox = self.canvas.bbox(text_id)
        box = tuple(map(lambda i, j: i + j, padding, bbox))

        fill = visited_node_bg_color() if node.get("visited", False) else unvisited_node_bg_color()
        outline_color = selected_line_color() if selected_id == node["id"] else \
            (active_line_color() if tree_structure_map[node["id"]]['active'] else inactive_line_color())
        width = 2 if tree_structure_map[node["id"]]['active'] else 1
        rect_id = self.canvas.create_rectangle(box, outline=outline_color, width=width,
                                               activeoutline=BLUE, fill=fill,
                                               tags=[f'box-{node["id"]}', 'data'])
        self.canvas.tag_raise(text_id, rect_id)
        self.canvas.tag_bind(
            f'text-{node["id"]}', "<Button-1>", lambda event, node_id=node["id"]: self.edit_node(node_id=node_id,
                                                                                                 box=box,
                                                                                                 text=node['text'])
        )
        self.textbox_events[node["id"]] = lambda node_id=node["id"]: self.edit_node(node_id=node_id,
                                                                                    box=box,
                                                                                    text=node['text'])
        self.canvas.tag_bind(
            f'box-{node["id"]}', "<Button-1>", self.box_click(node["id"], box, node["text"]))


        if node is not self.root:
            self.draw_collapse_button(node, box)
        if self.vis_settings["showbuttons"]:
            self.draw_buttons(node, box)
        self.draw_bookmark_star(node, box)
        return box


    def canvas_bbox_padding(self, bbox):
        padding = (-300, -300, 300, 300)
        box = tuple(map(lambda i, j: i + j, padding, bbox))
        return box


    def draw_expand_node_button(self, node, nodex, nodey, ghost=False):
        text_id = self.canvas.create_text(
            nodex - 4, nodey - 6, fill='white', activefill=BLUE,
            font=(self.font, self.get_text_size()),
            text='+',
            tags=[f'expand-{node["id"]}', 'data', 'text'],
            anchor=tkinter.NW
        )
        padding = (-5, -5, 5, 5)
        bbox = self.canvas.bbox(text_id)
        box = tuple(map(lambda i, j: i + j, padding, bbox))
        outline_color = inactive_line_color()
        fill = visited_node_bg_color() if ghost else expand_button_color()
        rect_id = self.canvas.create_rectangle(box, outline=outline_color,
                                               activeoutline=BLUE, fill=fill,
                                               tags=[f'expand-box-{node["id"]}', 'data'])
        self.canvas.tag_raise(text_id, rect_id)
        self.canvas.tag_bind(
            f'expand-{node["id"]}', "<Button-1>", lambda event, _node=node:
            self.expand_node(_node))
        self.canvas.tag_bind(
            f'expand-box-{node["id"]}', "<Button-1>", lambda event, _node=node:
            self.expand_node(_node))

        return box


    def draw_buttons(self, node, box):
        # TODO dynamic button positions

        if node is not self.root:
            # if node has siblings
            if len(self.state.tree_node_dict[node["parent_id"]]["children"]) > 1:
                if box[2] - box[0] > 200:
                    self.draw_shiftup_button(node, box)
                    self.draw_shiftdown_button(node, box)


        # TODO conditional on generated, etc
        if box[2] - box[0] > 200:
            self.draw_read_button(node, box)
            self.draw_memory_button(node, box)
            self.draw_info_button(node, box)
            self.draw_generate_button(node, box)
            self.draw_collapse_except_subtree_button(node, box)
            self.draw_changeparent_button(node, box)
            self.draw_addlink_button(node, box)

            self.draw_newchild_button(node, box)
            self.draw_newparent_button(node, box)
            self.draw_mergeparent_button(node, box)

        self.draw_delete_button(node, box)
        self.draw_edit_button(node, box)



        if len(node["children"]) > 0:
            if box[2] - box[0] > 200:
                self.draw_collapse_subtree_button(node, box)
                self.draw_expand_subtree_button(node, box)
                self.draw_expand_children_button(node, box)
                self.draw_collapse_children_button(node, box)
                self.draw_mergechildren_button(node, box)

    def draw_icon(self, node, x_pos, y_pos, icon_name, name=None, method=None):
        if name is None:
            name = icon_name
        icon_id = self.canvas.create_image(x_pos, y_pos,
                                           image=self.icons[icon_name]["icon"],
                                           tags=[f'{name}-{node["id"]}', 'data', 'image'])
        self.resize_icon_events.append(lambda: self.canvas.itemconfig(icon_id, image=self.icons[icon_name]["icon"]))
        self.canvas.tag_bind(
            f'{name}-{node["id"]}', "<Button-1>", method)
        return icon_id



    def draw_read_button(self, node, box):
        self.draw_icon(node, box[0] + (box[2] - box[0]) / 2 - 31, box[3] + 12, "read",
                       method=lambda event, _node=node: self.read_mode(_node))

    def draw_info_button(self, node, box):
        self.draw_icon(node, box[0] + (box[2] - box[0])/2 - 11, box[3] + 12, "info",
                       method=lambda event, _node=node: self.show_info(_node))

    def draw_edit_button(self, node, box):
        self.draw_icon(node, box[0] + (box[2] - box[0])/2 + 11, box[3] + 12, "edit",
                       method=lambda event, _node_id=node['id']: self.textbox_events[node['id']](_node_id))

    def draw_delete_button(self, node, box):
        self.draw_icon(node, box[0] + (box[2] - box[0])/2 + 31, box[3] + 12, "delete",
                       method=lambda event, _node=node: self.delete_node(_node))



    def draw_newchild_button(self, node, box):
        self.draw_icon(node, box[2] - 13, box[3] + 12, "add_child",
                       method=lambda event, _node=node: self.new_child(_node))

    def draw_generate_button(self, node, box):
        self.draw_icon(node, box[2] - 36, box[3] + 12, "generate",
                       method=lambda event, _node=node: self.generate(_node))

    def draw_memory_button(self, node, box):
        self.draw_icon(node, box[2] - 59, box[3] + 12, "memory",
                       method=lambda event, _node=node: self.new_child(_node))

    def draw_collapse_button(self, node, box):
        self.draw_icon(node, box[0] + 7, box[1] - 10, "close",
                       method=lambda event, _node=node: self.collapse_node(_node))

    def draw_collapse_subtree_button(self, node, box):
        self.draw_icon(node, box[0] + 27, box[1] - 10, "collapse_subtree",
                       method=lambda event, _node=node: self.collapse_node_subtree(_node))

    def draw_collapse_except_subtree_button(self, node, box):
        self.draw_icon(node, box[0] + 50, box[1] - 10, "ancestry",
                       method=lambda event, _node=node: self.collapse_except_subtree(_node))

    def draw_mergeparent_button(self, node, box):
        self.draw_icon(node, box[0] + 72, box[1] - 10, "merge_parent",
                       method=lambda event, _node=node: self.merge_parent(_node))

    def draw_changeparent_button(self, node, box):
        self.draw_icon(node, box[0] + 94, box[1] - 10, "change_link",
                       method=lambda event, _node=node: self.change_parent(_node))

    def draw_addlink_button(self, node, box):
        self.draw_icon(node, box[0] + 116, box[1] - 10, "add_link",
                       method=lambda event, _node=node: self.new_ghostparent(_node))

    def draw_newparent_button(self, node, box):
        self.draw_icon(node, box[0] + 138, box[1] - 10, "add_parent",
                       method=lambda event, _node=node: self.new_parent(_node))

    def draw_shiftup_button(self, node, box):
        self.draw_icon(node, box[0] + 160, box[1] - 10, "shift_up",
                       method=lambda event, _node=node: self.shift_up(_node))

    def draw_shiftdown_button(self, node, box):
        self.draw_icon(node, box[0] + 182, box[1] - 10, "shift_down",
                       method=lambda event, _node=node: self.shift_down(_node))


    def draw_mergechildren_button(self, node, box):
        self.draw_icon(node, box[2] - 79, box[1] - 10, "merge_children",
                       method=lambda event, _node=node: self.merge_children(_node))

    def draw_collapse_children_button(self, node, box):
        self.draw_icon(node, box[2] - 57, box[1] - 10, "collapse_children",
                       method=lambda event, _node=node: self.collapse_children(_node))

    def draw_expand_subtree_button(self, node, box):
        self.draw_icon(node, box[2] - 37, box[1] - 10, "subtree",
                       method=lambda event, _node=node: self.expand_node_subtree(_node))

    def draw_expand_children_button(self, node, box):
        self.draw_icon(node, box[2] - 14, box[1] - 10,  "children",
                       method=lambda event, _node=node: self.expand_children(_node))


    def draw_bookmark_star(self, node, box):
        self.draw_icon(node, box[0]-15, box[1] + (box[3] - box[1])/2,
                       icon_name="star" if node.get("bookmark", False) else "empty_star",
                       name="bookmark",
                       method=lambda event, _node=node: self.toggle_bookmark(_node))


    #################################
    #   Expand/Collapse
    #################################

    def select_node(self, node):
        if isinstance(node, str):
            node = self.state.tree_node_dict[node]
        self.selected_node = node
        self.select_node_func(node_id=node["id"])


    def expand_node(self, node, change_selection=True, center_selection=False):
        ancestry = node_ancestry(node, self.state.tree_node_dict)
        for ancestor in ancestry:
            ancestor['open'] = True
        if change_selection or not self.selected_node['open']:
            self.select_node(node)
        self.draw(self.root, self.selected_node, center_on_selection=center_selection)


    def expand_children(self, node):
        for child in node["children"]:
            child['open'] = True
        self.draw(self.root, self.selected_node, center_on_selection=False)


    def collapse_node(self, node, select_parent=False):
        if self.selected_node == node or select_parent:
            if node == self.root:
                self.select_node(self.root)
            else:
                node["open"] = False
                self.select_node(self.state.tree_node_dict[node["parent_id"]])
        else:
            node["open"] = False
        self.draw(self.root, self.selected_node, center_on_selection=False)


    def expand_all(self):
        self.expand_subtree(self.root)


    def collapse_all(self, immune=None):
        self.collapse_subtree(self.root, immune=immune)


    def collapse_subtree(self, root, immune=None):
        if immune is None:
            immune = []
        root["open"] = False
        for child in root["children"]:
            if child not in immune:
                self.collapse_subtree(child, immune)


    def expand_subtree(self, root):
        root['open'] = True
        for child in root["children"]:
            self.expand_subtree(child)


    def collapse_node_subtree(self, root):
        self.collapse_subtree(root)
        self.collapse_node(root, select_parent=True)


    def expand_node_subtree(self, root):
        self.expand_subtree(root)
        self.expand_node(root, change_selection=False)


    def collapse_except_subtree(self, root):
        self.collapse_all(immune=[root])
        self.expand_node(root, center_selection=True)


    def collapse_children(self, node):
        self.collapse_subtree(node)
        self.expand_node(node, change_selection=False)



    #################################
    #   Topology
    #################################

    # all these should use callbacks
    def merge_parent(self, node):
        pass

    def merge_children(self, node):
        pass

    def change_parent(self, node):
        pass

    def new_ghostparent(self, node):
        pass

    def new_parent(self, node):
        pass

    def new_child(self, node):
        pass

    def shift_up(self, node):
        pass

    def shift_down(self, node):
        pass

    #################################
    #   Interaction
    #################################


    def box_click(self, node_id, box, text):
        if text == '':
            return lambda event, node_id=node_id, box=box: self.edit_node(node_id=node_id, box=box, text=text)
        else:
            return lambda event, node_id=node_id: self.select_node(node=node_id)


    def edit_node(self, node_id, box, text):
        # self.select_node_func(node_id=node_id)
        self.delete_textbox()
        self.editing_node_id = node_id

        fontheight = tkinter.font.Font(font=(self.font, self.get_text_size())).metrics('linespace')
        self.textbox = TextAware(self.canvas, bg=edit_color(), fg='white', padx=10, pady=10, height=10,
                                 font=(self.font, self.get_text_size()))
        self.textbox.insert(tkinter.END, text)

        textbox_height = box[3] - box[1] if min_edit_box_height < box[3] - box[1] else min_edit_box_height
        textbox_width = self.vis_settings['textwidth']
        self.textbox_id = self.canvas.create_window(box[0] + (box[2] - box[0]) / 2, box[1] + (box[3] - box[1]) / 2,
                                                    window=self.textbox, height=textbox_height, width=textbox_width)


    def delete_textbox(self, save=True):
        if self.textbox is not None:
            if save:
                self.save_edits_func()

            self.canvas.delete(self.textbox_id)
            #self.textbox.destroy()
            self.textbox = None
            self.editing_node_id = None
            self.textbox_id = None


    # TODO use callback
    def toggle_bookmark(self, node):
        if node.get("bookmark", False):
            node["bookmark"] = False
        else:
            node["bookmark"] = True
        self.draw(self.root, self.selected_node)

    def delete_node(self, node):
        pass

    def generate(self, node):
        pass

    def read_mode(self, node):
        pass

    def show_info(self, node):
        pass


    #################################
    #   Util
    #################################


    def calc_tree_structure(self, node, selected_node, node_id_to_structure=None):
        # Create the map from id to structure if this is the root node
        if node_id_to_structure is None:
            node_id_to_structure = {}

        # default structure
        structure = {
            "depth": 1,
            "descendants": 0,
            "offset": 1 if node.get('open', False) else 0,
            "offset2": 1 if not node.get('open', False) else 0,
            "active": node["id"] == selected_node["id"]
        }

        # Have each child figure out their own structure and add themselves to the map recursively
        for child in node["children"]:
            self.calc_tree_structure(child, selected_node, node_id_to_structure)

        # Calculate own structure information based on children
        if node.get('open', False):
            for child in node["children"]:
                child_structure = node_id_to_structure[child["id"]]
                # Depth is max of child depth + 1
                structure["depth"] = max(structure["depth"], child_structure["depth"] + 1)
                # Descendants is sum of child descendants + 1 for the child itself
                structure["descendants"] += child_structure["descendants"] + 1
                structure["offset"] += child_structure["offset"]
                structure["offset2"] += child_structure["offset2"]
                # Active if any child is active
                structure["active"] = True if child_structure["active"] else structure["active"]

            if len(node["children"]) != 0 and structure["offset"] > 1:
                structure["offset"] -= 1
            elif len(node["children"]) != 0 and structure["offset2"] > 1:
                 structure["offset2"] -= 1
            #TODO
            # if len(node["children"]) != 0 and structure["offset2"] > 1:
            #     structure["offset2"] -= 1
        node_id_to_structure[node["id"]] = structure
        return node_id_to_structure


    def center_view_on_canvas_coords(self, x, y):
        x = x * self.scroll_ratio
        y = y * self.scroll_ratio
        x1, y1, x2, y2 = self.canvas.bbox("all")
        screen_width_in_canvas_coords = self.canvas.canvasx(self.canvas.winfo_width()) - self.canvas.canvasx(0)
        screen_height_in_canvas_coords = self.canvas.canvasy(self.canvas.winfo_height()) - self.canvas.canvasy(0)
        self.canvas.xview_moveto((x - screen_width_in_canvas_coords / 2) / (x2 - x1))
        self.canvas.yview_moveto((y - screen_height_in_canvas_coords / 2) / (y2 - y1))


    def reset_zoom(self):
        # TODO unknown bug, fix
        self.canvas.scale("all", 0, 0, 1 / self.scroll_ratio, 1 / self.scroll_ratio)
        self.canvas.configure(scrollregion=self.canvas_bbox_padding(self.canvas.bbox("all")))
        self.scroll_ratio = 1
        self.fix_text_zoom()
        self.fix_image_zoom()




