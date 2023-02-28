import tkinter as tk
from tkinter import ttk

from loom.utils.util import recursive_map

##################################################################
# Labels
##################################################################


def create_label(frame, text, row=None, underline=False, size=12, col=0, columnspan=2, pady=3, padx=8, **kwargs):
    row = frame.grid_size()[1] if row is None else row
    label = ttk.Label(frame, text=text)
    label_font = tk.font.Font(label, label.cget("font"))
    label_font.configure(underline=underline, size=size)
    label.configure(font=label_font)
    label.grid(row=row, column=col, columnspan=columnspan, padx=padx, pady=pady, **kwargs)
    return label


# Creates a label on the first column of the frame
def create_side_label(frame, text, row=None, col=0):
    return create_label(frame, text, row, col=col, columnspan=1)


# Create a label which is updated with a variable
def create_variable_label(frame, variable, row=None):
    label = ttk.Label(frame, textvariable=variable)
    label.grid(row=row, columnspan=2, pady=5)
    return label


# Create a title on with the given text on the specified row
def create_title(frame, text, row=None):
    return create_label(frame, text, row, size=14, columnspan=10, pady=3)


# Creates a label centered on the row
def create_header(frame, text, row=None):
    return create_label(frame, text, row, size=12, columnspan=10, pady=4, sticky=tk.W)


# Creates a separator on the given row
def create_separator(frame, row=None):
    row = frame.grid_size()[1] if row is None else row
    sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
    sep.grid(row=row, columnspan=10, sticky="ew", pady=3)
    return sep


def create_gap(frame, row=None):
    row = frame.grid_size()[1] if row is None else row
    label = ttk.Label(frame, text=" ")
    label.grid(row=row, columnspan=2, pady=1)


##################################################################
# Control primitives
##################################################################


# Creates a menubar on the root given a menu dictionary with the follow format:
# i.e. a list of pairs containing menu headers and a list of (menuitem, command) pairs
# and '-' as a separator
# e.g. [ ('File', [('Item1', 'BindingText', 'Binding', Cmd1), '-',
#                  ('Item2', 'BindingText', 'Binding', Cmd2)] ),
#           ('Edit', [ .... ] ) ]
def create_menubar(root, menu_list, menu_bar=None):
    # Create a new menu bar and add it to root
    if menu_bar is None:
        menu_bar = tk.Menu(root)
        root.config(menu=menu_bar)
    # Create each sub menu and fill it with its items
    for menuTitle, menuItems in menu_list.items():
        # Add the menu to the menu bar
        menu = tk.Menu(menu_bar)
        menu_bar.add_cascade(label=menuTitle, menu=menu)
        for item in menuItems:
            if item == "-":
                menu.add_separator()
            else:
                # justification doesn't work with menus?
                label = item[0] + "     " + item[1] if item[1] is not None else item[0]
                menu.add_command(label=label, command=item[3])
                if item[2] is not None:
                    root.bind(item[2], item[3])
    return menu_bar


# Create a button on the specified row with the specified text and function call
def create_button(frame, text, function, width=10, row=None, column=None):
    row = frame.grid_size()[1] if row is None else row
    button = ttk.Button(frame, text=text, command=function, width=width)
    if column is None:
        colspan = 2
        column = 1
    else:
        colspan = 1
    button.grid(row=row, column=column, columnspan=colspan, pady=3)
    return button


def create_checkbutton(master, display_text, var_name, vars_dict):
    row = master.grid_size()[1]
    create_side_label(master, display_text, row)
    check = ttk.Checkbutton(master, variable=vars_dict[var_name])
    check.grid(row=row, column=1, pady=3)
    return check


# Create a combobox with a text label, specified values, and selected variable
def create_combo_box(frame, text, variable, values, row=None, width=10):
    row = frame.grid_size()[1] if row is None else row
    column = 0
    if text != "":
        label = create_side_label(frame, text, row)
        column += 1
    else:
        label = None
    combo = ttk.Combobox(frame, textvariable=variable, state="readonly", width=width, values=values)
    combo.grid(row=row, column=column, columnspan=10, pady=3, sticky=tk.W)
    return label, combo


# Create a combobox with a text label, specified values, and selected variable
def create_list_box(frame, values, label_text="", row=None, selectmode=tk.SINGLE, width=10, height=25):
    row = frame.grid_size()[1] if row is None else row
    column = 0
    if label_text != "":
        label = create_side_label(frame, label_text, row)
        column += 1
    else:
        label = None

    listbox = tk.Listbox(frame, selectmode=selectmode, width=width, height=height)
    for value in values:
        listbox.insert(tk.END, value)
    listbox.grid(row=row, column=column, columnspan=10, pady=3, sticky=tk.W)
    return label, listbox


# Create a slider with a text label, value pair defining its range, and selected variable
def create_slider(frame, text, variable, valuePair, row=None, resolution=None):
    row = frame.grid_size()[1] if row is None else row
    create_side_label(frame, text, row)
    s = ttk.Style()
    s.configure("TScale", foreground="white")
    slider = tk.Scale(
        frame,
        from_=valuePair[0],
        to=valuePair[1],
        variable=variable,
        orient=tk.HORIZONTAL,
        resolution=resolution if resolution is not None else -1,
    )
    slider.grid(row=row, column=1, pady=3)
    return slider


##################################################################
# Control components
##################################################################


