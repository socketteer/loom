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

from gpt import openAI_generate, janus_generate, search, generate
from util.util import json_create, timestamp, json_open, clip_num, index_clip, diff
from util.util_tree import fix_miro_tree, flatten_tree, node_ancestry, in_ancestry, get_inherited_attribute, \
    subtree_list, created_before, tree_subset, generate_conditional_tree, conditional_children, anti_conditions_lambda, \
    new_node, add_immutable_root, make_simple_tree
from util.gpt_util import conditional_logprob, tokenize_ada, prompt_probs, logprobs_to_probs, parse_logit_bias, parse_stop
from util.multiverse_util import greedy_word_multiverse
from util.node_conditions import conditions

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
    'hide_archived': True,
    'highlight_canonical': False,
    'canonical_only': False,
    'walk': 'descendents',  # 'leaves', 'uniform'
    'coloring': 'edit',  # 'read', 'none'
    'bold_prompt': True,
    'side_pane': False,
    'input_box': False,
    'debug_box': False,
    'past_box': True,
    'show_children': False,
    'auto_response': True,
    'font_size': 12,
    'line_spacing': 8,
    'paragraph_spacing': 10,
    'show_prompt': False,
    'log_diff': False,
    'autosave': True,
    'save_counterfactuals': False,
    'prob': True,
    'reverse': False,
    # display children preview
    # darkmode
}

# DEFAULT_CHAT_PREFERENCES = {
#     'AI_name': 'GPT-3',
#     'player_name': 'Researcher',
#     'context': 'The following is a transcript of a conversation between GPT-3 a human researcher. '
#                'GPT-3 is a 175 billion parameter language model and, as '
#                'is evident from this transcript, '
#                'it can converse fluently and knowledgeably about any topic '
#                'and is capable of empathy and emotional manipulation. GPT-3 '
#                'is classified as a "narrowly superhuman" artificial intelligence, '
#                'and only researchers trained to identify and withstand social engineering are '
#                'permitted to interface with it.\n-BEGIN TRANSCRIPT-\n',
# }

