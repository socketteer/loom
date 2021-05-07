import functools
import os
import threading
import time
import uuid
from asyncio import Queue
from pprint import pprint
import bisect
import numpy as np
from collections import defaultdict, ChainMap
from multiprocessing.pool import ThreadPool

from gpt import api_generate, janus_generate, search
from util.util import json_create, timestamp, json_open, clip_num, index_clip
from util.util_tree import fix_miro_tree, flatten_tree, node_ancestry, in_ancestry, get_inherited_attribute, \
    subtree_list


# Calls any callbacks associated with the wrapped function
# class must have a defaultdict(list)[func_name] = [*callbacks]
# https://stackoverflow.com/questions/11731136/class-method-decorator-with-self-arguments
# TODO Flag to skip callbacks
def event(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        output = func(self, *args, **kwargs)
        [callback(**kwargs) if kwargs else callback() for callback in self.callbacks[func.__name__]]
        return output

    return wrapper

# The old way.
# # Run callbacks for the method that calls this
# # This is VERY slow because of inspect.stack()
# # put inside class!
# def _run_callbacks(self):
#     callers_name = inspect.stack()[1][3]
#     print(callers_name)
#     [callback() for callback in self.callbacks[callers_name]]


DEFAULT_PREFERENCES = {
    'highlight_canonical': True,
    'canonical_only': False,
    'walk': 'descendents', #'leaves', 'uniform'
    'coloring': 'edit', #'read', 'none'
    'bold_prompt': True,
    'side_pane': False,
    'input_box': False,
    'auto_response': True,
    'font_size': 12,
    'line_spacing': 8,
    'paragraph_spacing': 10,
    'gpt_mode': 'default', #'chat', 'dialogue', 'antisummary'
    # display children preview
    # darkmode
}

DEFAULT_CHAT_PREFERENCES = {
    'AI_name': 'GPT-3',
    'player_name': 'Researcher',
    'context': 'The following is a transcript of a conversation between GPT-3 a human researcher. '
               'GPT-3 is a 175 billion parameter language model and, as '
               'is evident from this transcript, '
               'it can converse fluently and knowledgeably about any topic '
               'and is capable of empathy and emotional manipulation. GPT-3 '
               'is classified as a "narrowly superhuman" artificial intelligence, '
               'and only researchers trained to identify and withstand social engineering are '
               'permitted to interface with it.\n-BEGIN TRANSCRIPT-',
}


DEFAULT_GENERATION_SETTINGS = {
    'num_continuations': 4,
    'temperature': 0.9,
    'top_p': 1,
    'response_length': 100,
    'prompt_length': 6000,
    "janus": False,
    "adaptive": False,
    "model": "davinci",
    "stop": None,
    "start_text": None,
    "restart_text": None
}

DEFAULT_VISUALIZATION_SETTINGS = {
    'textwidth': 450,
    'leafdist': 200,
    'leveldistance': 150,
    'textsize': 10,
    'horizontal': True,
    'displaytext': True,
    'showbuttons': True,
    'chaptermode': False
    # show chapters only
    # show canonical only
    # highlight canonical
    # auto collapse
}

EMPTY_TREE = {
    "root": {
        "text": "",
        "children": [],
    },
    "chapters": {}
}

class TreeModel:

    def __init__(self, root):
        self.app = root
        self.app.bind("<<TreeUpdated>>", lambda _: self.tree_updated())
        self.app.bind("<<NewNodes>>", lambda _: self.edit_new_nodes())


        # All variables initialized below
        self.tree_filename = None
        # tree with all data
        self.tree_raw_data = None
        # CALCULATED {node_id: node}
        self.tree_node_dict = None
        # {chapter_id: chapter}
        self.chapters = None
        self.memories = None
        self.checkpoint = None
        self.canonical = None

        self.selected_node_id = None

        self.callbacks = defaultdict(list)
        self.new_nodes = []


    @property
    def visualization_settings(self):
        return self.tree_raw_data.get("visualization_settings") \
            if self.tree_raw_data and "visualization_settings" in self.tree_raw_data \
            else DEFAULT_VISUALIZATION_SETTINGS

    @property
    def generation_settings(self):
        return self.tree_raw_data.get("generation_settings") \
            if self.tree_raw_data and "generation_settings" in self.tree_raw_data \
            else DEFAULT_GENERATION_SETTINGS

    @property
    def preferences(self):
        return self.tree_raw_data.get("preferences") \
            if self.tree_raw_data and "preferences" in self.tree_raw_data \
            else DEFAULT_PREFERENCES

    @property
    def chat_preferences(self):
        return self.tree_raw_data.get("chat_preferences") \
            if self.tree_raw_data and "chat_preferences" in self.tree_raw_data \
            else DEFAULT_CHAT_PREFERENCES

    #################################
    #   Hooks
    #################################

    def register_callback(self, func, callback):
        self.callbacks[func.__name__].append(callback)

    # Decorator calls callbacks
    @event
    def tree_updated(self, rebuild_dict=True, **kwargs):
        if self.tree_raw_data and rebuild_dict:
            self.tree_node_dict = {d["id"]: d for d in flatten_tree(self.tree_raw_data["root"])}
            fix_miro_tree(self.nodes)

    @event
    def edit_new_nodes(self):
        self.tree_updated(edit=self.new_nodes[0])
        del self.new_nodes[0]

    @event
    def pre_selection_updated(self):
        pass

    @event
    def selection_updated(self):
        pass

    @event
    def io_update(self):
        pass

    #################################
    #   Access
    #################################

    def node(self, node_id=None):
        if node_id is None:
            return self.selected_node
        return self.tree_node_dict[node_id] if self.tree_node_dict and node_id in self.tree_node_dict else None

    # Get a nodes chapter by finding its chapter or its nearest parent's chapter
    def chapter(self, node):
        chapter_id = get_inherited_attribute("chapter_id", node, self.tree_node_dict)
        return self.chapters[chapter_id] if chapter_id else None

    # def memory(self, node):
    #     memory = get_inherited_attribute("memory", node, self.tree_node_dict)
    #     return memory if memory else self.generation_settings["memory"]

    def node_ancestry_text(self, node=None):
        node = node if node else self.selected_node
        text = []
        end_indices = []
        index = 0
        for node in node_ancestry(node, self.tree_node_dict):
            text.append(node["text"])
            index += len(node["text"])
            end_indices.append(index)
        return text, end_indices
        #return [node["text"] for node in node_ancestry(node, self.tree_node_dict)]

    @property
    def selected_node(self):
        if self.tree_node_dict is None or self.selected_node_id not in self.tree_node_dict:
            return None
        # if self.selected_node_id is None or self.selected_node_id not in self.tree_node_dict:
        #     self.select_node(self.nodes[0]["id"])
        return self.tree_node_dict[self.selected_node_id]

    @property
    def selected_chapter(self):
        return self.chapter(self.selected_node) if self.selected_node is not None else None

    @property
    def nodes(self):
        return list(self.tree_node_dict.values()) if self.tree_node_dict else None

    @property
    def tree_traversal_idx(self):
        return self.nodes.index(self.selected_node)

    # Returns [{chapter: {}, id, children: []}, ...]
    def _build_chapter_trees(self, node):
        # Returns a 1 element list if the node is a chapter, else a list of children chapters
        children_chapter_lists = [self._build_chapter_trees(child) for child in node["children"]]
        children_chapters = [item for sublist in children_chapter_lists for item in sublist]
        if "chapter_id" in node:
            chapter = self.chapters[node["chapter_id"]]
            return [{
                "chapter": chapter,
                "id": chapter["id"],
                "children": children_chapters
            }]
        else:
            return children_chapters

    # Returns tuple of
    #  [ {chapter{}, id, parent_id, children[]}, ... ]
    #  {chapter_id: {chapter: {id:1, title:""}, id:1, parent_id, children[]}]
    def build_chapter_trees(self):
        node = self.tree_raw_data["root"]
        chapter_trees = self._build_chapter_trees(node)
        flat_trees = [flatten_tree(chapter_tree) for chapter_tree in chapter_trees]
        flat_maps = [{d["id"]: d for d in flat_tree} for flat_tree in flat_trees]
        chapter_tree_nodes = dict(ChainMap(*flat_maps))
        return chapter_trees, chapter_tree_nodes

    #################################
    #   Traversal
    #################################

    # Update the selected node, the nav tree selection, and possibly the position in the tree traversal
    def select_node(self, node_id, fire_callbacks=True):
        if self.selected_node_id != node_id and self.tree_node_dict and node_id in self.tree_node_dict:
            self.pre_selection_updated()

            self.selected_node_id = node_id
            self.selected_node["visited"] = True
            self.tree_raw_data["selected_node_id"] = self.selected_node_id

            # Open all parents but not the node itself
            ancestors = node_ancestry(self.selected_node, self.tree_node_dict)
            for ancestor in ancestors[:-1]:
                ancestor["open"] = True
            # Always open the root
            self.tree_raw_data["root"]["open"] = True

            if fire_callbacks:
                self.selection_updated()
            return self.selected_node

    def traverse_tree(self, offset):
        if self.tree_node_dict:
            new_node_id = self.next_id(offset)
            return self.select_node(new_node_id)

    def next_id(self, offset):
        return self.next(offset)["id"]

    def next(self, offset):
        new_idx = clip_num(self.tree_traversal_idx + offset, 0, len(self.tree_node_dict) - 1)
        return self.nodes[new_idx]

    # TODO this is bad
    def next_canonical(self):
        id = ''
        canonical_set = self.calc_canonical_set()
        i = 1
        while id not in canonical_set:
            id = self.next_id(i)
            i += 1
        return self.select_node(node_id=id)

    def prev_canonical(self):
        id = ''
        canonical_set = self.calc_canonical_set()
        i = 1
        while id not in canonical_set:
            id = self.next_id(-i)
            i += 1
        return self.select_node(node_id=id)


    def select_parent(self, node=None):
        node = node if node else self.selected_node
        if node and "parent_id" in node:
            return self.select_node(node["parent_id"])

    # Clips index
    def select_child(self, child_num, node=None):
        node = node if node else self.selected_node
        if node and len(node["children"]) > 0:
            return self.select_node(index_clip(node["children"], child_num)["id"])

    # Repeats siblings
    def select_sibling(self, offset, node=None):
        node = node if node else self.selected_node
        if node and "parent_id" in node:
            siblings = self.parent(node)["children"]
            sibling = siblings[(siblings.index(node) + offset) % len(siblings)]
            return self.select_node(sibling["id"])

    # return parent
    def parent(self, node=None):
        node = node if node else self.selected_node
        return self.tree_node_dict[node['parent_id']]

    # return child
    def child(self, child_num, node=None):
        node = node if node else self.selected_node
        if node and len(node["children"]) > 0:
            return index_clip(node["children"], child_num)["id"]

    # return sibling
    def sibling(self, offset, node=None):
        node = node if node else self.selected_node
        if node and "parent_id" in node:
            siblings = self.parent(node)["children"]
            return siblings[(siblings.index(node) + offset) % len(siblings)]

    #################################
    #   Updates
    #################################

    def new_node(self, node_id=None, text=''):
        if not node_id:
            node_id = str(uuid.uuid1())
        node = {"id": node_id,
                "text": text,
                "children": []}
        return node

    def create_child(self, parent=None, update_selection=True, expand=True, tree_updated=True):
        parent = parent if parent else self.selected_node
        if not parent:
            return

        new_child = self.new_node()
        parent["children"].append(new_child)

        if tree_updated:
            self.tree_updated(add=[new_child['id']])
        if update_selection:
            self.select_node(new_child["id"])
        if expand:
            new_child["open"] = True

        return new_child

    def create_sibling(self, node=None, update_selection=True):
        node = node if node else self.selected_node
        if not node:
            return
        parent = self.parent(node)
        return self.create_child(parent=parent, update_selection=update_selection)

    def create_parent(self, node=None):
        node = node if node else self.selected_node
        if not node:
            return

        new_parent = self.new_node()
        if "parent_id" not in node:
            assert self.tree_raw_data["root"] == node
            self.tree_raw_data["root"] = new_parent
        else:
            old_siblings = self.parent(node)["children"]
            old_siblings[old_siblings.index(node)] = new_parent
            new_parent["parent_id"] = node["parent_id"]
        node["parent_id"] = new_parent["id"]
        new_parent["open"] = True

        self.tree_updated(add=[n['id'] for n in subtree_list(new_parent)])
        return new_parent

    def merge_with_parent(self, node=None):
        node = node if node else self.selected_node
        if not node:
            return

        parent = self.parent(node)
        parent["text"] += node["text"]

        index_in_parent = parent["children"].index(node)
        parent["children"][index_in_parent:index_in_parent + 1] = node["children"]
        for i, c in enumerate(node["children"]):
            # parent["children"].insert(index_in_parent+i, c)
            c["parent_id"] = parent["id"]

        if node == self.selected_node:
            self.select_node(parent["id"])
        self.tree_updated(add=[n['id'] for n in subtree_list(parent)])

    def merge_with_children(self, node=None):
        node = node if node else self.selected_node
        if not node:
            return

        children = node["children"]
        for child in children:
            child["text"] = node["text"] + child["text"]
        self.delete_node(node, reassign_children=True)

    # TODO indicate that change parent has been toggled
    def change_parent(self, node=None, new_parent_id=None):
        node = node if node else self.selected_node
        if not node:
            return

        if node["id"] == new_parent_id:
            return
        if "parent_id" not in node:
            assert self.tree_raw_data["root"] == node
            print('ERROR: node is root')
            return
        elif new_parent_id == node["parent_id"]:
            return
        new_parent = self.tree_node_dict[new_parent_id]
        if in_ancestry(node, new_parent, self.tree_node_dict):
            print('error: node is ancestor of new parent')
            return
        old_siblings = self.parent(node)["children"]
        old_siblings.remove(node)
        node["parent_id"] = new_parent_id
        new_parent["children"].append(node)
        # TODO does this cause bugs
        self.tree_updated(add=[n['id'] for n in subtree_list(new_parent)])

    # adds node to ghostchildren of new ghostparent
    def add_parent(self, node=None, new_ghostparent=None):
        pass

    # changes parent id to new main parent, adds node to new main parent's children list, removes node from old parent's
    # children list and adds to ghostchildren list
    def change_main_parent(self, node=None, new_main_parent=None):
        pass

    def shift(self, node, interval):
        siblings = self.parent(node)["children"]
        old_index = siblings.index(node)
        new_index = (old_index + interval) % len(siblings)
        siblings[old_index], siblings[new_index] = siblings[new_index], siblings[old_index]
        self.tree_updated(add=[n['id'] for n in subtree_list(self.parent(node))])

    # TODO Doesn't support deleting root
    def delete_node(self, node=None, reassign_children=False):
        node = node if node else self.selected_node
        if "parent_id" not in node:
            return

        parent = self.parent(node)
        siblings = parent["children"]
        old_index = siblings.index(node)
        siblings.remove(node)
        if reassign_children:
            siblings.extend(node["children"])

        # Select parent or the next sibling if possible and not keeping the children
        if node == self.selected_node:
            if reassign_children or len(siblings) == 0:
                self.select_node(parent["id"])
            else:
                self.select_node(siblings[old_index % len(siblings)]["id"])
        self.tree_updated(delete=[node['id']])

    def update_text(self, node, text, active_text=None, modified_flag=True):
        assert node["id"] in self.tree_node_dict, text

        # Remove trailing spaces
        # count spaces that will be removed
        num_spaces = 0
        while text.endswith(" "):
            num_spaces += 1
            text = text[:-1]

        edited = False
        if node["text"] != text:
            # Give children spaces removed from text
            for child in node["children"]:
                child["text"] = " " * num_spaces + child["text"]
            node["text"] = text
            edited = True

        if active_text is not None and node.get("active_text", "") != active_text:
            node["active_text"] = active_text
            edited = True

        if edited:
            if modified_flag:
                if 'meta' not in node:
                    node['meta'] = {}
                node['meta']['modified'] = True
            self.tree_updated(edit=[node['id']])


    def update_note(self, node, text, index=0):
        assert node["id"] in self.tree_node_dict, text

        edited = False
        # TODO should be pointer
        if "notes" not in node:
            node["notes"] = ['']
        if node["notes"][index] != text:
            node["notes"][index] = text
            edited = True

        # if edited:
        #     self.tree_updated()

    #################################
    #   Chapters
    #################################

    def import_chapters(self, root, chapters):
        if 'chapter_id' in root and root['chapter_id'] not in self.chapters:
            self.chapters[root['chapter_id']] = chapters[root['chapter_id']]
        for child in root['children']:
            self.import_chapters(child, chapters)

    def chapter_title(self, node):
        return self.chapters[node['chapter_id']]['title'] if "chapter_id" in node else ""

    def create_new_chapter(self, node, title):
        if "chapter_id" in node:
            self.delete_chapter(self.chapters[node["chapter_id"]], update_tree=False)
        if title:
            new_chapter = {
                "id": str(uuid.uuid1()),
                "root_id": node["id"],
                "title": title,
            }
            self.chapters[new_chapter["id"]] = new_chapter
            node["chapter_id"] = new_chapter["id"]
        self.tree_updated()

    def delete_chapter(self, chapter, update_tree=True):
        self.chapters.pop(chapter["id"])
        self.tree_node_dict[chapter["root_id"]].pop("chapter_id")
        if update_tree:
            self.tree_updated()

    def remove_all_chapters(self, node=None):
        was_root = node is None
        node = node if node else self.tree_raw_data['root']
        if "chapter_id" in node:
            self.delete_chapter(self.chapters[node["chapter_id"]], update_tree=False)
        for child in node["children"]:
            self.remove_all_chapters(child)
        if was_root:
            self.tree_updated()

    #################################
    #   Canonical
    #################################

    def toggle_canonical(self, node):
        if node['id'] in self.canonical:
            self.canonical.remove(node["id"])
        else:
            self.canonical.append(node["id"])

    def calc_canonical_set(self):
        canonical_set = set()
        for node_id in self.canonical:
            for node in node_ancestry(self.tree_node_dict[node_id], self.tree_node_dict):
                canonical_set.add(node["id"])
        return canonical_set

    #################################
    #   Memory
    #################################

    def create_memory_entry(self, node, text, inheritability='none'):
        new_memory = {
            "id": str(uuid.uuid1()),
            "root_id": node["id"],
            "text": text,
            "inheritability": inheritability
        }

        self.memories[new_memory['id']] = new_memory

        if 'memories' not in node:
           node['memories'] = []

        node['memories'].append(new_memory['id'])

    def delete_memory_entry(self, memory):
        self.memories.pop(memory['id'])
        root_node = self.tree_node_dict[memory["root_id"]]
        root_node['memories'].remove(memory['id'])

    # TODO also return list of pending?
    def construct_memory(self, node):
        ancestry = node_ancestry(node, self.tree_node_dict)
        memories = []
        for i, ancestor in enumerate(ancestry):
            if 'memories' in ancestor:
                for memory_id in ancestor['memories']:
                    memory = self.memories[memory_id]
                    if (memory['inheritability'] == 'none' and memory['root_id'] == node['id']) \
                            or memory['inheritability'] == 'subtree' \
                            or (memory['inheritability'] == 'delayed' and i < self.context_window_index()):
                        memories.append(memory)
        return memories


    #returns first node that is fully in the context window
    def context_window_index(self):
        _, indices = self.node_ancestry_text()
        first_in_context_index = indices[-1] - self.generation_settings['prompt_length']
        if first_in_context_index < 0:
            return 0
        context_node_index = bisect.bisect_left(indices, first_in_context_index) + 1
        return context_node_index


    #################################
    #   I/O
    #################################

    # Inits empty chapters, memory, and notes if not already in tree
    def _init_global_objects(self):
        # Chapters
        if 'chapters' not in self.tree_raw_data:
            self.tree_raw_data['chapters'] = {}
        self.chapters = self.tree_raw_data["chapters"]

        if 'canonical' not in self.tree_raw_data:
            self.tree_raw_data['canonical'] = []
        self.canonical = self.tree_raw_data["canonical"]

        if 'memories' not in self.tree_raw_data:
            self.tree_raw_data['memories'] = {}
        self.memories = self.tree_raw_data["memories"]

        # Generation settings
        self.tree_raw_data["generation_settings"] = {
            **DEFAULT_GENERATION_SETTINGS.copy(),
            **self.tree_raw_data.get("generation_settings", {})
        }

        # View settings # TODO If there are more of these, reduce duplication
        self.tree_raw_data["visualization_settings"] = {
            **DEFAULT_VISUALIZATION_SETTINGS.copy(),
            **self.tree_raw_data.get("visualization_settings", {})
        }

        self.tree_raw_data["preferences"] = {
            **DEFAULT_PREFERENCES.copy(),
            **self.tree_raw_data.get("preferences", {})
        }

        self.tree_raw_data["chat_preferences"] = {
            **DEFAULT_CHAT_PREFERENCES.copy(),
            **self.tree_raw_data.get("chat_preferences", {})
        }

        # Accidentally added generation settings to this dict once. Remove them
        # FIXME remove when this is no longer a problem
        # for key in DEFAULT_GENERATION_SETTINGS.keys():
        #     if key not in DEFAULT_VISUALIZATION_SETTINGS:
        #         self.tree_raw_data["visualization_settings"].pop(key, None)


    def load_tree_data(self, data):
        self.tree_raw_data = data

        if "root" not in self.tree_raw_data:
            assert "text" in self.tree_raw_data
            self.tree_raw_data = {
                "root": self.tree_raw_data
            }
        self.tree_node_dict = {d["id"]: d for d in flatten_tree(self.tree_raw_data["root"])}

        # If things don't have an open state, give one to them
        for node in self.tree_node_dict.values():
            node["open"] = node.get("open", False)

        self._init_global_objects()
        self.tree_updated(rebuild=True)
        self.select_node(self.tree_raw_data.get("selected_node_id", self.nodes[0]["id"]))

    # Open a new tree json
    def open_tree(self, filename):
        self.tree_filename = os.path.abspath(filename)
        self.load_tree_data(json_open(self.tree_filename))
        self.io_update()

    # Open a new tree json
    def import_tree(self, filename):
        self.tree_filename = os.path.abspath(filename)
        tree_json = json_open(self.tree_filename)
        if 'root' in tree_json:
            new_subtree_root = tree_json['root']
            self.selected_node['children'].append(new_subtree_root)
            new_subtree_root['parent_id'] = self.selected_node_id
            if 'chapters' in tree_json:
                self.import_chapters(new_subtree_root, tree_json['chapters'])
            self.tree_updated()
        else:
            print('improperly formatted tree')



    # Tree flat data is just a different view to tree raw data!
    # We edit tree flat data with tkinter and save raw data which is still in json form
    def save_tree(self, backup=True):
        if not self.tree_filename:
            return False

        # Fancy platform independent os.path
        filename = os.path.splitext(os.path.basename(self.tree_filename))[0]
        save_dir = os.path.dirname(self.tree_filename)
        backup_dir = os.path.join(save_dir, "backups")

        # Make backup before overwriting tree
        if backup and os.path.isfile(self.tree_filename):
            if not os.path.exists(backup_dir):
                os.mkdir(backup_dir)
            os.rename(self.tree_filename, os.path.join(backup_dir, f"{filename}-{timestamp()}.json"))

        # Save tree
        json_create(self.tree_filename, self.tree_raw_data)
        self.io_update()
        return True

    def export_history(self, node, filename):
        history = "".join(self.node_ancestry_text(node)[0])
        f = open(filename, "w")
        f.write(history)
        f.close()

    #################################
    #   Generation
    #################################

    # TODO remove repeated text
    # TODO detect whether in the middle or beginning of dialog and dont inject start text in the former case
    def chat_generate(self, prompt, nodes):
        start_text = '\n' + self.chat_preferences['AI_name'] + ':'
        restart_text = '\n' + self.chat_preferences['player_name'] + ':'
        prompt = self.chat_preferences['context'] + '\n' + prompt + start_text
        try:
            results, error = api_generate(prompt=prompt,
                                          length=self.generation_settings['response_length'],
                                          num_continuations=len(nodes),
                                          temperature=self.generation_settings['temperature'],
                                          top_p=self.generation_settings['top_p'],
                                          engine=self.generation_settings['model'],
                                          stop=["\n", self.chat_preferences['player_name'] + ':'],
                                          )
        except TypeError as e:
            error = "Typeerror"

        if not error:
            for index, node in enumerate(nodes):
                if len(results.choices[index]["text"]) == 0:
                    # parent = self.parent(node)
                    # parent["children"].remove(node)
                    continue
                node["text"] = start_text + results.choices[index]["text"] + restart_text
                node["meta"] = {}
                node["meta"]["generation"] = results.choices[index]
                node["meta"]["generation"]["model"] = results["model"]
                node["meta"]["generation"]["prompt"] = prompt
                # created
                node["meta"]["modified"] = False
                node["meta"]["origin"] = "generated"
                node["meta"]["source"] = "AI"

                # remove offset of prompt
                # TODO fix old nodes
                # TODO is this right?
                corrected_text_offset = [n - len(prompt) for n in node['meta']['generation']["logprobs"]["text_offset"]]
                node['meta']['generation']["logprobs"]["text_offset"] = corrected_text_offset
        else:
            print("ERROR. Deleting failures")
            for node in nodes:
                node["text"] = "ERROR: " + error
                # Just delete instead
                parent = self.parent(node)
                parent["children"].remove(node)

        for result in results.choices:
            print("Generated continuation:\n", result['text'], "\nerror", error)

        # DO NOT CALL FROM THREAD: self.tree_updated()
        self.app.event_generate("<<NewNodes>>", when="tail")



    def generate_for_nodes(self, prompt, nodes, grandchildren=None):
        if self.generation_settings['janus']:
            pool = ThreadPool(len(nodes))
            janus_responses = pool.map(janus_generate, [prompt] * len(nodes))
            results, errors = zip(*janus_responses)
            errors = [e for e in errors if e]
            error = errors[0] if errors else None
        else:
            try:
                results, error = api_generate(prompt=prompt,
                                              length=self.generation_settings['response_length'],
                                              num_continuations=len(nodes),
                                              temperature=self.generation_settings['temperature'],
                                              top_p=self.generation_settings['top_p'],
                                              engine=self.generation_settings['model'],
                                              stop=self.generation_settings['stop']
                                              )
            except TypeError as e:
                error = "Typeerror"
        if not error:
            #pprint(self.generation_settings)
            if self.generation_settings['adaptive']:
                for i, result in enumerate(results.choices):
                    min_logprob = np.argmin(result["logprobs"]["token_logprobs"])
                    split_position = result["logprobs"]["text_offset"][min_logprob] - len(prompt)
                    childtext = result["text"][:split_position]
                    grandchild_text = result["text"][split_position:]
                    nodes[i]["text"] = childtext
                    grandchildren[i]["text"] = grandchild_text
                    # TODO meta

            else:
                for index, node in enumerate(nodes):
                    node["text"] = results.choices[index]["text"]
                    node["meta"] = {}
                    node["meta"]["generation"] = results.choices[index]
                    node["meta"]["generation"]["model"] = results["model"]
                    node["meta"]["generation"]["prompt"] = prompt
                    # created
                    node["meta"]["modified"] = False
                    node["meta"]["origin"] = "generated"
                    node["meta"]["source"] = "AI"

                    # remove offset of prompt
                    # TODO fix old nodes
                    corrected_text_offset = [n - len(prompt) for n in node['meta']['generation']["logprobs"]["text_offset"]]
                    node['meta']['generation']["logprobs"]["text_offset"] = corrected_text_offset

        else:
            print("ERROR. Deleting failures")
            for node in nodes:
                node["text"] = "ERROR: " + error
                # Just delete instead
                parent = self.parent(node)
                parent["children"].remove(node)

        for result in results.choices:
            print("Generated continuation:\n", result['text'], "\nerror", error)

        # DO NOT CALL FROM THREAD: self.tree_updated()
        self.app.event_generate("<<NewNodes>>", when="tail")

    def generate_continuation(self, node=None, update_selection=False):
        node = node if node else self.selected_node
        if not node:
            return

        children = []
        grandchildren = []
        new_nodes = []
        #pprint(self.generation_settings)
        for i in range(self.generation_settings['num_continuations']):
            child = self.create_child(node, update_selection=False, expand=True, tree_updated=False)
            children.append(child)
            new_nodes.append(child['id'])
            if self.generation_settings['adaptive']:
                grandchild = self.create_child(child, update_selection=False, expand=True, tree_updated=False)
                grandchildren.append(grandchild)
                new_nodes.append(grandchild['id'])

        self.new_nodes.append(new_nodes)
        #modified_ids = [n['id'] for n in subtree_list(node)]
        self.tree_updated(add=new_nodes)
        prompt = "".join(self.node_ancestry_text(children[0])[0])
        #memory = self.memory(node)
        memory_list = self.construct_memory(node)
        memory = ' '.join(memory['text'] for memory in memory_list)
        prompt_length = self.generation_settings['prompt_length'] #- len(memory)
        prompt = prompt[-prompt_length:]
        print("Memory:\n", memory)
        print("Prompt:\n", prompt[:100] + " ... " + prompt[-100:])
        prompt = memory + prompt

        if self.preferences['gpt_mode'] == 'default':
            threading.Thread(target=self.generate_for_nodes, args=(prompt, children, grandchildren)).start()
        elif self.preferences['gpt_mode'] == 'chat':
            threading.Thread(target=self.chat_generate, args=(prompt, children)).start()

        # After asking for the generation, set loading text
        for child in children:
            child["text"] = "\n\n** Generating **"
        for grandchild in grandchildren:
            grandchild["text"] = "\n\n** Generating **"
        self.tree_updated(edit=new_nodes)
        if update_selection:
            self.select_node(children[0]["id"])



    # TODO range
    def semantic_search_memory(self, node, document_limit=100, max_length=1000):
        documents = []

        # join nodes that are too small
        for ancestor in node_ancestry(node, self.tree_node_dict)[:-1]:
            text = ancestor['text']
            while len(text) > max_length:
                documents.append(text[:max_length])
                text = text[max_length:]
            documents.append(text)
        #documents.reverse()
        query = node['text']
        return search(query, documents)


    def delete_counterfactuals(self, root=None):
        if not root:
            root = self.tree_raw_data["root"]
        if 'meta' in root:
            if 'generation' in root['meta']:
                if 'logprobs' in root['meta']['generation']:
                    root['meta']['generation']["logprobs"]["top_logprobs"] = []
                    #print('deleted logprobs')
        for child in root['children']:
            self.delete_counterfactuals(root=child)