import functools
import os
import threading
import time
import math
import uuid
from asyncio import Queue
from pprint import pprint
import bisect
import numpy as np
from collections import defaultdict, ChainMap
from multiprocessing.pool import ThreadPool
import codecs
import json
from util.frames_util import frame_merger, frame_merger_append, frame_merger_override
from copy import deepcopy
import jsonlines

from gpt import openAI_generate, search, gen
from util.util import json_create, timestamp, json_open, clip_num, index_clip, diff
from util.util_tree import fix_miro_tree, flatten_tree, node_ancestry, in_ancestry, get_inherited_attribute, \
    subtree_list, generate_conditional_tree, filtered_children, \
    new_node, add_immutable_root, make_simple_tree, fix_tree, ancestry_in_range, ancestry_plaintext, ancestor_text_indices, \
    node_index, ancestor_text_list, tree_subset
from util.gpt_util import conditional_logprob, tokenize_ada, prompt_probs, logprobs_to_probs, parse_logit_bias, parse_stop
from util.multiverse_util import greedy_word_multiverse
from util.node_conditions import conditions, condition_lambda

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


DEFAULT_PREFERENCES = {

    # Nav tree
    'reverse': False,

    # Navigation 
    'walk': 'descendents',  # 'leaves', 'uniform'
    'nav_tag': 'bookmark',

    # Story frame 
    'editable': True,
    'history_conflict': 'overwrite', # 'branch', 'ask', 'forbid'
    'coloring': 'edit',  # 'read', 'none'
    'bold_prompt': True,
    'font_size': 12,
    'line_spacing': 8,
    'paragraph_spacing': 10,

    # Saving
    'revision_history': False,
    'autosave': False,
    #'save_counterfactuals': False,
    'model_response': 'backup', #'discard', #'save'

    # generation data
    'prob': True,
    # darkmode
}

DEFAULT_WORKSPACE = {
    'side_pane': {'open': True, 
                  'modules': ["metaprocess"]},
    'bottom_pane': {'open': False, 
                    'modules': []},
    'buttons': ["Edit", "Delete", "Generate", "New Child", "Next", "Prev", "Visualize", "Wavefunction", "Map"],
    'alt_textbox': False,
    'show_search': False
}

DEFAULT_MODULE_SETTINGS = {
    'edit': {'node_id': None,},
    'input': {'auto_response': True, 'submit_template': "{input}"},
    'minimap': {'level_offset': 70,
                'leaf_offset': 40,
                'node_radius': 10,
                'line_thickness': 2,
                'horizontal': False,
                'prune_mode': 'open_in_nav', #'in_nav', 'ancestry_dist', 'wavefunction_collapse', 'selected_dist', 'all'
                'path_length_limit': 10,
                },
    'read children': {'filter': 'in_nav', #'all', 'uncleared', or name of tag TODO hide condition
                      'show_continue': 'no alternatives', #no choice, always, never, or name of tag
                      'show_options': 'always'}, #always, never, or name of tag 
    'children': {'toggle_tag': 'bookmark'}
}

DEFAULT_GENERATION_SETTINGS = {
    'num_continuations': 4,
    'temperature': 0.9,
    'top_p': 1,
    'response_length': 100,
    'prompt_length': 6000,
    'logprobs': 0,
    #"adaptive": False,
    "model": "davinci",
    "stop": '',  # separated by '|'
    "start": '',
    "restart": '',
    'preset': 'None',
    'global_context': '',
    'logit_bias': '',
    'template': 'Default',
}


DEFAULT_MODEL_CONFIG = {
    'models': {
        'ada': {
            'model': 'ada', 
            'type': 'openai', 
            'api_base': 'https://api.openai.com/v1'
            },
        'babbage': {
            'model': 'babbage',
            'type': 'openai',
            'api_base': 'https://api.openai.com/v1'
            },
        # 'content-filter-alpha-c4': {'type': 'openai'},
        # 'content-filter-dev': {'type': 'openai'},
        'curie': {
            'model': 'curie',
            'type': 'openai',
            'api_base': 'https://api.openai.com/v1'
            },
        # 'cursing-filter-v6': {'type': 'openai'},
        'davinci': {
            'model': 'davinci',
            'type': 'openai',
            'api_base': 'https://api.openai.com/v1'
            },
        'text-davinci-002': {
            'model': 'text-davinci-002',
            'type': 'openai',
            'api_base': 'https://api.openai.com/v1'
            },
        'text-davinci-003': {
            'model': 'text-davinci-003',
            'type': 'openai',
            'api_base': 'https://api.openai.com/v1'
            },
        # 'code-davinci-002': {
        #     'model': 'code-davinci-002',
        #     'type': 'openai',
        #     'api_base': 'https://api.openai.com/v1'
        #     },
        'instruct-curie-beta': {
            'model': 'instruct-curie-beta',
            'type': 'openai',
            'api_base': 'https://api.openai.com/v1'
            },
        'instruct-davinci-beta': {
            'model': 'instruct-davinci-beta',
            'type': 'openai',
            'api_base': 'https://api.openai.com/v1'
            },
        'gpt-3.5-turbo': {
            'model': 'gpt-3.5-turbo',
            'type': 'openai-chat',
            'api_base': 'https://api.openai.com/v1'
            },
        'gpt-4': {
            'model': 'gpt-4',
            'type': 'openai-chat',
            'api_base': 'https://api.openai.com/v1'
            },
        'j1-large': {
            'model': 'j1-large',
            'type': 'ai21',
            'api_base': None,
            },
        'j1-jumbo': {
            'model': 'j1-jumbo',
            'type': 'ai21',
            'api_base': None,
            },
        'gpt-neo-1-3b': {
            'model': 'gpt-neo-1.3B',
            'type': 'gooseai',
            'api_base': None,
            },
        'gpt-neo-2-7b': {
            'model': 'gpt-neo-2.7B',
            'type': 'gooseai',
            'api_base': None,
            },
        'gpt-j-6b': {
            'model': 'gpt-j-6B',
            'type': 'gooseai',
            'api_base': None,
            },
        'gpt-neo-20b': {
            'model': 'gpt-neo-20B',
            'type': 'gooseai',
            'api_base': None,
            },
    },
    # 'api_base': None,
    # 'api_key': os.environ.get("API_KEY", ''),
    # 'OPENAI_API_KEY': os.environ.get("OPENAI_API_KEY", None),
    # 'AI21_API_KEY': os.environ.get("AI21_API_KEY", None),
    # 'GOOSEAI_API_KEY': os.environ.get("GOOSEAI_API_KEY", None),
}

DEFAULT_INLINE_GENERATION_SETTINGS = {
    "model": "davinci",
    "num_continuations": 8,
    "temperature": 1,
    "top_p": 1,
    "response_length": 60,
    "prompt_length": 6000,
    "logprobs": 0,
    "stop": "\\n|.|?|!",
    "start": "",
    "restart": "",
    "preset": "Single Line",
    "global_context": "",
    "logit_bias": "",
    "template": "Default",
}


DEFAULT_VISUALIZATION_SETTINGS = {
    'text_width': 450,
    'leaf_distance': 200,
    'level_distance': 150,
    'text_size': 10,
    'horizontal': True,
    'display_text': True,
    'show_buttons': True,
    'chapter_mode': False
    # show chapters only
    # show canonical only
    # highlight canonical
    # auto collapse
}

DEFAULT_VARS = {}

# new tags should be added to the root level by default
DEFAULT_TAGS = { 
    "bookmark": { 
        "name": "bookmark", 
        "scope": "node",
        "hide": False,
        "show_only": False,
        "toggle_key": "b",
        "icon": "bookmark-black",
    },
    "canonical": { 
        "name": "canonical", 
        "scope": "ancestry",
        "hide": False,
        "show_only": False,
        "toggle_key": '*',
        "icon": "book-white",
    },
    "archived": { 
        "name": "archived", 
        "scope": "node",
        "hide": True,
        "show_only": False,
        "toggle_key": "!",
        "icon": "archive-yellow",
    },
    "note": { 
        "name": "note", 
        "scope": "node",
        "hide": True,
        "show_only": False,
        "toggle_key": "#",
        "icon": "note-black",
    },
    "pinned": { 
        "name": "pinned", 
        "scope": "node",
        "hide": False,
        "show_only": False,
        "toggle_key": "^",
        "icon": "pin-red",
    }
 }

