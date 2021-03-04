darkmode = True

GREEN = '#008c50'
PALE_GREEN = '#54997a'
PURPLE = '#a959e3'
BLUE = '#78b3ff'
PALE_BLUE = '#b7d2ed'
RED = '#dc3246'
YELLOW = '#e3e307'
LIGHT_YELLOW = '#e4e4d2'

MAGENTA = '#ff00d0'


DARKMODE_SCROLL_BG = "#545454"
LIGHTMODE_SCROLL_BG = '#e4e4e4'

DARKMODE_TEXTBOX_BG = "#474747" #"#383838"
DARKMODE_TEXT = "white"

DARKMODE_EDIT_BG = "#747474"

DARKMODE_NOT_VISITED = '#636363'
DARKMODE_VISITED = "#474747"

DARKMODE_HISTORY = "#cccccc"

DARKMODE_OOC = "#999999"

DARKMODE_DEFAULT = "#474747"


LIGHTMODE_TEXTBOX_BG = '#e4e4e4'
LIGHTMODE_TEXT = "black"

LIGHTMODE_EDIT_BG = "#cccccc"

LIGHTMODE_NOT_VISITED = PALE_BLUE
LIGHTMODE_VISITED = LIGHTMODE_TEXTBOX_BG

LIGHTMODE_HISTORY = '#404040'

LIGHTMODE_OOC = "#777777"

LIGHTMODE_DEFAULT = LIGHTMODE_TEXTBOX_BG


def default_color():
    return DARKMODE_DEFAULT if darkmode else LIGHTMODE_DEFAULT


def scroll_bg_color():
    return DARKMODE_SCROLL_BG if darkmode else LIGHTMODE_SCROLL_BG


def text_color():
    return DARKMODE_TEXT if darkmode else LIGHTMODE_TEXT


def bg_color():
    return DARKMODE_TEXTBOX_BG if darkmode else LIGHTMODE_TEXTBOX_BG


def edit_color():
    return DARKMODE_EDIT_BG if darkmode else LIGHTMODE_EDIT_BG


def history_color():
    return DARKMODE_HISTORY if darkmode else LIGHTMODE_HISTORY


def ooc_color():
    return DARKMODE_OOC if darkmode else LIGHTMODE_OOC

def not_visited_color():
    return DARKMODE_NOT_VISITED if darkmode else LIGHTMODE_NOT_VISITED


def visited_color():
    return DARKMODE_VISITED if darkmode else LIGHTMODE_VISITED




### VIS ###



DM_VIS_BG = '#505050'

DM_VISITED_NODE = '#404040'
DM_UNVISITED_NODE = '#555555'

DM_INACTIVE_LINE = '#787878'
DM_ACTIVE_LINE = 'white'
DM_SELECTED_LINE = BLUE
DM_EXPAND_BUTTON = GREEN

DM_INACTIVE_TEXT = '#bbbbbb'
DM_ACTIVE_TEXT = 'white'
DM_BUTTONS = '#666666'


LM_VIS_BG = "#cccccc"#'white' #LIGHT_YELLOW #'#e4e4e4'

LM_VISITED_NODE = '#dddddd'
LM_UNVISITED_NODE = '#bbbbbb'

LM_INACTIVE_LINE = '#bbbbbb'
LM_ACTIVE_LINE = BLUE
LM_SELECTED_LINE = BLUE
LM_EXPAND_BUTTON = PALE_GREEN

LM_INACTIVE_TEXT = 'black'
LM_ACTIVE_TEXT = 'black'
LM_BUTTONS = '#404040'


def vis_bg_color():
    return DM_VIS_BG if darkmode else LM_VIS_BG


def visited_node_bg_color():
    return DM_VISITED_NODE if darkmode else LM_VISITED_NODE


def unvisited_node_bg_color():
    return DM_UNVISITED_NODE if darkmode else LM_UNVISITED_NODE


def active_text_color():
    return DM_ACTIVE_TEXT if darkmode else LM_ACTIVE_TEXT


def selected_line_color():
    return DM_SELECTED_LINE if darkmode else LM_SELECTED_LINE


def active_line_color():
    return DM_ACTIVE_LINE if darkmode else LM_ACTIVE_LINE


def inactive_line_color():
    return DM_INACTIVE_LINE if darkmode else LM_INACTIVE_LINE


def inactive_text_color():
    return DM_INACTIVE_TEXT if darkmode else LM_INACTIVE_TEXT


def expand_button_color():
    return DM_EXPAND_BUTTON if darkmode else LM_EXPAND_BUTTON