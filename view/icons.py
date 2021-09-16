import PIL
import os

class Icons:
    def __init__(self):
        self.icons = {}
        self.init_icons()

    def init_icon(self, icon_name, filename, size=16):
        self.icons[icon_name] = {}
        self.icons[icon_name]["size"] = size
        self.icons[icon_name]["img"] = PIL.Image.open(f"./static/icons/{filename}")
        #self.icons[icon_name]["icon"] = self.icons[icon_name]['img']#PIL.ImageTk.PhotoImage(self.icons[icon_name]["img"].resize((size, size)))

    def get_icon(self, icon_name, size=16):
        if 'icon' not in self.icons[icon_name]:
            self.icons[icon_name]['icon'] = PIL.ImageTk.PhotoImage(self.icons[icon_name]['img'].resize((size, size)))
        return self.icons[icon_name]['icon'] 

    def init_icons(self):
        # for all png files in ./static/icons
        for filename in os.listdir("./static/icons/program_icons"):
            if filename.endswith(".png"):
                icon_name = os.path.splitext(filename)[0]
                self.init_icon(icon_name, 'program_icons/' + filename, 16)
        for filename in os.listdir("./static/icons/tag_icons"):
            if filename.endswith(".png"):
                icon_name = os.path.splitext(filename)[0]
                self.init_icon(icon_name, 'tag_icons/' + filename, 16)


# icons_class = Icons()
# icons = icons_class.icons