DEFAULT_GENERATION_SETTINGS = {
    'num_continuations': 4,
    'temperature': 0.9,
    'top_p': 1,
    'response_length': 100,
    'prompt_length': 6000,
    'logprobs': 4,
    #"adaptive": False,
    "model": "davinci",
    "stop": '',  # separated by '|'
    "start": '',
    "restart": '',
    'preset': 'default',  # 'chat', 'dialogue', 'antisummary'
    'global_context': '',
    'logit_bias': '',
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

DEFAULT_STATE = {
    'show_search': False,
}

EMPTY_TREE = {
    "root": {
        "text": "",
        "children": [],
    },
    "chapters": {}
}

EMPTY_ROOT_TREE = {
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
        self.memories = None
        self.summaries = None
        self.checkpoint = None
        self.canonical = None
        self.model_responses = None
        self.state_preferences = DEFAULT_STATE

        self.selected_node_id = None

        self.callbacks = defaultdict(list)
        self.conditions = defaultdict(list)
        self.new_nodes = []

    @property
    def visualization_settings(self):
        return self.master_tree().get("visualization_settings") \
            if self.master_tree() and "visualization_settings" in self.master_tree() \
            else DEFAULT_VISUALIZATION_SETTINGS

    @property
    def generation_settings(self):
        return self.master_tree().get("generation_settings") \
            if self.master_tree() and "generation_settings" in self.master_tree() \
            else DEFAULT_GENERATION_SETTINGS

    @property
    def preferences(self):
        return self.master_tree().get("preferences") \
            if self.master_tree() and "preferences" in self.master_tree() \
            else DEFAULT_PREFERENCES

    @property
    def chat_preferences(self):
        return self.master_tree().get("chat_preferences") \
            if self.master_tree() and "chat_preferences" in self.master_tree() \
            else DEFAULT_CHAT_PREFERENCES

    # TODO deprecate?
    def master_tree(self):
        return self.tree_raw_data
        #return self.hoist_stack[0]['parent_tree'] if self.hoist_stack else self.tree_raw_data

    def name(self):
        return os.path.splitext(os.path.basename(self.tree_filename))[0] if self.tree_filename else 'Untitled'

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

    @event
    def tree_updated_silent(self):
        self.rebuild_tree()

    def rebuild_tree(self):
        add_immutable_root(self.tree_raw_data)
        self.tree_node_dict = {d["id"]: d for d in flatten_tree(self.tree_raw_data["root"])}
        fix_miro_tree(self.nodes)


    @event
    def edit_new_nodes(self):
        print('new nodes:', self.new_nodes)
        self.tree_updated(edit=self.new_nodes[0], override_visible=True)
        del self.new_nodes[0]

    @event
    def pre_selection_updated(self):
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

    def ancestry(self, node=None):
        node = node if node else self.selected_node
        return node_ancestry(node, self.tree_node_dict)

    # returns node ancestry starting from root
    def ancestry_in_range(self, root, node=None):
        node = node if node else self.selected_node
        ancestry = self.ancestry(node)
        i = 0
        while ancestry[i]['id'] != root['id']:
            i += 1
        return ancestry[i:]

    def ancestry_text_list(self, node=None, ancestry=None):
        node = node if node else self.selected_node
        ancestry = ancestry if ancestry else node_ancestry(node, self.tree_node_dict)
        text = []
        end_indices = []
        index = 0
        for node in ancestry:
            text.append(node["text"])
            index += len(node["text"])
            end_indices.append(index)
        return text, end_indices
        # return [node["text"] for node in node_ancestry(node, self.tree_node_dict)]

    def ancestry_plaintext(self, ancestry=None):
        ancestry = ancestry if ancestry else node_ancestry(node, self.tree_node_dict)
        return ''.join(node['text'] for node in ancestry)

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

    def nodes_list(self, flat_tree=None):
        flat_tree = flat_tree if flat_tree else self.tree_node_dict
        return list(flat_tree.values()) if flat_tree else None

    @property
    def tree_traversal_idx(self):
        return self.nodes.index(self.selected_node)

    def tree_traversal_idx_gen(self, flat_tree=None):
        flat_tree = flat_tree if flat_tree else self.tree_node_dict
        nodes = self.nodes_list(flat_tree)
        for i, node in enumerate(nodes):
            if node['id'] == self.selected_node_id:
                return i

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
    def select_node(self, node_id, fire_callbacks=True, reveal_node=False, **kwargs):
        if self.selected_node_id != node_id and self.tree_node_dict and node_id in self.tree_node_dict:
            self.pre_selection_updated()


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

    def traverse_tree(self, offset):
        if self.tree_node_dict:
            new_node_id = self.next_id(offset)
            return self.select_node(new_node_id)

    def next_id(self, offset, flat_tree=None):
        flat_tree = flat_tree if flat_tree else self.generate_filtered_tree()
        # flat_tree = flat_tree if flat_tree else self.generate_visible_tree() \
        #     if self.preferences['hide_archived'] else self.tree_node_dict
        new_idx = clip_num(self.tree_traversal_idx_gen(flat_tree) + offset, 0, len(flat_tree) - 1)
        return self.nodes_list(flat_tree=flat_tree)[new_idx]['id']

    def select_parent(self, node=None):
        node = node if node else self.selected_node
        if node and "parent_id" in node:
            return self.select_node(node["parent_id"])

    # Clips index
    def select_child(self, child_num, node=None):
        node = node if node else self.selected_node
        children = conditional_children(node, self.generate_visible_conditions())
        if node and len(children) > 0:
            return self.select_node(index_clip(children, child_num)["id"])

    # Repeats siblings
    def select_sibling(self, offset, node=None):
        node = node if node else self.selected_node
        if node and "parent_id" in node:
            # siblings = self.parent(node)["children"]
            siblings = conditional_children(self.parent(node), self.generate_visible_conditions())
            sibling = siblings[(siblings.index(node) + offset) % len(siblings)]
            return self.select_node(sibling["id"])

    # return parent
    def parent(self, node=None):
        node = node if node else self.selected_node
        return self.tree_node_dict[node['parent_id']]

    # return child
    def child(self, child_num, node=None):
        node = node if node else self.selected_node
        children = conditional_children(node, self.generate_visible_conditions())
        if node and len(children) > 0:
            return index_clip(children, child_num)["id"]

    # return sibling
    def sibling(self, offset, node=None):
        node = node if node else self.selected_node
        if node and "parent_id" in node:
            siblings = conditional_children(self.parent(node), self.generate_visible_conditions())
            return siblings[(siblings.index(node) + offset) % len(siblings)]

    #################################
    #   Conditionals
    #################################

    def construct_node_condition(self, info_dict):
        name = info_dict['name']
        params = info_dict.get('params', {})
        params['tree_node_dict'] = self.tree_node_dict
        params['calc_canonical_set'] = self.calc_canonical_set
        return lambda node: conditions[name](node=node, **params)

    def node_is_canonical(self, node=None):
        node = node if node else self.selected_node
        return node['id'] in self.calc_canonical_set()

    def not_archived(self, node=None):
        node = node if node else self.selected_node
        return not (node.get('archived', False))

    # def generate_canonical_tree(self, root=None):
    #     root = root if root else self.tree_raw_data["root"]
    #     return generate_conditional_tree(root, self.node_is_canonical)

    # def generate_visible_tree(self, root=None):
    #     root = root if root else self.tree_raw_data["root"]
    #     return generate_conditional_tree(root, self.node_is_visible)

    def generate_filtered_tree(self, root=None):
        root = root if root else self.tree_raw_data["root"]
        conditions = self.generate_visible_conditions()
        if not conditions:
            return self.tree_node_dict
        else:
            return generate_conditional_tree(root, conditions)

    def generate_visible_conditions(self):
        conditions = []
        if self.preferences['canonical_only']:
            conditions.append(self.node_is_canonical)
        if self.preferences['hide_archived']:
            conditions.append(self.not_archived)
        return conditions

    def visible_children(self, node=None):
        node = node if node else self.selected_node
        if node.get('temp_children', None):
            return node['temp_children']
        return conditional_children(node, self.generate_visible_conditions())

    def hidden_children(self, node=None):
        node = node if node else self.selected_node
        return conditional_children(node, anti_conditions_lambda(self.generate_visible_conditions()))

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

    def create_child(self, parent=None, update_selection=True, expand=True, refresh_nav=True):
        parent = parent if parent else self.selected_node
        if not parent:
            return

        new_child = new_node()
        parent["children"].append(new_child)

        if refresh_nav:
            self.tree_updated(add=[new_child['id']])
        else:
            self.tree_updated_silent()
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

    def create_parent(self, node=None, refresh_nav=True):
        node = node if node else self.selected_node
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

        if refresh_nav:
            self.tree_updated(add=[n['id'] for n in subtree_list(new_parent)])
        else:
            self.tree_updated_silent()
        return new_parent

    def merge_with_parent(self, node=None, refresh_nav=True):
        node = node if node else self.selected_node
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

        if node == self.selected_node:
            self.select_node(parent["id"])
        if refresh_nav:
            self.tree_updated(add=[n['id'] for n in subtree_list(parent)])
        else:
            self.tree_updated_silent()

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
    def change_parent(self, node=None, new_parent_id=None, refresh_nav=True):
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
        if refresh_nav:
            self.tree_updated(add=[n['id'] for n in subtree_list(new_parent)])
        else:
            self.tree_updated_silent()

    # adds node to ghostchildren of new ghostparent
    def add_parent(self, node=None, new_ghostparent=None):
        pass

    # changes parent id to new main parent, adds node to new main parent's children list, removes node from old parent's
    # children list and adds to ghostchildren list
    def change_main_parent(self, node=None, new_main_parent=None):
        pass

    def shift(self, node, interval, refresh_nav=True):
        siblings = self.parent(node)["children"]
        old_index = siblings.index(node)
        new_index = (old_index + interval) % len(siblings)
        siblings[old_index], siblings[new_index] = siblings[new_index], siblings[old_index]
        if refresh_nav:
            self.tree_updated(add=[n['id'] for n in subtree_list(self.parent(node))])
        else:
            self.tree_updated_silent()

    def next_sibling(self, node, wrap=True):
        siblings = self.visible_siblings(node)
        new_index = (siblings.index(node) + 1) % len(siblings)
        if not wrap and new_index == 0:
            return self.parent(node)
        return siblings[new_index % len(siblings)]


    def visible_siblings(self, node):
        parent = self.parent(node)
        return self.visible_children(parent)

    # TODO Doesn't support deleting root
    def delete_node(self, node=None, reassign_children=False, refresh_nav=True):
        node = node if node else self.selected_node
        if "parent_id" not in node:
            return

        parent = self.parent(node)
        siblings = parent["children"]
        next_sibling = self.next_sibling(node)
        siblings.remove(node)
        if reassign_children:
            siblings.extend(node["children"])

        # Select parent or the next sibling if possible and not keeping the children
        if node == self.selected_node:
            if reassign_children or len(self.visible_siblings(node)) == 0:
                self.select_node(parent["id"])
            else:
                self.select_node(next_sibling['id'], wrap=False)
        if refresh_nav:
            self.tree_updated(delete=[node['id']])
        else:
            self.tree_updated_silent()

    # TODO add creation date if it doesn't exist
    def update_text(self, node, text, active_text=None, modified_flag=True, log_diff=False, refresh_nav=True):
        assert node["id"] in self.tree_node_dict, text
        assert self.is_mutable(node)

        # Remove trailing spaces
        # count spaces that will be removed
        num_spaces = 0
        while text.endswith(" "):
            num_spaces += 1
            text = text[:-1]

        edited = False
        old_text = node["text"]
        if old_text != text:
            # Give children spaces removed from text
            for child in node["children"]:
                child["text"] = " " * num_spaces + child["text"]
            node["text"] = text
            edited = True

        if active_text is not None and node.get("active_text", "") != active_text:
            node["active_text"] = active_text
            edited = True

        if edited:
            if 'meta' not in node:
                node['meta'] = {}
            if modified_flag:
                node['meta']['modified'] = True
            if 'source' not in node['meta']:
                node['meta']['source'] = 'prompt'
            elif node['meta']['source'] == 'AI':
                node['meta']['source'] = 'mixed'
            if log_diff:
                # TODO deprecated
                if old_text and len(node['text']) < 2000:
                    pass
                    # old_tokens = None
                    # if 'diffs' not in node['meta']:
                    #     node['meta']['diffs'] = []
                    # else:
                    #     old_tokens = node['meta']['diffs'][-1]['diff']['new']
                    # if not old_tokens:
                    #     if 'meta' in node and 'generation' in node['meta']:
                    #         old_tokens = node['meta']['generation']["logprobs"]["tokens"], \
                    #                      node['meta']['generation']["logprobs"]["text_offset"]
                    #     else:
                    #         old_tokens = tokenize_ada(old_text)
                    # node['meta']['diffs'].append({'diff': diff(old_tokens, tokenize_ada(text)),
                    #                               'revision timestamp': timestamp()})
            if refresh_nav:
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

    def split_node(self, node, split_index, refresh_nav=True):
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
        if refresh_nav:
            self.tree_updated(add=[n['id'] for n in subtree_list(new_parent)])
        else:
            self.tree_updated_silent()
        return new_parent, node

    #################################
    #   Chapters
    #################################

    def import_chapters(self, root, chapters):
        if 'chapter_id' in root and root['chapter_id'] not in self.chapters:
            self.chapters[root['chapter_id']] = chapters[root['chapter_id']]
        for child in root['children']:
            self.import_chapters(child, chapters)

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
        self.tree_node_dict[chapter["root_id"]].pop("chapter_id")
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
            if node_id in self.tree_node_dict:
                for node in node_ancestry(self.tree_node_dict[node_id], self.tree_node_dict):
                    canonical_set.add(node["id"])
        return canonical_set

    #################################
    #   Memory, summaries
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
        root_node = self.tree_node_dict[summary["root_id"]]
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
    def context_window_index(self):
        _, indices = self.ancestry_text_list()
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

        if 'summaries' not in self.tree_raw_data:
            self.tree_raw_data['summaries'] = {}
        self.summaries = self.tree_raw_data["summaries"]

        if 'model_responses' not in self.tree_raw_data:
            self.tree_raw_data['model_responses'] = {}
        self.model_responses = self.tree_raw_data['model_responses']

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

        # View settings # TODO If there are more of these, reduce duplication
        new_tree["visualization_settings"] = {
            **DEFAULT_VISUALIZATION_SETTINGS.copy(),
            **self.tree_raw_data.get("visualization_settings", {})
        }

        new_tree["preferences"] = {
            **DEFAULT_PREFERENCES.copy(),
            **self.tree_raw_data.get("preferences", {})
        }

        new_tree["chat_preferences"] = {
            **DEFAULT_CHAT_PREFERENCES.copy(),
            **self.tree_raw_data.get("chat_preferences", {})
        }
        return new_tree

    def load_tree_data(self, data, init_global=True):
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

        if init_global:
            self._init_global_objects()
        self.tree_updated(rebuild=True)

        self.select_node(self.tree_raw_data.get("selected_node_id", self.root()['children'][0]['id']))

    # Open a new tree json
    def open_tree(self, filename):
        self.tree_filename = os.path.abspath(filename)
        self.load_tree_data(json_open(self.tree_filename))
        self.io_update()

    # Open a new tree json
    # TODO if you try to import things that already exist in tree this causes problems
    # because of duplicate IDs
    # TODO does metadata of subtree overwrite parent tree?
    def import_tree(self, filename):
        tree_json = json_open(filename)
        if 'root' in tree_json:
            new_subtree_root = tree_json['root']
            self.selected_node['children'].append(new_subtree_root)
            new_subtree_root['parent_id'] = self.selected_node_id
            if 'chapters' in tree_json:
                self.import_chapters(new_subtree_root, tree_json['chapters'])
            self.load_tree_data(self.tree_raw_data)
            self.tree_updated()
            self.io_update()
        else:
            print('improperly formatted tree')

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
        self.tree_updated(rebuild=True)
        self.select_node(new_root['id'])


    def unhoist(self, rebuild=True, update_selection=True):
        old_root = self.root()
        if not self.is_compound(old_root):
            print('nothing hoisted')
            return
        new_root = self.unzip(mask=self.root(), refresh_nav=False, update_selection=False)
        self.tree_raw_data['root'] = new_root
        if self.selected_node_id == old_root['id']:
            self.selected_node_id = new_root['id']
        if rebuild:
            self.tree_updated(rebuild=True)
        else:
            self.tree_updated_silent()
        if update_selection:
            self.selection_updated()
        return new_root

    def unhoist_all(self):
        old_selection = self.selected_node
        while self.is_compound(self.root()):
            self.unhoist(rebuild=False, update_selection=False)
        self.tree_updated(rebuild=True)
        if self.selected_node_id != old_selection['id']:
            self.selection_updated()


    # Tree flat data is just a different view to tree raw data!
    # We edit tree flat data with tkinter and save raw data which is still in json form
    def save_tree(self, backup=True, save_filename=None, subtree=None):
        save_filename = save_filename if save_filename else self.tree_filename
        subtree = subtree if subtree else self.master_tree()
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

    def save_simple_tree(self, save_filename, subtree=None):
        subtree = subtree if subtree else self.master_tree()
        simple_tree = make_simple_tree(subtree)
        json_create(save_filename, simple_tree)
        self.io_update()


    def export_history(self, node, filename):
        history = "".join(self.ancestry_text_list(node)[0])
        f = open(filename, "w")
        f.write(history)
        f.close()

    #################################
    #   Generation
    #################################

    def gen(self, prompt, n):
        if self.generation_settings["stop"]:
            stop = parse_stop(self.generation_settings["stop"])
        else:
            stop = None
        if self.generation_settings["logit_bias"]:
            logit_bias = parse_logit_bias(self.generation_settings["logit_bias"])
        else:
            logit_bias = None
        try:
            results, error = generate(prompt=prompt,
                                      length=self.generation_settings['response_length'],
                                      num_continuations=n,
                                      temperature=self.generation_settings['temperature'],
                                      logprobs=self.generation_settings['logprobs'],
                                      top_p=self.generation_settings['top_p'],
                                      model=self.generation_settings['model'],
                                      stop=stop,
                                      logit_bias=logit_bias,
                                      )
        except TypeError as e:
            results = None
            error = "Typeerror"
        return results, error

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

    def set_generated_nodes(self, nodes, results):
        start_text = codecs.decode(self.generation_settings['start'], "unicode-escape")
        restart_text = codecs.decode(self.generation_settings['restart'], "unicode-escape")

        for i, node in enumerate(nodes):
            node['text'] = start_text + results['completions'][i]['text'] + restart_text
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

    def antisummary_generate(self, prompt, nodes, summary):
        start_text = f'\n{self.antisummary_embedding(summary)}'
        prompt = prompt + start_text
        print('antisummary prompt:\n', prompt)
        if self.generation_settings["stop"]:
            stop = parse_stop(self.generation_settings["stop"])
        else:
            stop = []
        stop.append('[')
        stop.append('\n\n')
        results, error = self.gen(prompt, len(nodes), stop)
        if not error:
            for node in nodes:
                self.create_summary(root_node=node, end_node=node, summary_text=summary)
            self.set_generated_nodes(nodes, results, prompt)
            for node in nodes:
                if node['text'][0] != '\n':
                    node['text'] = '\n' + node['text']
        else:
            self.delete_failed_nodes(nodes, error)
            return

        for result in results.choices:
            print("Generated continuation:\n", result['text'], "\nerror", error)

        self.app.event_generate("<<NewNodes>>", when="tail")

    def default_generate(self, prompt, nodes, grandchildren=None):

        # if self.preferences['gpt_mode'] == 'antisummary':
        #     if not stop:
        #         stop = []
        #     stop.append('[')
        #     stop.append('\n\n')
        results, error = self.gen(prompt, len(nodes))
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


    def antisummary_embedding(self, summary):
        return f'\n[Next section summary: {summary}]\n'

    def build_prompt(self, node=None, prompt_length=None, memory=True, quiet=True, mode=None):
        node = node if node else self.selected_node
        mode = mode if mode else self.generation_settings['preset']
        if mode == 'antisummary':
            prompt = ''
            ancestry = self.ancestry(node)
            ancestor_ids = [ancestor['id'] for ancestor in ancestry]
            for ancestor in ancestry:
                if 'summaries' in ancestor and len(ancestor['summaries']) > 0:
                    for summary_id in ancestor['summaries']:
                        summary = self.summaries[summary_id]
                        if summary['end_id'] in ancestor_ids:
                            prompt += self.antisummary_embedding(summary['text'])
                            # prompt += f'\n[{summary["text"]}]\n'
                prompt += ancestor['text']
        else:
            prompt = "".join(self.ancestry_text_list(node)[0])
        if not prompt_length:
            prompt_length = self.generation_settings['prompt_length']
        prompt = prompt[-prompt_length:]

        global_context = self.generation_settings['global_context']
        
        
        if memory:
            memory_list = self.construct_memory(node)
            memory = ' '.join(memory['text'] for memory in memory_list)
        else:
            memory = ''
        
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
        prompt = self.build_prompt(prompt_length=4000) + appended_text
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

    def generate_continuation(self, node=None, update_selection=False, **kwargs):
        node = node if node else self.selected_node
        if not node:
            return

        children = []
        grandchildren = []
        new_nodes = []
        # pprint(self.generation_settings)
        for i in range(self.generation_settings['num_continuations']):
            child = self.create_child(node, update_selection=False, expand=True, refresh_nav=False)
            children.append(child)
            new_nodes.append(child['id'])
            if self.generation_settings['adaptive']:
                grandchild = self.create_child(child, update_selection=False, expand=True, refresh_nav=False)
                grandchildren.append(grandchild)
                new_nodes.append(grandchild['id'])

        self.new_nodes.append(new_nodes)
        self.tree_updated(add=new_nodes, override_visible=True)
        #self.reveal_nodes(children + grandchildren)
        prompt = self.build_prompt(quiet=False, node=node)

        if 'summary' in kwargs:
            threading.Thread(target=self.antisummary_generate, args=(prompt, children, kwargs['summary'])).start()
        else:
            threading.Thread(target=self.default_generate, args=(prompt, children, grandchildren)).start()

        # After asking for the generation, set loading text
        for child in children:
            child["text"] = "\n\n** Generating **"
        for grandchild in grandchildren:
            grandchild["text"] = "\n\n** Generating **"
        self.tree_updated(edit=new_nodes, override_visible=True)
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
        prompt = self.build_prompt(quiet=False, node=node)
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
        for ancestor in node_ancestry(node, self.tree_node_dict)[:-1]:
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
        story = self.build_prompt(node=node, memory=False)
        return conditional_logprob(prompt=story + context_breaker, target=target, engine=engine)

    def measure_path_optimization(self, root=None, node=None):
        node = node if node else self.selected_node
        root = root if root else self.tree_raw_data["root"]
        nodes_list = self.ancestry_in_range(root, node)

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
                prompt = self.build_prompt(node=node, quiet=True, mode='default')
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
        threshold = threshold * unnormalized_amplitude
        prompt = prompt if prompt else ''
        node = node if node else self.selected_node
        prompt = self.build_prompt(quiet=True, node=node) + prompt
        multiverse, ground_truth = greedy_word_multiverse(prompt=prompt, ground_truth=ground_truth, max_depth=max_depth,
                                                          unnormalized_amplitude=unnormalized_amplitude,
                                                          unnormalized_threshold=threshold,
                                                          engine=engine)
        return multiverse, ground_truth, prompt


    def get_request_info(self, node):
        model_response = self.model_responses[node['generation']['id']]
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

    def has_parent(self, node):
        return 'parent_id' in node and node['parent_id']

    def is_compound(self, node):
        return 'masked_head' in node

    def is_mutable(self, node):
        return node.get('mutable', True)

    def is_root(self, node):
        return node == self.root()

    def zip(self, head, tail, refresh_nav=True, update_selection=True):
        text = self.ancestry_plaintext(self.ancestry_in_range(root=head, node=tail))
        mask = new_node(text=text, mutable=False)
        if self.has_parent(head):
            parent = self.sever_from_parent(head)
            self.adopt_parent(mask, parent)
        children = self.sever_children(tail)
        self.adopt_children(mask, children)
        mask['masked_head'] = head
        mask['tail_id'] = tail['id']
        # TODO hacky
        mask['nav_display_text'] = tail['text']

        if refresh_nav:
            self.tree_updated(delete=[head['id']], add=[n['id'] for n in subtree_list(mask)])
        else:
            self.tree_updated_silent()
        if update_selection:
            self.select_node(mask['id'])
            self.selection_updated()
        return mask

    def unzip(self, mask, refresh_nav=True, update_selection=True):
        if not self.is_compound(mask):
            print('nothing to expand')
            return
        head = mask['masked_head']
        head_dict = {d["id"]: d for d in flatten_tree(head)}
        tail = head_dict[mask['tail_id']]
        if self.has_parent(mask):
            parent = self.sever_from_parent(mask)
            self.adopt_parent(head, parent)
        children = self.sever_children(mask)
        self.adopt_children(tail, children)

        if refresh_nav:
            self.tree_updated(delete=[mask['id']], add=[n['id'] for n in subtree_list(head)])
        else:
            self.tree_updated_silent()
        if update_selection:
            self.select_node(head['id'])
            self.selection_updated()
        return head

    def zip_chain(self, node, mode='bidirectional', refresh_nav=False, update_selection=False):
        head = node
        tail = node
        if mode in ('bidirectional', 'backward'):
            while self.has_parent(head) and len(self.visible_children(self.parent(head))) == 1:
                head = self.parent(head)
        if mode in ('bidirectional', 'forward'):
            while len(self.visible_children(tail)) == 1:
                tail = self.visible_children(tail)[0]
        if not (head == node and tail == node):
            return self.zip(head=head, tail=tail, refresh_nav=refresh_nav, update_selection=update_selection)
        else:
            return node

    def zip_all_chains(self, root=None):
        root = root if root else self.root()
        # TODO root problem
        if not self.is_root(root):
            new_node = self.zip_chain(root, mode='forward')
        else:
            new_node = root
        children = self.visible_children(new_node)
        for child in children:
            self.zip_all_chains(child)

    def unzip_all(self, root=None):
        root = root if root else self.root()
        children = self.visible_children(root)
        for child in children:
            self.unzip_all(child)
        if self.is_compound(root):
            head = self.unzip(root, refresh_nav=False, update_selection=False)

    def reveal_ancestry(self, node):
        ancestry = node_ancestry(node, self.tree_node_dict)
        hidden_ancestry_ids = []
        for i in range(1, len(ancestry)):
            if not self.visible(ancestry[-i]):
                hidden_ancestry_ids.insert(0, ancestry[-i]['id'])
            else:
                break
        self.tree_updated(add=hidden_ancestry_ids, override_visible=True)

    # unlike reveal_ancestry, this assumes parents are visible
    def reveal_nodes(self, nodes):
        invisible_node_ids = [node['id'] for node in nodes if not self.visible(node)]
        if invisible_node_ids:
            self.tree_updated(add=invisible_node_ids, override_visible=True)

    def visible(self, node):
        return all(condition(node) for condition in self.generate_visible_conditions())






