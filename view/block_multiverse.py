import tkinter
import tkinter.font as tkf
import json
import math
from pprint import pprint
from tkinter import ttk
from tkinter import Tk
import uuid

from PIL import ImageTk, Image
from view.colors import vis_bg_color

rainbow_colors = ['#9400D3', '#4B0082', '#0000FF', '#00FF00', '#FFFF00', '#FF7F00', '#FF0000']

class BlockMultiverse:
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.frame = None
        self.canvas = None
        self.build_canvas()
        self.scroll_ratio = 1
        self.bind_mouse_controls()
        self.window_offset = (0, 0)
        #self.draw_rectangle()
        #self.set_window(0, 0, 102, 202)

    def build_canvas(self):
        self.frame = ttk.Frame(self.parent_frame)
        background_color = vis_bg_color()
        self.canvas = tkinter.Canvas(self.frame, bg=background_color, width=1000, height=1000)

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

        # # windows zoom
        # def zoomer(event):
        #     if event.delta > 0:
        #         zoom_in(event)
        #         self.scroll_ratio *= 1.1
        #         self.canvas.scale("all", event.x, event.y, 1.1, 1.1)
        #     elif event.delta < 0:
        #         zoom_out(event)
        #         self.scroll_ratio *= 0.9
        #         self.canvas.scale("all", event.x, event.y, 0.9, 0.9)
        #     self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        #     #self.fix_text_zoom()
        #     #self.fix_image_zoom()

        # # linux zoom
        def zoom_in(event):
            self.scroll_ratio *= 1.1
            self.canvas.scale("all", self.window_offset[0], self.window_offset[1], 1, 1.1)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.fix_text_zoom()
            #self.fix_image_zoom()

        def zoom_out(event):
            self.scroll_ratio *= 0.9
            self.canvas.scale("all", self.window_offset[0], self.window_offset[1], 1, 0.9)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            # self.showtext = event.text > 0.8
            self.fix_text_zoom()
            #self.fix_image_zoom()

        # Mac and then linux scrolls
        #self.canvas.bind("<MouseWheel>", zoomer)
        self.canvas.bind("<Button-4>", zoom_in)
        self.canvas.bind("<Button-5>", zoom_out)

    def get_text_size(self):
        return max(1, math.floor(10 * self.scroll_ratio))

    def fix_text_zoom(self):
        size = self.get_text_size()
        for item in self.canvas.find_withtag("text"):
            self.canvas.itemconfig(item, font=('Arial', size))

    def draw_rectangle(self):
        self.canvas.create_rectangle(0, 0, 1000, 1000, outline="#fb0", fill="#fb0")
        self.canvas.create_rectangle(0, 0, 100, 200, outline="black", fill="black")
        self.frame.update()
        print(self.parent_frame.winfo_reqwidth())
        print(self.parent_frame.winfo_reqheight())

    def set_y_window(self, x0, y0, height, window_width=1000):
        self.reset_view()
        self.window_offset = (x0, y0)
        self.canvas.move("all", -x0, -y0)
        self.scroll_ratio = window_width / height
        self.canvas.scale("all", 0, 0, 1, self.scroll_ratio)

    def reset_view(self):
        self.canvas.scale("all", 0, 0, 1, 1 / self.scroll_ratio)
        self.scroll_ratio = 1
        self.canvas.move("all", self.window_offset[0], self.window_offset[1])
        self.window_offset = (0, 0)

    def node_clicked(self, x0, y0, height, token):
        self.set_y_window(x0, y0, height)

    def draw_multiverse(self, multiverse, ground_truth='', y_offset=0, depth=0,  canvas_height=1000,
                        block_width=100, color_index=0, prefix='', show_text=True, show_probabilities=False):
        if not multiverse:
            return
        y = y_offset
        x = depth * block_width
        rainbow_index = color_index % len(rainbow_colors)
        for token, node in multiverse.items():
            height = canvas_height * node['unnormalized_prob']
            is_ground_truth = (token == ground_truth[0]) if ground_truth else False
            color = 'black' if is_ground_truth else rainbow_colors[rainbow_index]

            identifier = str(uuid.uuid1())
            self.canvas.create_rectangle((x, y, x + block_width, y + height),
                                         fill=color, outline=color, tags=[identifier])

            self.canvas.tag_bind(f'{identifier}', "<Button-1>", lambda event, _token=token, _x=x, _y=y, _height=height: self.node_clicked(_x, _y, _height, _token))

            if show_text:
                #font_size = min(10, int(math.ceil(height)))
                font_size = 10
                text = token
                if show_probabilities:
                    text += f' ({node["normalized_prob"]}, {node["unnormalized_prob"]})'
                self.canvas.create_text(x + block_width/2, y + height/2, text=text, font=('Arial', font_size), tags=['text'])


            self.draw_multiverse(node['children'], ground_truth=ground_truth[1:] if is_ground_truth else '', y_offset=y,
                                 depth=depth + 1, canvas_height=canvas_height, block_width=block_width,
                                 color_index=rainbow_index, prefix=prefix+token)
            y += height
            rainbow_index = (rainbow_index + 1) % len(rainbow_colors)