# My code sucked. Lets try OOD...?
class ControlComponent:

    # Calls callback with single argument: value
    def __init__(self, frame, row, label_text, default, callback):
        self.frame = frame
        self.row = row
        self.label_text = label_text
        self.default = default
        self.callback = callback

        self.labels, self.controls, self.tk_variables = self.build()

    # Build labels, controls, variables
    def build(self):
        return ...

    # Refresh after a change
    def refresh(self):
        ...

    # Hide all labels and controls
    def grid_remove(self):
        recursive_map(lambda t: t.grid_remove(), (self.labels, self.controls))

    # Show all labels and controls
    def grid(self):
        recursive_map(lambda t: t.grid(), (self.labels, self.controls))


class Checkbox(ControlComponent):
    def __init__(self, frame, row, label_text, default, callback):
        super().__init__(frame, row, label_text, default, callback)

    def build(self):
        label = create_side_label(self.frame, self.label_text, self.row)

        variable = tk.BooleanVar()
        variable.set(self.default)
        variable.trace_add("write", lambda *_: self.callback(variable.get()))

        checkbox = tk.Checkbutton(self.frame, variable=variable)
        checkbox.grid(row=self.row, column=1, sticky=tk.W)
        return label, checkbox, variable


class Entry(ControlComponent):
    def __init__(self, frame, row, label_text, default, callback, width=10):
        self.width = width
        self.entry = None
        super().__init__(frame, row, label_text, default, callback)

    def build(self):
        label = create_side_label(self.frame, self.label_text, self.row)

        variable = tk.StringVar(value=self.default)
        if self.callback is not None:
            variable.trace_add("write", lambda *_: self.callback(variable.get()))

        control = ttk.Entry(self.frame, textvariable=variable, width=self.width)
        control.grid(row=self.row, column=1, columnspan=10, padx=1, sticky=tk.W)
        self.entry = control
        return label, control, variable

    def focus_entry(self):
        self.entry.focus()


class EnumDropdown(ControlComponent):
    def __init__(self, frame, row, label_text, default, callback):
        self.enum_type = default.__class__
        self.enum_values = [e.value for e in self.enum_type]
        super().__init__(frame, row, label_text, default, callback)

    def build(self):
        label = create_side_label(self.frame, self.label_text, self.row)

        variable = tk.StringVar(value=self.default.value)
        variable.trace_add("write", lambda *_: self.callback(self.enum_type(variable.get())))

        combo = ttk.Combobox(self.frame, textvariable=variable, values=self.enum_values, state="readonly", width=10)
        combo.grid(row=self.row, column=1, columnspan=5, sticky=tk.W)

        return label, combo, variable


class Slider(ControlComponent):
    def __init__(self, frame, row, label_text, default, callback):
        self.is_int = isinstance(default, int)
        if self.is_int:
            self.caster = lambda n: int(round(float(n)))
        else:  # Can't do ternary with lambdas...
            self.caster = float
        self.resolution = max(self.caster(default / 10), 1 if self.is_int else 0.1)
        super().__init__(frame, row, label_text, default, callback)

    def build(self):
        label = create_side_label(self.frame, self.label_text, self.row)

        # Vars
        self.lower_bound_var = tk.StringVar(value=self.caster(self.default - 10 * self.resolution))
        self.upper_bound_var = tk.StringVar(value=self.caster(self.default + 10 * self.resolution))
        self.slider_variable = tk.IntVar(value=self.default) if self.is_int else tk.DoubleVar(value=self.default)

        # Update
        self.lower_bound_var.trace_add("write", lambda *_: self.refresh())
        self.upper_bound_var.trace_add("write", lambda *_: self.refresh())
        self.slider_variable.trace_add("write", lambda *_: self.callback(self.caster(self.slider_variable.get())))

        # Controls
        lower = ttk.Entry(self.frame, textvariable=self.lower_bound_var, width=5)
        lower.grid(row=self.row, column=1, sticky=tk.SE)
        self.build_scale()
        upper = ttk.Entry(self.frame, textvariable=self.upper_bound_var, width=5)
        upper.grid(row=self.row, column=6, sticky=tk.SW)

        return (
            label,
            (lower, self.scale, upper),
            (self.lower_bound_var, self.upper_bound_var, self.slider_variable),
        )

    def build_scale(self):
        self.scale = tk.Scale(
            self.frame,
            from_=self.caster(self.lower_bound_var.get()),
            to=self.caster(self.upper_bound_var.get()),
            resolution=self.resolution,
            variable=self.slider_variable,
            orient=tk.HORIZONTAL,
        )
        self.scale.grid(row=self.row, column=2, columnspan=3)

    def refresh(self):
        self.scale.destroy()
        self.build_scale()


class ComplexSlider(ControlComponent):
    def __init__(self, frame, row, label_text, default, callback):
        super().__init__(frame, row, label_text, default, callback)

    def build(self):
        self.complex = complex(self.default)

        def set_real(real):
            self.complex = real + self.complex.imag
            self.update()

        def set_imag(imag):
            self.complex = self.complex.real + 1j * imag
            self.update()

        control_label = create_side_label(self.frame, str(self.label_text), self.row)
        self.complex_label = create_label(self.frame, str(self.complex), self.row, col=1, sticky=tk.W)

        self.real_slider = Slider(self.frame, self.row + 1, "Real", self.complex.real, callback=set_real)
        self.imag_slider = Slider(self.frame, self.row + 2, "Imaginary", self.complex.imag, callback=set_imag)

        return (control_label, self.complex_label), (self.real_slider, self.imag_slider), []

    def update(self):
        self.complex_label["text"] = str(self.complex)
        self.callback(self.complex)


def treeview_all_nodes(treeview: ttk.Treeview, parent=None):
    nodes = []
    for node in treeview.get_children(parent):
        nodes.append(node)
        nodes.extend(treeview_all_nodes(treeview, node))
    return nodes
