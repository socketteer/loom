import tkinter
import tkinter.font as tkf
import json
import math

active_id = "3074457352469999697"
tree_params = {'rootx': 100,
               'rooty': 100,
               'width': 3500,
               'height': 1000,
               'levelheight': 20,
               'leafdist': 25,
               'textsize': 10,
               'textwidth': 100,
               'horizontal': True,
               'fixedwidth': False}

with open('data/adaptive_ada.json') as f:
    top_tree = json.load(f)
if "root" in top_tree:
    top_tree = top_tree["root"]


def clicked(canv, node_id):
    global active_id
    if not active_id == node_id:
        active_id = node_id
        redraw(canv)


# TODO in case of creating/deleting/expanding/collapsing subtrees, canvas size may change
def redraw(canv):
    canv.delete('data')
    drawtree(top_tree, canv, tree_params['rootx'], tree_params['rooty'], 0)


def draw():
    # init tk
    global tree_params
    root = tkinter.Tk()
    frame = tkinter.Frame(root, width=tree_params['width'], height=tree_params['height'])
    frame.pack(expand=True, fill=tkinter.BOTH)
    # create canvas
    canv = tkinter.Canvas(frame, bg='#FFFFFF', height=tree_params['width'], width=tree_params['height'])
    hbar = tkinter.Scrollbar(frame, orient=tkinter.HORIZONTAL)
    hbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
    hbar.config(command=canv.xview)
    vbar = tkinter.Scrollbar(frame, orient=tkinter.VERTICAL)
    vbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
    vbar.config(command=canv.yview)

    if not tree_params['displaytext']:
        tree_params['textwidth'] = 0

    drawtree(top_tree, canv, tree_params['rootx'], tree_params['rooty'], 0)

    # TODO for vertical, compensate for text heights too
    textheight = top_tree["offset"] * tree_params['leafdist'] if tree_params['horizontal'] \
        else top_tree["depth"] * tree_params['levelheight']
    width_offset = top_tree["depth"] * (tree_params['textwidth'] + tree_params['levelheight']) if tree_params[
        'horizontal'] \
        else top_tree["offset"] * (tree_params['leafdist'] + tree_params['textwidth'])

    canv.config(width=tree_params['width'], height=tree_params['height'],
                scrollregion=(0, 0, width_offset + tree_params['rootx'], textheight + tree_params['rooty']))
    canv.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
    canv.pack(side=tkinter.LEFT, expand=True, fill=tkinter.BOTH)
    root.mainloop()


#TODO centered tree
#TODO shrink width and extend line when text doesn't fill
def drawtree(tree, canv, nodex, nodey, parx=None, pary=None,
             level=0):
    tree['offset'], tree['depth'], tree['active'] = tree_shape(tree)
    if tree_params['displaytext']:
        # FIXME this is totally wrong; any way to get textheight?
        textheight = 0 if tree_params['horizontal'] else tree_params['textsize'] * 5 * len(tree['text']) / tree_params[
            'textwidth']
        textx = nodex + tree_params['textwidth'] / 2 if tree_params['horizontal'] else nodex
        texty = nodey if tree_params['horizontal'] else nodey + textheight / 2
        node_id = tree['id']
        text_color = "#00005f" if tree['active'] else "#000000"
        text_id = canv.create_text(textx, texty, fill=text_color, activefill='#999999',
                                   font=("Helvetica", tree_params['textsize']), width=tree_params['textwidth'],
                                   text=tree['text'],
                                   tags=[f'text-{node_id}', 'data'])
        canv.tag_bind(f'text-{node_id}', "<Button-1>", lambda event, canv=canv, node_id=node_id: clicked(canv, node_id))
    else:
        textheight = 0
    if level != 0:
        color = "#0000ff" if tree['active'] else "#000000"
        line_id = canv.create_line(parx, pary, nodex, nodey, fill=color, tags=['data'])
    child_offset = 0

    for child in tree['children']:
        childx = nodex + tree_params['levelheight'] + tree_params['textwidth'] if tree_params['horizontal'] \
            else nodex + child_offset * tree_params['leafdist']
        childy = nodey + child_offset * tree_params['leafdist'] if tree_params['horizontal'] \
            else nodey + tree_params['levelheight'] + textheight
        parentx = nodex + tree_params['textwidth'] if tree_params['horizontal'] else nodex
        parenty = nodey if tree_params['horizontal'] else nodey + textheight

        drawtree(child, canv, childx,
                 childy, parentx, parenty, level + 1)
        child_offset = child_offset + child['offset']


def tree_shape(tree):
    if 'id' not in tree:
        tree['id'] = None
    active = True if active_id == tree['id'] else False
    if "children" not in tree or len(tree['children']) == 0:
        tree["offset"] = 1
        tree["depth"] = 1
        return 1, 1, active
    offset = 0
    max_depth = 0
    for child in tree['children']:
        child_offset, child_depth, child_active = tree_shape(child)
        offset = offset + child_offset
        if child_depth > max_depth:
            max_depth = child_depth
        active = active or child_active
    tree['active'] = active
    return offset, max_depth + 1, active


draw()
