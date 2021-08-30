import re

special_keybindings = {'!': 'exclam',
                       '@': 'at',
                       '#': 'numbersign',
                       '$': 'dollar',
                       '%': 'percent',
                       '^': 'asciicircum',
                       '&': 'ampersand',
                       '*': 'asterisk',
                       '(': 'parenleft',
                       ')': 'parenright'}

def tkinter_keybindings(key):
    if key.isalnum():
        return f"Key-{key.lower()}"
    elif key in special_keybindings:
        return special_keybindings[key]
    else:
        print('invalid key')
        return None

