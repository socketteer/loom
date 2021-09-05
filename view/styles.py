from tkinter.font import Font
from view.colors import text_color, bg_color


def textbox_config(fg=text_color(), bg=bg_color(), font='Georgia', size=12):
    return {'font': Font(family=font, size=size),
            'spacing1': 10,  # spacing between paragraphs
            'foreground': fg,
            'background': bg,
            'padx': 2,
            'pady': 5,
            'spacing2': 8,  # Spacing between lines
            'spacing3': 5,
            'wrap': "word",
            'insertbackground': fg}
