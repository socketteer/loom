import math
import tkinter
import uuid
import openai
from tkinter import ttk
from decimal import *
from util.custom_tks import TextAware
from util.gpt_util import logprobs_to_probs
from util.tokenizer import tokenize, token_to_word


rainbow_colors = ['#9400D3', '#4B0082', '#0000FF', '#00FF00', '#FFFF00', '#FF7F00', '#FF0000']

default_y_scale = 1

class BlockMultiverse:
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame

        self.frame = None
        self.multiverse_frame = None
        self.bottom_input_frame = None
        self.past_box = None
        self.canvas = None
        self.wavefunction = None
        self.selected_id = None
        self.window_height = 1000
        self.node_info = {}
        self.build_canvas()
        self.build_past_box()
        self.window_offset = (0, 0)
        self.y_scale = default_y_scale
        self.x_scale = 1
        self.bind_mouse_controls()
        self.prompt = None

    def clear_multiverse(self):
        self.wavefunction = None
        self.selected_id = None
        self.canvas.delete("all")
        self.node_info = {}
        self.set_pastbox_text('', '')
        self.prompt = None
        self.reset_view()

    def build_canvas(self):
        self.frame = ttk.Frame(self.parent_frame)
        self.multiverse_frame = ttk.Frame(self.frame)
        self.multiverse_frame.pack(expand=True, fill=tkinter.BOTH)
        self.canvas = tkinter.Canvas(self.multiverse_frame, bg="#808080")

        hbar = tkinter.Scrollbar(self.multiverse_frame, orient=tkinter.HORIZONTAL)
        hbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        hbar.config(command=self.canvas.xview)

        vbar = tkinter.Scrollbar(self.multiverse_frame, orient=tkinter.VERTICAL)
        vbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        vbar.config(command=self.canvas.yview)

        self.canvas.config(
            xscrollcommand=hbar.set,
            yscrollcommand=vbar.set
        )
        self.canvas.pack(side=tkinter.LEFT, expand=True, fill=tkinter.BOTH)

    def build_past_box(self):
        self.bottom_input_frame = ttk.Frame(self.frame)
        self.bottom_input_frame.pack(side="bottom", fill="both")
        self.past_box = TextAware(self.bottom_input_frame, bd=3, height=3)
        self.past_box.pack(expand=True, fill='x')
        self.past_box.configure(
            foreground='white',
            background='black',
            wrap="word",
        )
        self.past_box.tag_configure("prompt", foreground="gray")
        self.past_box.configure(state="disabled")

    def set_pastbox_text(self, prompt_text='', completion_text=''):
        if self.past_box:
            self.past_box.configure(state="normal")
            self.past_box.delete('1.0', "end")
            self.past_box.insert('1.0', prompt_text, "prompt")
            self.past_box.insert("end-1c", completion_text)
            self.past_box.configure(state="disabled")
            self.past_box.see("end")

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
            self.y_scale *= 1.1
            self.x_scale *= 1.1
            self.canvas.scale("all", event.x, event.y, 1, 1.1)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.fix_text_zoom()
            #self.fix_image_zoom()

        def zoom_out(event):
            self.y_scale *= 0.9
            self.x_scale *= 0.9
            self.canvas.scale("all", event.x, event.y, 1, 0.9)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            # self.showtext = event.text > 0.8
            self.fix_text_zoom()
            #self.fix_image_zoom()

        # Mac and then linux scrolls
        #self.canvas.bind("<MouseWheel>", zoomer)
        self.canvas.bind("<Button-4>", zoom_in)
        self.canvas.bind("<Button-5>", zoom_out)

    def get_text_size(self, original_size=10):
        text_size = max(1, math.floor(original_size * self.y_scale))
        return min(text_size, 12)

    def fix_text_zoom(self):
        # size = self.get_text_size()
        # for item in self.canvas.find_withtag("text"):
        #     self.canvas.itemconfig(item, font=('Arial', size))
        for key, info in self.node_info.items():
            size = self.get_text_size(info['font_size'])
            self.canvas.itemconfig(info['text_widget'], font=('Arial', size))

    def set_y_window(self, x0, y0, height):
        old_y_scale = self.y_scale
        self.reset_view()
        self.window_offset = (x0, y0)
        self.canvas.move("all", -x0, -y0)
        self.y_scale = self.window_height / height
        magnification = self.y_scale / old_y_scale

        print('\nmagnification: *', "{:.2f}".format(magnification))
        print('total magnification: ', "{:.2f}".format(self.y_scale)) 
        print('+{:.2f} bits'.format(math.log(magnification,2)))
        print('total bits: ', "{:.2f}".format(math.log(self.y_scale, 2)))

        self.canvas.scale("all", 0, 0, 1, self.y_scale)
        self.fix_text_zoom()

    def reset_view(self):
        self.canvas.scale("all", 0, 0, 1, default_y_scale / self.y_scale)
        self.y_scale = default_y_scale
        self.canvas.move("all", self.window_offset[0], self.window_offset[1])
        self.window_offset = (0, 0)
        self.fix_text_zoom()
        if self.prompt:
            self.set_pastbox_text(prompt_text=self.prompt)

    def active_wavefunction(self):
        return self.wavefunction and self.selected_id

    def active_info(self):
        return self.node_info[self.selected_id]

    def node_clicked(self, x0, y0, height, node_id):
        self.selected_id = node_id
        #print(self.node_info[node_id]['token'])
        self.set_y_window(x0, y0, height)
        prefix_text = self.node_info[node_id]['prefix']
        self.set_pastbox_text(prompt_text=self.prompt if self.prompt else '', 
                          completion_text=prefix_text)

    def draw_multiverse(self, multiverse, ground_truth='', block_width=150, start_position=(0, 0), color_index=0,
                        prefix='', show_text=True, show_probabilities=False, prompt=''):
        if not self.prompt:
            self.prompt = prompt
        self.set_pastbox_text(prompt_text=self.prompt)
        if not self.wavefunction:
            self.wavefunction = multiverse
        else:
            if self.selected_id:
                #self.node_info[self.selected_id]['node']['children'] = multiverse
                prefix = self.node_info[self.selected_id]['prefix']
            else:
                return
        self.propagate(multiverse, ground_truth, prefix, block_width, start_position, color_index, show_text,
                       y_offset=0, depth=1)

    # TODO should work purely in absolute coordinates
    def propagate(self, multiverse, ground_truth, prefix, block_width, start_position, color_index, show_text,
                  y_offset, depth):
        x = start_position[0] + (depth * block_width)

        rainbow_index = color_index % len(rainbow_colors)
        for token, node in multiverse.items():
            y = start_position[1] + y_offset
            height = Decimal(self.window_height) * Decimal(node['unnormalized_prob'])
            is_ground_truth = (token == ground_truth[0]) if ground_truth else False

            self.draw_block(x, y, token, prefix, node['unnormalized_prob'], height, block_width, is_ground_truth,
                            show_text, rainbow_index)

            self.propagate(node['children'], ground_truth=ground_truth[1:] if is_ground_truth else None,
                           prefix=prefix + token,
                           block_width=block_width,
                           start_position=start_position,
                           color_index=rainbow_index,
                           show_text=show_text,
                           y_offset=y_offset,
                           depth=depth + 1,
                           )
            y_offset += height
            rainbow_index = (rainbow_index + 1) % len(rainbow_colors)

    def draw_block(self, x, y, token, prompt, probability, height, block_width, is_ground_truth, show_text, rainbow_index):
        color = 'black' if is_ground_truth else rainbow_colors[rainbow_index]

        identifier = str(uuid.uuid1())
        self.draw_rectangle_absolute(x, y, x + block_width, y + height, fill=color, activefill='gray', activeoutline='white',
                                     outline=color, tags=[identifier])

        self.canvas.tag_bind(f'{identifier}', "<Button-1>",
                             lambda event, _id=identifier, _x=x, _y=y, _height=height: self.node_clicked(_x, _y,
                                                                                                         _height,
                                                                                                         _id))

        self.node_info[identifier] = {
            'id': identifier,
            'prefix': prompt + token,
            'token': token,
            'amplitude': probability,
            'x': x,
            'y': y,
        }

        if show_text:
            text_color = 'blue' if color == '#FFFF00' else 'white'  # if is_ground_truth else 'black'
            font_size = min(12, int(math.ceil(height * self.y_scale / 2)))
            text = token
            self.node_info[identifier]['font_size'] = Decimal(font_size) / Decimal(self.y_scale)
            self.node_info[identifier]['text_widget'] = self.draw_text_absolute(x + block_width / 2, y + height / 2,
                                                                                text=text,
                                                                                font=('Arial', font_size),
                                                                                tags=['text', f'text-{identifier}'],
                                                                                fill=text_color)
        return identifier

    # def propagate_realtime(self, prompt, ground_truth='', block_width=150, parent_position=(0,0), max_depth=3,
    #                        unnormalized_amplitude=1, threshold=0.01, rainbow_index=0, engine='ada'):
    #     if ground_truth and isinstance(ground_truth, str):
    #         ground_truth = tokenize(ground_truth)
    #         ground_truth = [token_to_word(token).replace('Ġ', ' ') for token in ground_truth]
    #     self.propagate_and_draw(prompt, ground_truth, block_width, parent_position, max_depth, unnormalized_amplitude,
    #                             threshold, rainbow_index, engine)
    #
    # def propagate_and_draw(self, prompt, ground_truth, block_width, parent_position, max_depth,
    #                        unnormalized_amplitude, threshold, rainbow_index, engine):
    #     if max_depth == 0:
    #         return
    #     response = openai.Completion.create(prompt=prompt,
    #                                         max_tokens=1,
    #                                         n=1,
    #                                         temperature=0,
    #                                         logprobs=100,
    #                                         engine=engine)
    #     logprobs = response.choices[0]["logprobs"]["top_logprobs"][0]
    #     probs = {k: logprobs_to_probs(v) * unnormalized_amplitude for k, v in sorted(logprobs.items(),
    #                                                                                  key=lambda item: item[1],
    #                                                                                  reverse=True)}
    #
    #     ground_truth_token = ground_truth[0] if ground_truth else 'NO GROUND TRUTH'
    #     x = parent_position[0] + block_width
    #     y_offset = 0
    #     for token, probability in probs.items():
    #         y = parent_position[1] + y_offset
    #         height = self.window_height * probability
    #         is_ground_truth = (token == ground_truth_token) if ground_truth else False
    #         self.draw_block(x, y, token, prompt, probability, height, block_width, is_ground_truth, True, rainbow_index)
    #
    #         if token == ground_truth_token:
    #             self.propagate_and_draw(prompt + token, ground_truth[1:], block_width, (x, y), max_depth-1, probability,
    #                                     threshold, rainbow_index, engine)
    #         elif probability > threshold:
    #             self.propagate_and_draw(prompt + token, '', block_width, (x, y), max_depth - 1,
    #                                     probability, threshold, rainbow_index, engine)
    #         else:
    #             break
    #         y_offset += height
    #         rainbow_index = (rainbow_index + 1) % len(rainbow_colors)


    def map_to_scaled_coordinates(self, x, y):
        x = x - self.window_offset[0]
        y = y - self.window_offset[1]
        y = y * self.y_scale
        return x, y

    def map_to_absolute_coordinates(self, x, y):
        x = x + self.window_offset[0]
        y = y + self.window_offset[1]
        y = Decimal(y) / Decimal(self.y_scale)
        return x, y

    # draw a rectangle with size and coordinates regardless of current zoom / pan state
    def draw_rectangle_absolute(self, x0, y0, x1, y1, **kwargs):
        rel_x0, rel_y0 = self.map_to_scaled_coordinates(x0, y0)
        rel_x1, rel_y1 = self.map_to_scaled_coordinates(x1, y1)
        return self.canvas.create_rectangle((rel_x0, rel_y0, rel_x1, rel_y1), **kwargs)

    def draw_text_absolute(self, x, y, **kwargs):
        rel_x, rel_y = self.map_to_scaled_coordinates(x, y)
        #rel_x = int(round(rel_x))
        #rel_y = int(round(rel_y))
        return self.canvas.create_text(rel_x, rel_y, **kwargs)

