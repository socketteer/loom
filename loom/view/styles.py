from tkinter.font import Font

from loom.view.colors import bg_color, text_color


def textbox_config(fg=text_color(), bg=bg_color(), font="Georgia", size=12, spacing1=10, spacing2=8, pady=5):
    return {
        "font": Font(family=font, size=size),
        "spacing1": spacing1,  # spacing between paragraphs
        "foreground": fg,
        "background": bg,
        "padx": 2,
        "pady": pady,
        "spacing2": spacing2,  # Spacing between lines
        "spacing3": 5,
        "wrap": "word",
        "insertbackground": fg,
    }


def code_textbox_config(bg="black"):
    return {
        "font": Font(family="Monaco", size=12),
        "foreground": "white",
        "background": bg,
        "insertbackground": "white",
        "spacing1": 2,
        "spacing2": 2,
        "spacing3": 2,
    }