EMPTY_TREE = {
    "root": {
        "mutable": False,
        "visited": True,
        "text": "",
        "children": [
            {
                "text": "",
                "children": [],
            }
        ],
    }
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
        #self.memories = None
        self.summaries = None
        self.checkpoint = None
        self.canonical = None
        #self.tags = None
        self.model_responses = None

        self.selected_node_id = None

        self.callbacks = defaultdict(list)
        self.conditions = defaultdict(list)
        self.new_nodes = []
        self.OPENAI_API_KEY = None
        self.AI21_API_KEY = None
        self.GOOSEAI_API_KEY = None

    @property
    def visualization_settings(self):
        return self.tree_raw_data.get("visualization_settings") \
            if self.tree_raw_data and "visualization_settings" in self.tree_raw_data \
            else DEFAULT_VISUALIZATION_SETTINGS

    @property
    def tags(self):
        return self.tree_raw_data.get("tags") \
            if self.tree_raw_data and "tags" in self.tree_raw_data \
            else DEFAULT_TAGS


    @property
    def model_config(self):
        return self.state["model_config"]

    @property
    def generation_settings(self):
        return self.state['generation_settings']

    @property
    def inline_generation_settings(self):
        return self.state['inline_generation_settings']

    @property
    def preferences(self):
        return self.state['preferences']

    @property
    def module_settings(self):
        return self.state['module_settings']

    @property
    def workspace(self):
        return self.state['workspace']

    @property
    def memories(self):
        return self.state['memories']

    @property
    def vars(self):
        return self.state['vars']
    
    # user frame

    @property
    def user_preferences(self):
        return self.user_frame.get("preferences") \
            if "preferences" in self.user_frame \
            else {}

    @property
    def user_generation_settings(self):
        return self.user_frame.get("generation_settings") \
            if "generation_settings" in self.user_frame \
            else {}

    @property
    def user_inline_generation_settings(self):
        return self.user_frame.get("inline_generation_settings") \
            if "inline_generation_settings" in self.user_frame \
            else {}

    @property
    def user_module_settings(self):
        return self.user_frame.get("module_settings") \
            if "module_settings" in self.user_frame \
            else {}

    @property
    def user_workspace(self):
        return self.user_frame.get("workspace") \
            if "workspace" in self.user_frame \
            else {}

    @property
    def user_frame(self):
        return self.tree_raw_data.get("frame") \
            if self.tree_raw_data and "frame" in self.tree_raw_data \
            else {}

    @property
    def state(self):
        state = {}
        state["memories"] = {}
        state["vars"] = deepcopy(DEFAULT_VARS)
        state["preferences"] = deepcopy(DEFAULT_PREFERENCES)
        state["generation_settings"] = deepcopy(DEFAULT_GENERATION_SETTINGS)
        state["inline_generation_settings"] = deepcopy(DEFAULT_INLINE_GENERATION_SETTINGS)
        state["workspace"] = deepcopy(DEFAULT_WORKSPACE)
        state["module_settings"] = deepcopy(DEFAULT_MODULE_SETTINGS) 
        state["model_config"] = deepcopy(DEFAULT_MODEL_CONFIG)
        frames = self.accumulate_frames(self.selected_node) if self.selected_node else {}
        frame_merger.merge(state, frames)
        frame_merger.merge(state, self.user_frame)
        return state


    def name(self):
        return os.path.splitext(os.path.basename(self.tree_filename))[0] if self.tree_filename else 'Untitled'

    #################################
    #   Frames
    #################################
    """
    Frames are updates to the state applied by nodes in the tree. 
    At any node in the multiverse, the state of the tree is the accumulation of all frames from its ancestry, 
    applied in chronological order (the future can override the past).
    A frame is a dictionary which is merged into the state of the tree using deepmerge.
    """

    def accumulate_frames(self, node):
        frames = []
        for ancestor in self.ancestry(node):
            if 'frame' in ancestor:
                frames.append(ancestor['frame'])
        frame_accumulator = {}
        for frame in frames:
            frame_merger.merge(frame_accumulator, deepcopy(frame))
        return frame_accumulator

    def set_frame(self, frame_parent, frame):
        frame_parent['frame'] = deepcopy(frame)

    # def overwrite_frame(self, frame, new_frame):
    #     frame = deepcopy(new_frame)

    def update(self, dict, update, append=False):
        if append:
                frame_merger_append.merge(dict, deepcopy(update))
        else:
            frame_merger.merge(dict, deepcopy(update))

    def set_path(self, dict, value, path):
        update_path = dict
        for key in path[:-1]:
            if key not in update_path:
                update_path[key] = {}
            update_path = update_path[key]
        update_path[path[-1]] = deepcopy(value)

    def get_path(self, dict, path):
        update_path = dict
        for key in path:
            if key not in update_path:
                return None
            update_path = update_path[key]
        return update_path

    def update_frame(self, node, update, append=False):
        if 'frame' in node:
            self.update(node['frame'], update, append)
        else:
            node['frame'] = deepcopy(update)
        self.tree_updated(write=False)

    def get_frame(self, node):
        return node.get('frame', {})

    def set_user_frame(self, state):
        self.tree_raw_data['frame'] = deepcopy(state)

    def update_user_frame(self, update, append=False):
        if 'frame' in self.tree_raw_data:
            self.update(self.tree_raw_data['frame'], update, append)
        else:
            self.tree_raw_data['frame'] = deepcopy(update)
        self.tree_updated(write=False)

    # TODO merge with frame
    def set_user_frame_partial(self, value, path):
        if 'frame' not in self.tree_raw_data:
            self.tree_raw_data['frame'] = {}
        self.set_path(self.tree_raw_data['frame'], value, path)
        
    def set_frame_partial(self, node, value, path):
        if 'frame' not in node:
            node['frame'] = {}
        self.set_path(node['frame'], value, path)

    def clear_user_frame(self):
        self.set_user_frame({})
        self.tree_updated(write=False)

    def write_user_frame_to_node(self):
        # saves current user settings as a frame at the selected node
        self.set_frame(self.selected_node, self.user_frame)
        self.clear_user_frame()

    #################################
    #   Hooks
    #################################

    def register_callback(self, func, callback):
        self.callbacks[func.__name__].append(callback)

    # Decorator calls callbacks
    @event
    def tree_updated(self, rebuild_dict=True, **kwargs):
        if self.tree_raw_data and rebuild_dict:
            self.rebuild_tree()

    # def tree_updated_silent(self):
    #     self.rebuild_tree()


    @event
    def rebuild_tree(self):
        add_immutable_root(self.tree_raw_data)
        self.tree_node_dict = {d["id"]: d for d in flatten_tree(self.tree_raw_data["root"])}
        fix_miro_tree(self.nodes)


    @event
    def edit_new_nodes(self):
        print('new nodes:', self.new_nodes)
        self.tree_updated()
        time.sleep(0.5)
        for node_id in self.new_nodes[0]:
            self.node(node_id)['mutable'] = True
        self.tree_updated(edit=self.new_nodes[0])
        del self.new_nodes[0]

    @event
    def pre_selection_updated(self, **kwargs):
        pass

    @event
    def selection_updated(self, **kwargs):
        pass

    @event
    def io_update(self):
        pass

    #################################
    #   Access
    #################################

    def root(self):
        return self.tree_raw_data['root']

    # return the node in tree_node_dict with id
    def node(self, node_id):
        # if type(node_id).__name__ != 'str':
        #     breakpoint()
        return self.tree_node_dict.get(node_id, None)

    # Get a nodes chapter by finding its chapter or its nearest parent's chapter
    def chapter(self, node):
        chapter_id = get_inherited_attribute("chapter_id", node, self.tree_node_dict)
        return self.chapters[chapter_id] if chapter_id else None

    @property
    def selected_node(self):
        if self.tree_node_dict is None or self.selected_node_id not in self.tree_node_dict:
            return None
        # if self.selected_node_id is None or self.selected_node_id not in self.tree_node_dict:
        #     self.select_node(self.nodes[0]["id"])
        return self.node(self.selected_node_id)

    @property
    def selected_chapter(self):
        return self.chapter(self.selected_node) if self.selected_node is not None else None

    @property
    def nodes(self):
        return list(self.tree_node_dict.values()) if self.tree_node_dict else None


    @property
    def tree_traversal_idx(self):
        return self.nodes.index(self.selected_node)


    def nodes_list(self, filter=None):
        #tree = tree if tree else self.tree_node_dict
        if not filter:
            return list(self.tree_node_dict.values())
        else:
            return [n for n in list(self.tree_node_dict.values()) if filter(n)]

    def nodes_dict(self, filter=None):
        nodes = self.nodes_list(filter)
        return {d['id']: d for d in nodes}

    def traversal_idx(self, node, filter=None):
        #tree = tree if tree else self.tree_node_dict
        nodes = self.nodes_list(filter) if filter else self.nodes
        return nodes.index(node)
        # for i, node in enumerate(nodes):
        #     if node['id'] == node_id:
        #         return i

    def filter_indices(self, nodes, filter=None):
        if filter:
            return {idx: d for idx, d in enumerate(nodes) if filter(d)}
        else:
            return {idx: d for idx, d in enumerate(nodes)}


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
    #   Ancestry
    #################################

    def ancestry(self, node, root=None):
        if not root:
            return node_ancestry(node, self.tree_node_dict)
        else: 
            return ancestry_in_range(root=root, node=node, node_dict=self.tree_node_dict)

    def ancestry_text(self, node, root=None):
        ancestry = self.ancestry(node, root)
        return ancestry_plaintext(ancestry, text_callback=self.text)

    def ancestor_text_list(self, node, root=None):
        ancestry = self.ancestry(node, root)
        return ancestor_text_list(ancestry, text_callback=self.text)

    def ancestor_text_indices(self, node, root=None):
        ancestry = self.ancestry(node, root)
        return ancestor_text_indices(ancestry, text_callback=self.text)

    def chain_uninterrupted(self, start, end):
        # returns true if chain of nodes has no other siblings
        chain = ancestry_in_range(start, end, self.tree_node_dict)
        for ancestor in chain[:-1]:
            if len(ancestor["children"]) > 1:
                return False
        return True


    #################################
    #   Subtree
    #################################

    def children_text_list(self, node, filter=None):
        return [self.text(child) for child in filtered_children(node, filter)]

    def children_text(self, node, delimiter='\n', filter=None):
        return delimiter.join(self.children_text_list(node, filter))


    #################################
    #   Traversal
    #################################

    # Update the selected node, the nav tree selection, and possibly the position in the tree traversal
    def select_node(self, node_id, fire_callbacks=True, reveal_node=False, **kwargs):
        if self.selected_node_id != node_id and self.tree_node_dict and node_id in self.tree_node_dict:
            self.pre_selection_updated(**kwargs)

            self.selected_node_id = node_id
            self.selected_node["visited"] = True
            self.tree_raw_data["selected_node_id"] = self.selected_node_id
            if reveal_node:
                self.reveal_nodes([self.selected_node])

            # Open all parents but not the node itself
            ancestors = node_ancestry(self.selected_node, self.tree_node_dict)
            for ancestor in ancestors[:-1]:
                ancestor["open"] = True
            # Always open the root
            self.tree_raw_data["root"]["open"] = True
            if fire_callbacks:
                self.selection_updated(**kwargs)
            return self.selected_node

    #TODO move out of model
    # def traverse_tree(self, offset=1, visible_only=True):
    #     if self.tree_node_dict:
    #         new_node_id = self.next_id(offset, visible_only)
    #         return self.select_node(new_node_id)

    # this only works if node is in filter
    def next_id(self, node, offset=1, filter=None):
        nodes = self.nodes_list(filter)
        traversal_idx = self.traversal_idx(node, filter)
        new_idx = clip_num(traversal_idx + offset, 0, len(nodes) - 1)
        return nodes[new_idx]["id"]

    # return id of next node which satisfies filter condition
    def find_next(self, node, filter=None, visible_filter=None):
        nodes = self.nodes_list(visible_filter) if visible_filter else self.nodes
        current_idx = self.traversal_idx(node, visible_filter)
        true_indices = self.filter_indices(nodes, filter)
        if len(true_indices) < 1:
            return
        try:
            go_to_true = next(i for i, idx in enumerate(true_indices.keys()) if idx > current_idx)
        except StopIteration:
            go_to_true = 0
        return list(true_indices.values())[go_to_true]["id"]

    def find_prev(self, node, filter=None, visible_filter=None):
        nodes = self.nodes_list(visible_filter) if visible_filter else self.nodes
        current_idx = self.traversal_idx(node, visible_filter)
        true_indices = self.filter_indices(nodes, filter)
        if len(true_indices) < 1:
            return
        earlier_true = list(i for i, idx in enumerate(true_indices.keys()) if idx < current_idx)
        go_to_true = earlier_true[-1] if len(earlier_true) > 0 else -1
        return list(true_indices.values())[go_to_true]["id"]

    def parent(self, node):
        return self.node(node['parent_id']) if 'parent_id' in node else None

    # return child
    def child(self, node, child_num, filter=None):
        children = filtered_children(node, filter)
        if len(children) > 0:
            return index_clip(children, child_num)
        else:
            return None

    # return next sibling
    def sibling(self, node, offset=1, filter=None, wrap=True):
        siblings = self.siblings(node, filter)
        if node not in siblings:
            new_idx = 0
        else:
            new_idx = (siblings.index(node) + offset) % len(siblings)
        if not wrap and new_idx == 0:
            return self.parent(node)
        return siblings[new_idx]

    def siblings(self, node, filter=None):
        if not self.has_parent(node):
            return None
        parent = self.parent(node)
        return filtered_children(parent, filter)

    def siblings_index(self, node, filter=None):
        if not self.has_parent(node):
            return 0
        parent = self.parent(node)
        siblings = filtered_children(parent, filter)
        if node in siblings:
            return siblings.index(node)
        else:
            return len(siblings)


    #################################
    #   Conditionals
    #################################

    def has_parent(self, node):
        return 'parent_id' in node and node['parent_id']

    def is_compound(self, node):
        return 'masked_head' in node

    def is_hoisted(self, node):
        return node.get('hoisted', False)

    def is_mutable(self, node):
        return node.get('mutable', True)

    def is_root(self, node):
        return node == self.root()

    def visible(self, node):
        return self.visible_conditions()(node) or self.is_root(node) #or self.is_compound(node)

    def id_visible(self, node_id):
        return self.visible(self.node(node_id))

    def is_AI_generated(self, node):
        if 'meta' in node:
            if 'source' in node['meta']:
                return node["meta"]["source"] == "AI"
        return False

    def is_template(self, node):
        return node.get('template', False)

    def construct_node_condition(self, info_dict):
        name = info_dict['name']
        params = info_dict.get('params', {})
        params['tree_node_dict'] = self.tree_node_dict
        return lambda node: conditions[name](node=node, **params)

    def generate_filtered_tree(self, root=None):
        root = root if root else self.tree_raw_data["root"]
        condition = self.visible_conditions()
        if not condition:
            return self.tree_node_dict
        else:
            return generate_conditional_tree(root, condition)

    def visible_conditions(self):
        and_conditions = []
        or_conditions = []
        for tag, attributes in self.tags.items():
            if attributes['hide']:
                and_conditions.append(lambda node, _tag=tag: not self.has_tag(node, _tag))
            if attributes['show_only']:
                or_conditions.append(lambda node, _tag=tag: self.has_tag(node, _tag))
        return lambda node: condition_lambda(node, and_conditions, or_conditions)



    #################################
    #   Updates
    #################################

    def node_creation_metadata(self, node, source='prompt'):
        if 'meta' not in node:
            node["meta"] = {}
        node["meta"]["creation_timestamp"] = timestamp()
        node["meta"]["source"] = source
        # TODO replace with history
        node["meta"]["modified"] = False

    def create_child(self, parent, expand=True, text=''):
        if not parent:
            return
        new_child = new_node(text=text)
        parent["children"].append(new_child)
        if expand:
            new_child["open"] = True

        self.rebuild_tree()
        return new_child

        # if refresh_nav:
        #     self.tree_updated(add=[new_child['id']])
        # else:
        #     self.rebuild_tree()
        # if update_selection:
        #     self.select_node(new_child["id"])

    def create_sibling(self, node):
        if not node:
            return
        parent = self.parent(node)
        return self.create_child(parent=parent)

    def create_parent(self, node):
        if not node:
            return
        new_parent = {
            "id": str(uuid.uuid1()),
            "text": "",
            "children": [node]
        }
        if "parent_id" not in node:
            assert self.tree_raw_data["root"] == node
            self.tree_raw_data["root"] = new_parent
        else:
            old_siblings = self.parent(node)["children"]
            old_siblings[old_siblings.index(node)] = new_parent
            new_parent["parent_id"] = node["parent_id"]

        node["parent_id"] = new_parent["id"]
        new_parent["open"] = True

        self.rebuild_tree()
        return new_parent

    def merge_with_parent(self, node):
        if not node:
            return

        assert 'parent_id' in node, self.is_mutable(node)
        parent = self.parent(node)
        assert self.is_mutable(parent)

        parent["text"] += node["text"]

        index_in_parent = parent["children"].index(node)
        parent["children"][index_in_parent:index_in_parent + 1] = node["children"]
        for i, c in enumerate(node["children"]):
            # parent["children"].insert(index_in_parent+i, c)
            c["parent_id"] = parent["id"]
        
        self.rebuild_tree()

        # if node == self.selected_node:
        #     self.select_node(parent["id"])
        # if refresh_nav:
        #     self.tree_updated(add=[n['id'] for n in subtree_list(parent)])
        # else:
        #     self.rebuild_tree()

    def merge_with_children(self, node=None):
        node = node if node else self.selected_node
        assert self.is_mutable(node)
        if not node:
            return

        children = node["children"]
        for child in children:
            child["text"] = node["text"] + child["text"]
        self.delete_node(node, reassign_children=True)

    # TODO indicate that change parent has been toggled
    def change_parent(self, node, new_parent_id=None):
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
        new_parent = self.node(new_parent_id)
        if in_ancestry(node, new_parent, self.tree_node_dict):
            print('error: node is ancestor of new parent')
            return
        old_siblings = self.parent(node)["children"]
        old_siblings.remove(node)
        node["parent_id"] = new_parent_id
        new_parent["children"].append(node)
        # TODO does this cause bugs
        self.rebuild_tree()

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
        self.rebuild_tree()
        # if refresh_nav:
        #     self.tree_updated(add=[n['id'] for n in subtree_list(self.parent(node))])
        # else:
        #     self.rebuild_tree()

    # TODO Doesn't support deleting root
    def delete_node(self, node=None, reassign_children=False):
        node = node if node else self.selected_node
        if "parent_id" not in node:
            return

        parent = self.parent(node)
        siblings = parent["children"]
        #next_sibling = self.next_sibling(node)
        siblings.remove(node)
        if reassign_children:
            siblings.extend(node["children"])

        self.rebuild_tree()



    # TODO add creation date if it doesn't exist
    def update_text(self, node, text, modified_flag=True, save_revision_history=False, refresh_nav=True):
        if not node["id"] in self.tree_node_dict or not text:
            return
        if not self.is_mutable(node):
            return

        # Remove trailing spaces
        # count spaces that will be removed
        # num_spaces = 0
        # while text.endswith(" "):
        #     num_spaces += 1
        #     text = text[:-1]

        old_text = node["text"]
        if old_text != text:
            # Give children spaces removed from text
            # for child in node["children"]:
            #     child["text"] = " " * num_spaces + child["text"]
            node["text"] = text

            if 'meta' not in node:
                node['meta'] = {}
            if modified_flag:
                node['meta']['modified'] = True
            if 'source' not in node['meta']:
                node['meta']['source'] = 'prompt'
            elif node['meta']['source'] == 'AI':
                node['meta']['source'] = 'mixed'

            if save_revision_history:
                if 'history' not in node:
                    node['history'] = []
                node['history'].append({
                    'timestamp': timestamp(),
                    'text': old_text,
                })
                
            if refresh_nav:
                self.tree_updated(edit=[node['id']])
            else:
                self.rebuild_tree()
                #pass


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

    # TODO update, make attribute-agnostic
    def split_node(self, node, split_index):
        new_parent = self.create_parent(node)
        parent_text = node['text'][:split_index]
        child_text = node['text'][split_index:]

        if parent_text[-1] == ' ':
            child_text = ' ' + child_text
            parent_text = parent_text[:-1]

        new_parent["text"] = parent_text
        node["text"] = child_text

        new_parent["meta"] = {}
        new_parent['meta']['origin'] = f'split (from child {node["id"]})'
        if 'summaries' in node:
            new_parent['summaries'] = node['summaries']
            for summary_id in new_parent['summaries']:
                summary = self.summaries[summary_id]
                summary['root_id'] = new_parent['id']
            node['summaries'] = []
        if 'meta' in node and 'source' in node['meta']:
            new_parent['meta']['source'] = node['meta']['source']

        # both nodes inherit tags
        if 'tags' in node:
            new_parent['tags'] = node['tags']

        new_parent['visited'] = True

        # move chapter head to new parent
        if 'chapter_id' in node:
            new_parent['chapter_id'] = node['chapter_id']
            node.pop('chapter_id')
        self.rebuild_tree()
        # if refresh_nav:
        #     self.tree_updated(add=[n['id'] for n in subtree_list(new_parent)])
        # else:
        #     self.rebuild_tree()
        return new_parent, node

    def sever_from_parent(self, node):
        parent = self.parent(node)
        parent['children'].remove(node)
        node['parent_id'] = None
        return parent

    def sever_children(self, node):
        children = node['children'].copy()
        for child in children:
            child['parent_id'] = None
        node['children'] = []
        # TODO empty?
        return children

    def adopt_parent(self, node, parent):
        node['parent_id'] = parent['id']
        parent['children'].append(node)

    def adopt_children(self, node, children):
        for child in children:
            self.adopt_parent(child, parent=node)

    def zip(self, head, tail, refresh_nav=True, update_selection=True):
        text = self.ancestry_text(node=tail, root=head) #ancestry_plaintext(ancestry_in_range(root=head, node=tail))
        mask = new_node(text=text, mutable=False)
        if self.has_parent(head):
            parent = self.sever_from_parent(head)
            self.adopt_parent(mask, parent)
        children = self.sever_children(tail)
        self.adopt_children(mask, children)
        mask['masked_head'] = head
        mask['tail_id'] = tail['id']
        # TODO hacky
        nav_preview_text = head['text'].strip()[:15].replace('\n', '\\n') \
                                   + '...' + tail['text'].strip()[:12].replace('\n', '\\n')
        self.add_text_attribute(mask, "nav_preview", nav_preview_text)
        mask['visited'] = True

        if refresh_nav:
            self.tree_updated(delete=[head['id']], add=[n['id'] for n in subtree_list(mask)], write=False)
        else:
            self.rebuild_tree()
        if update_selection:
            self.select_node(mask['id'], write=False)
            self.selection_updated(write=False)
        return mask

    def unzip(self, mask, filter=None, refresh_nav=True, update_selection=True):
        if not self.is_compound(mask):
            print('nothing to expand')
            return
        # if self.is_hoisted(mask):
        #     return self.unhoist(rebuild=refresh_nav, update_selection=update_selection)
        head = mask['masked_head']
        head_dict = {d["id"]: d for d in flatten_tree(head)}
        tail = head_dict[mask['tail_id']]
        if self.has_parent(mask):
            parent = self.sever_from_parent(mask)
            self.adopt_parent(head, parent)
        children = self.sever_children(mask)
        self.adopt_children(tail, children)

        if refresh_nav:
            self.tree_updated(delete=[mask['id']], add=[n['id'] for n in subtree_list(head, filter)], write=False)
        else:
            self.rebuild_tree()
        if update_selection:
            self.select_node(head['id'])
            self.selection_updated()
        return head

    def zip_chain(self, node, filter=None, mode='bidirectional', refresh_nav=False, update_selection=False):
        head = node
        tail = node
        if mode in ('bidirectional', 'backward'):
            while self.has_parent(head) and len(filtered_children(self.parent(head), filter)) == 1:
                head = self.parent(head)
        if mode in ('bidirectional', 'forward'):
            while len(filtered_children(tail, filter)) == 1:
                tail = filtered_children(tail, filter)[0]
        if not (head == node and tail == node):
            zipped = self.zip(head=head, tail=tail, refresh_nav=refresh_nav, update_selection=update_selection)
            zipped['tags'] = self.get_constituents_attribute(zipped, "tags")
            zipped['memories'] = self.get_constituents_attribute(zipped, "memories")
            return zipped
        else:
            return node

    def zip_all_chains(self, root=None, filter=None):
        root = root if root else self.root()
        # TODO root problem
        if not self.is_root(root):
            new_node = self.zip_chain(root, filter=filter, mode='forward')
        else:
            new_node = root
        children = filtered_children(new_node, filter)
        for child in children:
            self.zip_all_chains(child, filter)

    def unzip_all(self, root=None, filter=None):
        root = root if root else self.root()
        children = root['children']
        for child in children:
            self.unzip_all(child, filter)
        # TODO this interferes with hoist?
        if self.is_compound(root) and not self.is_hoisted(root):
            head = self.unzip(root, filter=filter, refresh_nav=False, update_selection=False)

    # returns list of masked nodes from head to tail
    def constituents(self, mask):
        if not self.is_compound(mask):
            print('not compound node')
            return
        head = mask['masked_head']
        head_dict = {d["id"]: d for d in flatten_tree(head)}
        tail = head_dict[mask['tail_id']]
        return node_ancestry(tail, head_dict)

    def get_constituents_attribute(self, mask, attribute):
        attributes = []
        for node in self.constituents(mask):
            attributes.extend(node.get(attribute, []))
        attributes = list(set(attributes))
        return attributes

    def tag_constituents(self, mask):
        pass

    def reveal_ancestry(self, node):
        ancestry = self.ancestry(node)
        hidden_ancestry_ids = []
        for i in range(1, len(ancestry)):
            if not self.visible(ancestry[-i]):
                hidden_ancestry_ids.insert(0, ancestry[-i]['id'])
            else:
                break
        self.tree_updated(add=hidden_ancestry_ids, override_visible=True, write=False)

    # unlike reveal_ancestry, this assumes parents are visible
    def reveal_nodes(self, nodes):
        invisible_node_ids = [node['id'] for node in nodes if not self.visible(node)]
        if invisible_node_ids:
            self.tree_updated(add=invisible_node_ids, override_visible=True, write=False)


    #################################
    #   Text
    #################################

    def text(self, node, raw=False):
        if not node:
            return ''
        if self.is_template(node) and not raw:
            try:
                return eval(f'f"""{node["text"]}"""')
            except Exception as e:
                print(e)
                return node['text']
        else:
            return node['text']

    def set_template(self, node, value):
        node['template'] = value
        self.tree_updated()

    def display_to_raw_index(self, node, index):
        # if the node text is an fstring template, convert index of evaluated text to 
        # index of raw template
        if self.is_template(node):
            # TODO
            return index
        else:
            return index

    #################################
    #   Chapters
    #################################

    # def import_chapters(self, root, chapters):
    #     if 'chapter_id' in root and root['chapter_id'] not in self.chapters:
    #         self.chapters[root['chapter_id']] = chapters[root['chapter_id']]
    #     for child in root['children']:
    #         self.import_chapters(child, chapters)

    def chapter_title(self, node):
        # print(self.chapters)
        # print(self.chapters)
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
        self.node(chapter["root_id"]).pop("chapter_id")
        if update_tree:
            self.tree_updated()

    def remove_all_chapters(self, node=None):
        was_root = node is None
        node = node if node else self.root()
        if "chapter_id" in node:
            self.delete_chapter(self.chapters[node["chapter_id"]], update_tree=False)
        for child in node["children"]:
            self.remove_all_chapters(child)
        if was_root:
            self.tree_updated()


    #################################
    #   Vars
    #################################

    # TODO globals

    def create_var(self, node, name, value=''):
        if name not in self.vars:
            self.update_var(node, name, value)
        else:
            pass

    def delete_var(self, node, name):
        # what should this do?
        # 1. delete from all frames
        # 2. mask in current frame
        pass

    def update_var(self, node, name, value):
        self.update_frame(node=node, update={'vars': {name: value}})


    #################################
    #   Memory, summaries
    #################################

    def create_memory(self, node, text, inheritability='none'):
        memory_id = str(uuid.uuid1())
        new_memory = {
            "id": memory_id,
            "root_id": node["id"],
            "text": text,
            "inheritability": inheritability,
            "enabled": True,
        }
        # TODO if inheritability global, add to root frame instead
        self.update_frame(node, update={'memories': {memory_id: new_memory}})
        self.tree_updated()

    def update_memory(self, memory_id, update):
        try:
            memory = self.state['memories'][memory_id]
            self.update_frame(node=self.node(memory["root_id"]), update={'memories': {memory_id: update}})
        except KeyError:
            pass

    def delete_memory(self, memory_id):
        pass
        # self.memories.pop(memory['id'])
        # root_node = self.node(memory["root_id"])
        # root_node['memories'].remove(memory['id'])

    def memory_active(self, node, memory):
        memory_ancestor = self.node(memory['root_id'])
        # if not in_ancestry(memory_ancestor, node, self.tree_node_dict):
        #     return False
        return memory['inheritability'] == 'none' and memory['root_id'] == node['id'] \
               or memory['inheritability'] == 'subtree' or memory['inheritability'] == 'global' \
               or (memory['inheritability'] == 'delayed'
                   and node_index(memory_ancestor, self.tree_node_dict) < self.context_window_index(node))

    # TODO also return list of pending?
    # def construct_memory(self, node):
    #     ancestry = self.ancestry(node)
    #     memories = []
    #     for ancestor in ancestry:
    #         if 'memories' in ancestor:
    #             for memory_id in ancestor['memories']:
    #                 memory = self.memories[memory_id]
    #                 if self.memory_active(node, memory):
    #                     memories.append(memory)
    #     return memories

    def create_summary(self, root_node, end_node, summary_text):
        new_summary = {
            "id": str(uuid.uuid1()),
            "root_id": root_node["id"],
            "end_id": end_node["id"],
            "text": summary_text,
        }

        self.summaries[new_summary['id']] = new_summary

        if 'summaries' not in root_node:
            root_node['summaries'] = []

        root_node['summaries'].append(new_summary['id'])

    def delete_summary(self, summary):
        self.summaries.pop(summary['id'])
        root_node = self.node(summary["root_id"])
        root_node['summmaries'].remove(summary['id'])

    def past_summaries(self, node=None):
        node = node if node else self.selected_node
        ancestry = self.ancestry(node)
        ancestry_ids = [ancestor['id'] for ancestor in ancestry]
        summaries = []
        for i, ancestor in enumerate(ancestry):
            if 'summaries' in ancestor:
                for summary_id in ancestor['summaries']:
                    summary = self.summaries[summary_id]
                    if summary['end_id'] in ancestry_ids:
                        summaries.append(summary)
        return summaries

    # returns first node that is fully contained in the context window
    def context_window_index(self, node):
        indices = self.ancestor_text_indices(node)
        end_indices = [ind[1] for ind in indices]
        first_in_context_index = end_indices[-1] - self.generation_settings['prompt_length']
        if first_in_context_index < 0:
            return 0
        context_node_index = bisect.bisect_left(end_indices, first_in_context_index) + 1
        return context_node_index

    #################################
    #   Tags
    #################################

    def get_node_tags(self, node):
        tags = ["visited"] if node.get("visited", False) else ["not visited"]
        if not self.is_mutable(node):
            tags.append("immutable")
        if self.has_tag(node, "canonical"):
            tags.append("canonical")
        else:
            tags.append("uncanonical")
        return tags

    def add_tag(self, name, scope='node', hide=False, show_only=False, toggle_key='None', icon='None'):
        self.tags[name] = {'name': name,
                           'scope': scope,
                           'hide': hide,
                           'show_only': show_only,
                           'toggle_key': toggle_key,
                           'icon': icon}

    def delete_tag(self, name):
        del self.tags[name]
        # TODO delete tag from all nodes

    def tag_node(self, node, tag):
        if tag not in self.tags:
            print('no such tag')
            return
        if 'tags' not in node:
            node['tags'] = []
        if tag not in node['tags']:
            node['tags'].append(tag)

    def untag_node(self, node, tag):
        if 'tags' in node and tag in node['tags']:
            node['tags'].remove(tag)

    def toggle_tag(self, node, tag):
        if self.has_tag_attribute(node, tag):
            self.untag_node(node, tag)
        else:
            self.tag_node(node, tag)

    def tagged_nodes(self, tag, filter=None):
        if tag not in self.tags:
            print('no such tag')
            return
        # for tags with "node" scope, return all nodes with that tag
        nodes = self.nodes_list(filter)
        tagged_nodes = [d for d in nodes if self.has_tag_attribute(d, tag)]
        if self.tags[tag]['scope'] == 'node':
            return tagged_nodes

        # for tags with "subtree" scope, return all nodes with that tag and their subtrees
        elif self.tags[tag]['scope'] == 'subtree':
            tag_subtrees = []
            for node in tagged_nodes:
                # add all nodes in subtree of node to tag_subtrees
                tag_subtrees.extend(subtree_list(node))
            # remove duplicates
            tag_subtrees = list(set(tag_subtrees))
            return tag_subtrees

        # for tags with "ancestry" scope, return all nodes with that tag and their ancestors
        elif self.tags[tag]['scope'] == 'ancestry':
            tag_ancestors = []
            for node in tagged_nodes:
                # add all ancestors of node to tag_ancestors
                ancestors = self.ancestry(node)
                tag_ancestors.extend(ancestors)
            # remove duplicates
            tag_ancestors = list(set(tag_ancestors))
            return tag_ancestors
        else:
            print('invalid scope')
            return

    def tagged_indices(self, tag, filter=None):
        if tag not in self.tags:
            print('no such tag')
            return
        nodes = self.nodes_list(filter)
        return {idx: d for idx, d in enumerate(nodes) if self.has_tag(d, tag)}

    def has_tag_attribute(self, node, tag):
        return 'tags' in node and node['tags'] is not None and tag in node['tags']

    def has_tag(self, node, tag):
        #print(node)
        if tag not in self.tags:
            return False
        if self.tags[tag]['scope'] == 'node':
            return self.has_tag_attribute(node, tag)
        elif self.tags[tag]['scope'] == 'subtree':
            # check if one of ancestors has tag
            for ancestor in self.ancestry(node):
                if self.has_tag_attribute(ancestor, tag):
                    return True
            return False
        elif self.tags[tag]['scope'] == 'ancestry':
            # check if one of descendents has tag
            for descendant in subtree_list(node):
                if self.has_tag_attribute(descendant, tag):
                    return True
            return False
        else:
            print('invalid scope')
            return


    # temporary function to turn root-level attributes into a tag in all nodes
    # TODO
    def turn_attributes_into_tags(self):
        self.tree_raw_data['tags'] = DEFAULT_TAGS
        for attribute in ('bookmark', 'archived', 'canonical'):
            if attribute not in self.tags:
                self.add_tag(attribute, 'node')
            for node in self.nodes:
                if attribute in node:
                    self.tag_node(node, attribute)
                    del node[attribute]
        print('done')


    def tag_scope(self, node, tag):
        if self.tags[tag]['scope'] == 'node':
            return [node['id']]
        elif self.tags[tag]['scope'] == 'subtree':
            return subtree_list(node)
        elif self.tags[tag]['scope'] == 'ancestry':
            return [d['id'] for d in self.ancestry(node)]


    def update_tree_tag_changed(self, node, tag):
        if self.tags[tag]['hide'] or self.tags[tag]['show_only']:
            update_scope = self.tag_scope(node, tag)
            hidden_in_scope = [d for d in update_scope if not self.visible(self.node(d))]
            visible_in_scope = [d for d in update_scope if self.visible(self.node(d))]
            if self.has_tag_attribute(node, tag):
                if self.tags[tag]['hide']:
                    self.tree_updated(delete=hidden_in_scope)
                    return
            else:
                if self.tags[tag]['hide']:
                    self.tree_updated(add=visible_in_scope)
                    return
                elif self.tags[tag]['show_only']:
                    self.tree_updated(delete=hidden_in_scope)
                    return
        self.tree_updated(edit=[node['id']])


    #################################
    #   Text attributes
    #################################

    def add_text_attribute(self, node, attribute, text):
        if 'text_attributes' not in node:
            node['text_attributes'] = {}
        node['text_attributes'][attribute] = text
        self.tree_updated()


    def get_text_attribute(self, node, attribute):
        if 'text_attributes' not in node:
            return None
        if attribute not in node['text_attributes']:
            return None
        return node['text_attributes'][attribute]

    def remove_text_attribute(self, node, attribute):
        if 'text_attributes' not in node:
            return
        if attribute not in node['text_attributes']:
            return
        del node['text_attributes'][attribute]
        self.tree_updated()


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

        # if 'memories' not in self.tree_raw_data:
        #     self.tree_raw_data['memories'] = {}
        # self.memories = self.tree_raw_data["memories"]

        if 'summaries' not in self.tree_raw_data:
            self.tree_raw_data['summaries'] = {}
        self.summaries = self.tree_raw_data["summaries"]

        if 'model_responses' not in self.tree_raw_data:
            self.tree_raw_data['model_responses'] = {}
        self.model_responses = self.tree_raw_data['model_responses']

        # if 'tags' not in self.tree_raw_data:
        #     self.tree_raw_data['tags'] = DEFAULT_TAGS
        # self.tags = self.tree_raw_data['tags']

        # Generation settings
        self.tree_raw_data["generation_settings"] = {
            **DEFAULT_GENERATION_SETTINGS.copy(),
            **self.tree_raw_data.get("generation_settings", {})
        }

        self.tree_raw_data["inline_generation_settings"] = {
            **DEFAULT_INLINE_GENERATION_SETTINGS.copy(),
            **self.tree_raw_data.get("inline_generation_settings", {})
        }

        self.tree_raw_data["frame"] = self.tree_raw_data.get("frame", {})

        # View settings # TODO If there are more of these, reduce duplication
        self.tree_raw_data["visualization_settings"] = {
            **DEFAULT_VISUALIZATION_SETTINGS.copy(),
            **self.tree_raw_data.get("visualization_settings", {})
        }

        self.tree_raw_data["preferences"] = {
            **DEFAULT_PREFERENCES.copy(),
            **self.tree_raw_data.get("preferences", {})
        }

        self.tree_raw_data["module_settings"] = {
            **DEFAULT_MODULE_SETTINGS.copy(),
            **self.tree_raw_data.get("module_settings", {})
        }

        self.tree_raw_data['tags'] = {
            **DEFAULT_TAGS.copy(),
            **self.tree_raw_data.get('tags', {})
        }

        # self.tree_raw_data["chat_preferences"] = {
        #     **DEFAULT_CHAT_PREFERENCES.copy(),
        #     **self.tree_raw_data.get("chat_preferences", {})
        # }


    def copy_global_objects(self, new_tree):
        if 'chapters' not in new_tree:
            new_tree['chapters'] = self.chapters

        if 'canonical' not in new_tree:
            new_tree['canonical'] = self.canonical

        if 'memories' not in new_tree:
            new_tree['memories'] = self.memories

        if 'summaries' not in new_tree:
            new_tree['summaries'] = self.summaries

        # Generation settings
        new_tree["generation_settings"] = {
            **DEFAULT_GENERATION_SETTINGS.copy(),
            **self.tree_raw_data.get("generation_settings", {})
        }

        new_tree["inline_generation_settings"] = {
            **DEFAULT_INLINE_GENERATION_SETTINGS.copy(),
            **self.tree_raw_data.get("inline_generation_settings", {})
        }

        # View settings # TODO If there are more of these, reduce duplication
        new_tree["visualization_settings"] = {
            **DEFAULT_VISUALIZATION_SETTINGS.copy(),
            **self.tree_raw_data.get("visualization_settings", {})
        }

        new_tree["preferences"] = {
            **DEFAULT_PREFERENCES.copy(),
            **self.tree_raw_data.get("preferences", {})
        }

        self.tree_raw_data['tags'] = {
            **DEFAULT_TAGS.copy(),
            **self.tree_raw_data.get('tags', {})
        }

        return new_tree

    def load_tree_data(self, data, init_global=True):
        if "root" not in data:
            # json file with a root node
            self.tree_raw_data = deepcopy(EMPTY_TREE)
            if "text" in data:
                self.tree_raw_data['root'] = data
            else:
                self.tree_raw_data['root']['children'] = data
            fix_tree(self.tree_raw_data)
        else:
            self.tree_raw_data = data
        self.tree_node_dict = {d["id"]: d for d in flatten_tree(self.tree_raw_data["root"])}

        # If things don't have an open state, give one to them
        for node in self.tree_node_dict.values():
            node["open"] = node.get("open", False)

        if init_global:
            self._init_global_objects()
        self.tree_updated(rebuild=True, write=False)

        self.select_node(self.tree_raw_data.get("selected_node_id", self.root()['children'][0]['id']))


    # Open a new tree json
    def open_tree(self, filename):
        self.tree_filename = os.path.abspath(filename)
        self.load_tree_data(json_open(self.tree_filename))
        self.io_update()

    def open_empty_tree(self):
        self.tree_filename = None
        self.load_tree_data(deepcopy(EMPTY_TREE))
        self.io_update()

    # Open a new tree json
    # TODO if you try to import things that already exist in tree this causes problems
    # because of duplicate IDs
    # TODO does metadata of subtree overwrite parent tree?
    def import_tree(self, filename):
        tree_json = json_open(filename)
        if 'root' in tree_json:
            new_subtree_root = tree_json['root']
            if not new_subtree_root['mutable']:
                new_subtree_root['mutable'] = True
            self.add_subtree(self.selected_node, new_subtree_root)
            # self.selected_node['children'].append(new_subtree_root)
            # new_subtree_root['parent_id'] = self.selected_node_id
            if 'chapters' in tree_json:
                #self.import_chapters(new_subtree_root, tree_json['chapters'])
                self.chapters.update(tree_json['chapters'])
            if 'tags' in tree_json:
                self.tags.update(tree_json['tags'])
            self.load_tree_data(self.tree_raw_data)
            self.tree_updated()
            self.io_update()
        else:
            if 'id' in tree_json:
                self.add_subtree(self.selected_node, tree_json)
                self.load_tree_data(self.tree_raw_data)
                self.tree_updated()
                self.io_update()
            else:
                print('improperly formatted tree')

    def add_subtree(self, node, subtree_root):
        node['children'].append(subtree_root)
        subtree_root['parent_id'] = node['id']

    # open new tree with node as root
    def open_node_as_root(self, node=None, new_filename=None, save=True, rebuild_global=False):
        if save:
            self.save_tree()
        node = self.selected_node if not node else node
        if new_filename:
            self.tree_filename = os.path.join(os.getcwd() + '/data', f'{new_filename}.json')
        # new_root = node
        if 'parent_id' in node:
            node.pop('parent_id')
        self.load_tree_data(node, init_global=rebuild_global)

    # current node acts like root from now on
    #
    # creates parent node with ancestry text
    def hoist(self, node=None):
        node = self.selected_node if not node else node
        if self.is_root(node):
            print('cannot hoist root')
            return
        new_root = self.zip(head=self.root(), tail=node, refresh_nav=False, update_selection=False)
        self.tree_raw_data['root'] = new_root
        new_root['open'] = True
        new_root['hoisted'] = True
        self.tree_updated(rebuild=True, write=False)
        self.select_node(new_root['id'])


    def unhoist(self, rebuild=True, update_selection=True):
        old_root = self.root()
        if not self.is_hoisted(old_root):
            print('nothing hoisted')
            return
        new_root = self.unzip(mask=self.root(), refresh_nav=False, update_selection=False)
        self.tree_raw_data['root'] = new_root
        if self.selected_node_id == old_root['id']:
            self.selected_node_id = new_root['id']
        if rebuild:
            self.tree_updated(rebuild=True, write=False)
        else:
            self.rebuild_tree()
        if update_selection:
            self.selection_updated()
        return new_root

    def unhoist_all(self):
        old_selection = self.selected_node
        while self.is_compound(self.root()):
            self.unhoist(rebuild=False, update_selection=False)
        self.tree_updated(rebuild=True, write=False)
        if self.selected_node_id != old_selection['id']:
            self.selection_updated()


    def tree_dir(self):
        return os.path.dirname(self.tree_filename)

    # Tree flat data is just a different view to tree raw data!
    # We edit tree flat data with tkinter and save raw data which is still in json form
    def save_tree(self, backup=True, save_filename=None, subtree=None):
        save_filename = save_filename if save_filename else self.tree_filename
        subtree = subtree if subtree else self.tree_raw_data
        if not save_filename:
            return False
        print('saving tree')

        # Fancy platform independent os.path
        filename = os.path.splitext(os.path.basename(save_filename))[0]
        save_dir = os.path.dirname(self.tree_filename)
        backup_dir = os.path.join(save_dir, "backups")

        # Make backup before overwriting tree
        if backup and os.path.isfile(save_filename):
            if not os.path.exists(backup_dir):
                os.mkdir(backup_dir)
            os.rename(save_filename, os.path.join(backup_dir, f"{filename}-{timestamp()}.json"))

        # print('chapters:', subtree['chapters'])
        # Save tree
        json_create(save_filename, subtree)
        self.io_update()
        return True

    def export_subtree(self, root, filename, filter=None, copy_attributes=None):
        filtered_tree = tree_subset(root, filter=filter, copy_attributes=copy_attributes)
        filtered_tree = {'root': filtered_tree}
        if 'tags' in copy_attributes:
            filtered_tree['tags'] = self.tags
        if 'chapter_id' in copy_attributes:
            filtered_tree['chapters'] = self.chapters
        # TODO copy globals
        json_create(filename, filtered_tree)
        self.io_update()

    def save_simple_tree(self, save_filename, subtree=None):
        subtree = subtree if subtree else self.tree_raw_data
        simple_tree = make_simple_tree(subtree)
        json_create(save_filename, simple_tree)
        self.io_update()

    def save_jsonl(self, save_filename=None, subtree=None):
        subtree = subtree if subtree else self.tree_raw_data
        flat_tree = self.nodes
        save_filename = save_filename if save_filename else os.path.splitext(os.path.basename(self.tree_filename))[0]+ '.jsonl'
        filename = os.path.join(os.getcwd() + '/data/exports', save_filename)
        with jsonlines.open(filename, mode='w') as writer:
            for line in flat_tree:
                line_dict = {'id': line['id']}
                if 'text' in line:
                    line_dict['text'] = line['text']
                if 'parent_id' in line:
                    line_dict['parent_id'] = line['parent_id']
                writer.write(line_dict)
        self.io_update()

    def flat_export(self, subtree=None):
        subtree = subtree if subtree else self.tree_raw_data
        flat_tree = self.nodes
        export_body = ''
        for line in flat_tree:
            export_body += '\t{'
            export_body += f'id: {repr(line["id"])}'
            if 'text' in line:
                export_body += f', text: {repr(line["text"])}'
            if 'parent_id' in line:
                export_body += f', parentId: {repr(line["parent_id"])}'
            if 'children' in line and len(line['children']) > 0:
                export_body += f', hasChildren: true'
            if 'tags' in line and len(line['tags']) > 0:
                export_body += f', tags: {repr(line["tags"])}'
            else: 
                export_body += f', tags: []'
            export_body += '},\n'
        export_string = f'[\n{export_body}]'
        print(export_string)

    def export_history(self, node, filename):
        history = self.ancestry_text(node)
        f = open(filename, "w")
        f.write(history)
        f.close()

    #################################
    #   Generation
    #################################

    def post_generation(self, error, nodes, results):
        if not error:
            #TODO adaptive branching
            self.model_responses[results['id']] = results
            self.set_generated_nodes(nodes, results)
        else:
            self.delete_failed_nodes(nodes, error)
            return

        for result in results['completions']:
            print("Generated continuation:\n", result['text'], "\nerror", error)

        # DO NOT CALL FROM THREAD: self.tree_updated()
        self.app.event_generate("<<NewNodes>>", when="tail")

    def default_post_template(self, completion):
        start_text = codecs.decode(self.generation_settings['start'], "unicode-escape")
        restart_text = codecs.decode(self.generation_settings['restart'], "unicode-escape")
        return start_text + completion['text'] + restart_text

    def custom_post_template(self, completion, filename):
        text = completion['text']
        with open(f'./config/post_templates/{filename}.txt', 'r') as f:
            prompt = f.read()
        eval_prompt = eval(f'f"""{prompt}"""')
        return eval_prompt

    def set_generated_nodes(self, nodes, results):
        for i, node in enumerate(nodes):
            node['text'] = self.default_post_template(results['completions'][i])
            # node['text'] = self.default_post_template(results['completions'][i]) \
            #     if self.generation_settings['post_template'] == "Default" \
            #     else self.custom_post_template(results['completions'][i], self.generation_settings['post_template'])
            self.node_creation_metadata(node, source='AI')
            node["generation"] = {'id': results['id'],
                                  'index': i}
            # TODO save history

    def delete_failed_nodes(self, nodes, error):
        print(f"ERROR {error}. Deleting failures")
        for node in nodes:
            parent = self.parent(node)
            parent["children"].remove(node)
        self.tree_updated(delete=[node['id'] for node in nodes])

    def default_generate(self, prompt, nodes):
        results, error = gen(prompt, self.generation_settings, self.model_config,
            OPENAI_API_KEY=self.OPENAI_API_KEY,
            AI21_API_KEY=self.AI21_API_KEY,
            GOOSEAI_API_KEY=self.GOOSEAI_API_KEY,)
        self.post_generation(error, nodes, results)


    # if self.generation_settings['adaptive']:
    #     for i, result in enumerate(results.choices):
    #         min_logprob = np.argmin(result["logprobs"]["token_logprobs"])
    #         split_position = result["logprobs"]["text_offset"][min_logprob] - len(prompt)
    #         childtext = result["text"][:split_position]
    #         grandchild_text = result["text"][split_position:]
    #         nodes[i]["text"] = childtext
    #         grandchildren[i]["text"] = grandchild_text
    #         # TODO metadata

    def prompt(self, node):
        if self.generation_settings['template'] == 'Default':
            prompt = self.default_prompt(node)
        elif self.generation_settings['template'] == 'Antisummary':
            prompt = self.antisummary_prompt(node)
        elif self.generation_settings['template'] == 'Adaptive Summary':
            prompt = self.summary_prompt(node)
        else:
            prompt = self.custom_prompt(node, self.generation_settings['template'])
        return prompt

    def custom_prompt(self, node, filename):
        input = self.ancestry_text(node)
        input = input[-self.generation_settings['prompt_length']:]
        with open(f'./config/prompts/{filename}.txt', 'r') as f:
            prompt = f.read()
        eval_prompt = eval(f'f"""{prompt}"""')
        eval_prompt = eval_prompt[-6000:]
        return eval_prompt

    def antisummary_embedding(self, summary):
        return f'\n[Next section summary: {summary}]\n'

    def antisummary_prompt(self, node):
        prompt = ''
        ancestry = self.ancestry(node)
        ancestor_ids = [ancestor['id'] for ancestor in ancestry]
        for ancestor in ancestry:
            if 'summaries' in ancestor and len(ancestor['summaries']) > 0:
                for summary_id in ancestor['summaries']:
                    summary = self.summaries[summary_id]
                    # only add summary if entire summarized text is in prompt
                    if summary['end_id'] in ancestor_ids:
                        prompt += self.antisummary_embedding(summary['text'])
            prompt += ancestor['text']
        prompt = prompt[-self.generation_settings['prompt_length']:]
        return prompt

    # builds a summarization prompt with default summarization few-shots and any summaries from ancestry
    def summary_prompt(self, node, num_summaries=3):
        passages = []
        summaries = []

        # load summaries json
        with open(f'./config/fewshots/summaries.json', 'r') as f:
            sum_json = json.load(f)
        
        for entry in sum_json:
            # add to passages and summaries
            passages.append(entry['passage'])
            summaries.append(entry['summary'])

        ancestry = self.ancestry(node)
        ancestor_ids = [ancestor['id'] for ancestor in ancestry]
        for ancestor in ancestry:
            if 'summaries' in ancestor and len(ancestor['summaries']) > 0:
                for summary_id in ancestor['summaries']:
                    summary = self.summaries[summary_id]
                    # only add summary if entire summarized text is in prompt
                    if summary['end_id'] in ancestor_ids:
                        end_node = self.node(summary['end_id'])
                        included_nodes = ancestry_in_range(root=ancestor, node=end_node)
                        passage_text = ''.join([node['text'] for node in included_nodes])
                        passages.append(passage_text)
                        summaries.append(summary['text'])

        # add the last num_summaries of the passages and summaries to a prompt
        prompt = ''
        if len(passages) > 0:
            for i in range(num_summaries):
                prompt += "\nPassage:\n"
                prompt += passages[-num_summaries + i]
                prompt += "\nSummary:\n"
                prompt += summaries[-num_summaries + i]

        input = self.ancestry_text(node)
        input = input[-self.generation_settings['prompt_length']:]

        prompt += "\nPassage:\n"
        prompt += input
        prompt += "\nSummary:\n"
        return prompt



    def default_prompt(self, node, prompt_length=None, memory=True, quiet=True):
        prompt = self.ancestry_text(node)
        if not prompt_length:
            prompt_length = self.generation_settings['prompt_length']
        prompt = prompt[-prompt_length:]

        global_context = self.generation_settings['global_context']

        memory = ''
        # if memory:
        #     memory_list = self.construct_memory(node)
        #     memory = ' '.join(memory['text'] for memory in memory_list)
        # else:
        #     memory = ''
        
        start_text = codecs.decode(self.generation_settings['start'], "unicode-escape")

        if not quiet:
            print("Global context:\n", global_context)
            print("Memory:\n", memory)
            if len(prompt) > 200:
                print("Prompt:\n", prompt[:100] + " ... " + prompt[-100:])
            else:
                print("Prompt:\n", prompt)
            if start_text:
                print("Start text: ", start_text)
            # print("Prompt:\n", prompt)
        return global_context + memory + prompt + start_text

    def autocomplete_generate(self, appended_text, engine='curie'):
        # TODO memory and chat prepending - abstract this
        # TODO different behavior if not in submit box
        appended_text = self.pre_modifications(appended_text)
        prompt = self.default_prompt(prompt_length=4000) + appended_text
        # print('prompt: ', prompt)
        results, error = openAI_generate(prompt=prompt,
                                         length=1,  # TODO 3 or so
                                         num_continuations=1,
                                         temperature=0,
                                         logprobs=100,
                                         top_p=self.generation_settings['top_p'],
                                         engine=engine
                                         # TODO stop
                                         )

        counterfactuals = results.choices[0]['logprobs']['top_logprobs'][0]
        sorted_counterfactuals = list(sorted(counterfactuals.items(), key=lambda item: item[1], reverse=True))
        return sorted_counterfactuals

    def generate_continuations(self, node=None, update_selection=False, **kwargs):
        node = node if node else self.selected_node
        if not node:
            return

        children = []
        #grandchildren = []
        new_nodes = []
        # pprint(self.generation_settings)
        for i in range(self.generation_settings['num_continuations']):
            child = self.create_child(node, expand=True)
            children.append(child)
            new_nodes.append(child['id'])
            # if self.generation_settings['adaptive']:
            #     grandchild = self.create_child(child, update_selection=False, expand=True, refresh_nav=False)
            #     grandchildren.append(grandchild)
            #     new_nodes.append(grandchild['id'])

        self.new_nodes.append(new_nodes)
        self.tree_updated(add=new_nodes)
        #self.reveal_nodes(children + grandchildren)
        prompt = self.prompt(node=node)

        threading.Thread(target=self.default_generate, args=(prompt, children)).start()

        # After asking for the generation, set loading text
        for child in children:
            child["text"] = "\n\n** Generating **" if 'placeholder' not in kwargs else kwargs['placeholder']
            child['mutable'] = False
        # for grandchild in grandchildren:
        #     grandchild["text"] = "\n\n** Generating **"
        self.tree_updated(edit=new_nodes)
        if update_selection:
            self.select_node(children[0]["id"])

    def generate_tree_init(self, node=None, max_depth=2, branching_factor=2, interval=50, stop_condition=None,
                           temperature=1, engine='ada'):
        node = node if node else self.selected_node
        self.generate_tree(node, max_depth, branching_factor, interval, stop_condition, temperature, engine)
        new_nodes = []
        # while len(self.new_nodes) > 0:
        #     print(self.new_nodes)
        #     self.tree_updated(add=self.new_nodes[0])
        #     #new_nodes += self.new_nodes[0]
        #     del self.new_nodes[0]
        # #self.tree_updated(add=new_nodes)

    def generate_tree(self, node=None, max_depth=3, branching_factor=2, interval=50, stop_condition=None,
                      temperature=1, engine='ada'):
        node = node if node else self.selected_node
        print('generating children for node', node['id'])
        if max_depth == 0 or (stop_condition and stop_condition(node)):
            return
        prompt = self.default_prompt(quiet=False, node=node)
        results, error = openAI_generate(prompt=prompt,
                                         length=interval,
                                         num_continuations=branching_factor,
                                         temperature=temperature,
                                         logprobs=0,
                                         top_p=self.generation_settings['top_p'],
                                         engine=engine
                                         )
        # create child nodes
        children = []
        for i in range(branching_factor):
            child = self.create_child(node, update_selection=False, expand=True, refresh_nav=False)
            children.append(child)
        # set child nodes
        self.generated_nodes_metadata(children, results, prompt)
        self.tree_updated(add=[child['id'] for child in children])
        # for each child node, branch again
        for child in children:
            # self.new_nodes.append(child['id'])
            self.generate_tree(node=child, max_depth=max_depth - 1, branching_factor=branching_factor,
                               interval=interval,
                               stop_condition=stop_condition, temperature=temperature, engine=engine)

        # TODO multi threading

    def generate_adaptive_tree(self, node=None, max_depth=3, branching_factor=2, max_interval=100, algorithm='min',
                               min_interval=None, stop_condition=None):
        pass

        # TODO range

    def semantic_search_memory(self, node, document_limit=100, max_length=1000):
        documents = []

        # join nodes that are too small
        for ancestor in self.ancestry(node)[:-1]:
            text = ancestor['text']
            while len(text) > max_length:
                documents.append(text[:max_length])
                text = text[max_length:]
            documents.append(text)
        # documents.reverse()
        query = node['text']
        return search(query, documents)

    # modifications made to text submitted using input box
    # TODO split into pre and post user input modifications
    def submit_modifications(self, text):
        return self.post_modifications(self.pre_modifications(text))

    # submit modifications prepended to user input
    def pre_modifications(self, text):
        if text and self.selected_node['text'] \
                and self.selected_node['text'][-1] not in ['"', '\'', '\n', '-', '(', '{', '[', '*'] \
                and text[0] != ' ':
            text = ' ' + text
        else:
            text = text
        return text

    # submit modifications appended to user input
    def post_modifications(self, text):
        # if self.preferences['gpt_mode'] == 'dialogue':
        #     # add punctuation if there isn't any
        #     if len(text) > 0 and text[-1] not in [',', '.', '!', '?', '-']:
        #         # TODO figure out most appropriate punctuation using gpt
        #         text = text + '.'
        #     text = text + '"'
        return text

    # TODO token index ???
    def score_counterfactual(self, node=None, target=None, context_breaker='', engine='curie'):
        if not target:
            return
        if not node:
            node = self.selected_node
        story = self.default_prompt(node=node, memory=False)
        return conditional_logprob(prompt=story + context_breaker, target=target, engine=engine)

    def measure_path_optimization(self, root, node):
        #node = node if node else self.selected_node
        #root = root if root else self.tree_raw_data["root"]
        nodes_list = self.ancestry(node=node, root=root)

        selection_bits = 0
        intervention_bits = 0
        total_tokens = 0
        for n in nodes_list:
            optimization_info = self.measure_node_optimization(node=n, quiet=True, final_node=node)
            intervention_bits += optimization_info['intervention_bits']
            selection_bits += optimization_info['selection_bits']
            total_tokens += optimization_info['num_tokens']

        print('intervention bits: {:.2f}'.format(intervention_bits))
        print('selection bits: {:.2f}'.format(selection_bits))
        total_bits = intervention_bits + selection_bits
        print('total bits: {:.2f}'.format(total_bits))
        print(f'bits per token: {total_bits:.2f}/{total_tokens} =', '{:.2f}'.format(total_bits / total_tokens))

    def measure_node_optimization(self, node=None, quiet=False, final_node=None):
        node = node if node else self.selected_node
        if 'meta' not in node:
            print('error: no meta attribute')
            return
        has_intervention_optimization = False
        has_selection_optimization = False
        if node["meta"]["source"] == "AI":
            # selection optimization
            has_selection_optimization = True
        elif node["meta"]["source"] == "mixed":
            # selection and intervention optimization
            has_selection_optimization = True
            has_intervention_optimization = True
        else:
            # human-written node, intervention optimization only
            has_intervention_optimization = True

        node_tokens = None

        if has_intervention_optimization:
            tokens_logprobs, node_tokens = self.changed_tokens_logprobs(node)
            if not quiet:
                print('\nOPTIMIZATION FROM TOKENS INJECTED')
                for token in tokens_logprobs:
                    print(f"'{token['token']}'")
                    print('logprob:', token['logprob'])
                    prob = logprobs_to_probs(token['logprob'])
                    print('prob:', prob)
                    optimization_power = 1 / prob
                    print('optimization power:', optimization_power)

            intervention_logprob = sum(token['logprob'] for token in tokens_logprobs)
            intervention_prob = logprobs_to_probs(intervention_logprob)
            intervention_optimization_power = 1 / intervention_prob
            intervention_bits = math.log2(intervention_optimization_power)

            if not quiet:
                print('\ntotal intervention logprob:', intervention_logprob)
                print('total intervention optimization power:', intervention_optimization_power)
                print(f'bits of intervention optimization: (log_2({intervention_optimization_power})) =',
                      intervention_bits)
                print(f'intervention bits per token: {intervention_bits}/{len(node_tokens)} =',
                      intervention_bits / len(node_tokens))
        else:
            intervention_optimization_power = 1
            intervention_bits = 0

        if has_selection_optimization:
            selection_optimization_power, selection_bits, node_tokens = self.selection_optimization(node=node,
                                                                                                    final_node=final_node)
            if not quiet:
                print('\ntotal selection optimization power:', selection_optimization_power)
                print(f'bits of selection optimization: (log_2({selection_optimization_power})) =',
                      selection_bits)
                print(f'selection bits per token: {selection_bits:.2f}/{len(node_tokens)} =',
                      selection_bits / len(node_tokens))

        else:
            selection_optimization_power = 1
            selection_bits = 0

        if not node_tokens:
            print('error, no node tokens')
            return

        optimization_info = {'intervention_power': intervention_optimization_power,
                             'intervention_bits': intervention_bits,
                             'selection_power': selection_optimization_power,
                             'selection_bits': selection_bits,
                             'num_tokens': len(node_tokens)}

        return optimization_info

        # TODO selection optimization

    # TODO removed tokens
    # TODO deprecated
    def changed_tokens_logprobs(self, node=None):
        node = node if node else self.selected_node
        if 'meta' in node and 'source' in node['meta']:
            if node["meta"]["source"] == "AI":
                return [], None
            if node["meta"]["source"] == "mixed":
                try:
                    original_tokens = node['meta']['diffs'][0]['diff']['old']
                    current_tokens = node['meta']['diffs'][-1]['diff']['new']
                except KeyError:
                    return [], None
                total_diff = diff(original_tokens, current_tokens)
                # uses original prompt
                prompt = node["meta"]["generation"]["prompt"] + node['text']
                engine = node["meta"]["generation"]["model"].split(':')[0]
                logprobs, tokens, positions = prompt_probs(prompt, engine)
                corrected_positions = [p - len(node["meta"]["generation"]["prompt"]) for p in positions]
                start = positions.index(len(node["meta"]["generation"]["prompt"]))
                changed_indices = []
                for word in total_diff['added']:
                    start_index = word['indices'][0]
                    token_index = corrected_positions.index(start_index)
                    token_logprob = logprobs[token_index]
                    token = tokens[token_index]
                    changed_indices.append({'token': token, 'logprob': token_logprob, 'indices': word['indices']})
                return changed_indices, tokens[start:]
            elif node["meta"]["source"] == "prompt":
                prompt = self.default_prompt(node=node, quiet=True, mode='default')
                engine = self.generation_settings['model']
                logprobs, tokens, positions = prompt_probs(prompt, engine)
                start_index = positions.index(len(prompt) - len(node['text']))
                index = start_index
                changed_indices = []
                for logprob in logprobs[start_index:]:
                    changed_indices.append({'token': tokens[index], 'logprob': logprob})
                    index += 1
                return changed_indices, tokens[start_index:]

    # TODO count all AI siblings of current node regardless of order?
    def selection_optimization(self, node, final_node=None):
        final_node = final_node if final_node else self.selected_node
        siblings = self.parent(node)["children"]
        competing_siblings = 0
        # this should include the node itself
        for sibling in siblings:
            if not ('meta' in sibling and 'source' in sibling['meta'] and sibling['meta']['source'] == 'prompt'):
                competing_siblings += 1
            # if 'meta' in sibling and 'source' in sibling['meta'] and sibling['meta']['source'] != 'prompt':
            #     if created_before(sibling, final_node):
            #         competing_siblings += 1

        selection_optimization_power = competing_siblings
        selection_bits = math.log2(selection_optimization_power)

        if node["meta"]["source"] == 'AI':
            tokens = node["meta"]["generation"]["logprobs"]["tokens"]
        else:
            tokens = node['meta']['diffs'][-1]['diff']['new'][0]

        return selection_optimization_power, selection_bits, tokens

    def generate_greedy_multiverse(self, prompt=None, node=None, ground_truth=None, max_depth=3,
                                   unnormalized_amplitude=1, threshold=0.1, engine='ada'):
        print('propagating wavefunction')
        print('max depth:', max_depth)
        print('threshold:', threshold)
        print('ground truth:', ground_truth)
        threshold = threshold * unnormalized_amplitude
        prompt = prompt if prompt else ''
        node = node if node else self.selected_node
        prompt = self.default_prompt(quiet=True, node=node) + prompt
        model_info = self.model_config['models'][engine]
        multiverse, ground_truth = greedy_word_multiverse(prompt=prompt, ground_truth=ground_truth, max_depth=max_depth,
                                                          unnormalized_amplitude=unnormalized_amplitude,
                                                          unnormalized_threshold=threshold,
                                                          engine=engine,
                                                          goose=model_info['type'] == 'gooseai')
        return multiverse, ground_truth, prompt


    def get_request_info(self, node):
        model_response = self.model_responses.get(node['generation']['id'], False)
        if not model_response:
            return None, '', ''
        prompt = model_response['prompt']['text']
        completion = model_response['completions'][node['generation']['index']]
        return model_response, prompt, completion


    #################################
    #   Cleaning
    #################################


    # TODO deprecated
    def delete_counterfactuals(self, root=None):
        if not root:
            root = self.tree_raw_data["root"]
        if 'meta' in root:
            if 'generation' in root['meta']:
                if 'logprobs' in root['meta']['generation']:
                    root['meta']['generation']["logprobs"]["top_logprobs"] = []
                    # print('deleted logprobs')
        for child in root['children']:
            self.delete_counterfactuals(root=child)

    # TODO only strip generation metadata
    def strip_metadata(self, root=None, delete_chapters=False):
        root = root if root else self.root()
        if root == self.root() and delete_chapters:
            self.remove_all_chapters(root)
            self.tree_raw_data['chapters'] = {}
        if 'meta' in root:
            root.pop('meta')
        # if delete_chapters and 'chapter_id' in root:
        #     root.pop('chapter_id')
        for child in root['children']:
            self.strip_metadata(root=child)

    def clear_old_generation_metadata(self, root=None):
        root = root if root else self.root()
        print('...')
        if 'meta' in root and 'generation' in root['meta']:
            print('clearing generation data')
            root['meta'].pop('generation')
        for child in root['children']:
            self.clear_old_generation_metadata(child)


    def backup_and_delete_model_response_data(self, root=None):
        root = root if root else self.root()
        print('backing up model response data')
        # Fancy platform independent os.path
        save_dir = os.path.dirname(self.tree_filename)
        backup_dir = os.path.join(save_dir, "backups")
        if not os.path.exists(backup_dir):
            os.mkdir(backup_dir)
        json_create(os.path.join(backup_dir, f"model_responses-{timestamp()}.json"), self.tree_raw_data['model_responses'])
        self.tree_raw_data['model_responses'] = {}

    
        
