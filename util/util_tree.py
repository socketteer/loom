import uuid
import html2text
import numpy as np
import re
import random
from datetime import datetime


# Height of d, root has the greatest height, minimum is 1
def height(d):
    return 1 + max([0, *[height(c) for c in d["children"]]])

# Depth of d, root is 0 depth
def depth(d, node_dict):
    return 0 if "parent_id" not in d else (1 + depth(node_dict[d["parent_id"]], node_dict))


# Returns a list of ancestor nodes beginning with the progenitor
def node_ancestry(node, node_dict):
    ancestry = [node]
    while "parent_id" in node:
        node = node_dict[node["parent_id"]]
        ancestry.insert(0, node)
    return ancestry

# returns whether node_a was created before node_b
# TODO for old nodes, extract date from generation metadata...?
def created_before(node_a, node_b):
    try:
        timestamp1 = node_a['meta']['creation_timestamp']
        timestamp2 = node_b['meta']['creation_timestamp']
    except KeyError:
        print('error: one or more of the nodes has no timestamp attribute')
        return None
    t1 = datetime.strptime(timestamp1, "%Y-%m-%d-%H.%M.%S")
    t2 = datetime.strptime(timestamp2, "%Y-%m-%d-%H.%M.%S")
    return t1 <= t2

def nearest_common_ancestor(node_a, node_b, node_dict):
    ancestry_a = node_ancestry(node_a, node_dict)
    ancestry_b = node_ancestry(node_b, node_dict)
    # for node in ancestry_a:
    #     print(node['id'])
    # print('ancestry b')
    # for node in ancestry_b:
    #     print(node['id'])
    for i in range(1, len(ancestry_a)):
        if i > (len(ancestry_b) - 1) or ancestry_a[i] is not ancestry_b[i]:
            return ancestry_a[i-1], i-1
    return ancestry_a[-1], len(ancestry_a) - 1


def node_index(node, node_dict):
    return len(node_ancestry(node, node_dict)) - 1


# Returns True if a is ancestor of b
def in_ancestry(a, b, node_dict):
    ancestry = node_ancestry(b, node_dict)
    return a in ancestry


def get_inherited_attribute(attribute, node, tree_node_dict):
    for lineage_node in reversed(node_ancestry(node, tree_node_dict)):
        if attribute in lineage_node:
            return lineage_node[attribute]
    return None

# recursively called on subtree
def overwrite_subtree(node, attribute, new_value, old_value=None, force_overwrite=False):
    if force_overwrite or (attribute not in node) or old_value is None or (node[attribute] == old_value) \
            or (node[attribute] == new_value):
        node[attribute] = new_value
        terminal_nodes_list = []
        for child in node['children']:
            terminal_nodes_list += overwrite_subtree(child, attribute, new_value, old_value, force_overwrite)
        return terminal_nodes_list
    else:
        return [node]


def stochastic_transition(node, mode='descendents', filter_set=None):
    transition_probs = subtree_weights(node, mode, filter_set)
    choice = random.choices(node['children'], transition_probs, k=1)
    return choice[0]


def subtree_weights(node, mode='descendents', filter_set=None):
    weights = []
    if 'children' in node:
        for child in node['children']:
            if mode == 'descendents':
                weights.append(num_descendents(child, filter_set))
            elif mode == 'leaves':
                weights.append(num_leaves(child, filter_set))
            elif mode == 'uniform':
                weights.append(1)
            else:
                print('invalid mode for subtree weights')
    #print('unnormalized probabilities: ', weights)
    norm = np.linalg.norm(weights, ord=1)
    normalized_weights = weights / norm
    #print('probabilities: ', normalized_weights)
    return normalized_weights


def num_descendents(node, filter_set=None):
    if not filter_set or node["id"] in filter_set:
        descendents = 1
        if 'children' in node:
            for child in node['children']:
                if not filter_set or child["id"] in filter_set:
                    descendents += num_descendents(child)
    else:
        descendents = 0
    return descendents


def num_leaves(node, filter_set=None):
    if not filter_set or node["id"] in filter_set:
        if 'children' in node and len(node['children']) > 0:
            leaves = 0
            for child in node['children']:
                if not filter_set or child["id"] in filter_set:
                    leaves += num_leaves(child)
            return leaves
        else:
            return 1
    else:
        return 0

# TODO regex, tags
def search(root, pattern, text=True, tags=False, case_sensitive=False, regex=False, filter_set=None, max_depth=None):
    matches = []
    if not (text or tags) \
            or (filter_set is not None and root['id'] not in filter_set)\
            or max_depth == 0:
        return []
    if text:
        matches_iter = re.finditer(pattern, root['text']) if case_sensitive \
            else re.finditer(pattern, root['text'], re.IGNORECASE)
        for match in matches_iter:
            matches.append({'node_id': root['id'],
                            'span': match.span(),
                            'match': match.group()})
    if tags:
        # search for pattern in root['tags']
        pass
    for child in root['children']:
        matches += search(child, pattern, text, tags, case_sensitive, regex, filter_set, max_depth-1 if max_depth else None)
    return matches


def subtree_list(root, depth_limit=None):
    if depth_limit == 0:
        return []
    subtree = [root]
    for child in root['children']:
        subtree += subtree_list(child, depth_limit - 1 if depth_limit else None)
    return subtree

# {
#   root: {
#       text: ...
#       children: [
#           {
#               text: ...
#               children: ...
#           },
#       ]
#   }
#   generation_settings: {...}
# }
# Adds an ID field and a parent ID field to each dict in a recursive tree with "children"
def flatten_tree(d):
    if "id" not in d:
        d["id"] = str(uuid.uuid1())

    children = d.get("children", [])
    flat_children = []
    for child in children:
        child["parent_id"] = d["id"]
        flat_children.extend(flatten_tree(child))

    return [d, *flat_children]


def flatten_tree_revisit_parents(d, parent=None):
    if "id" not in d:
        d["id"] = str(uuid.uuid1())

    children = d.get("children", [])
    flat_children = []
    for child in children:
        child["parent_id"] = d["id"]
        flat_children.extend(flatten_tree_revisit_parents(child, d))

    return [d, *flat_children] if parent is None else [d, *flat_children, parent]


# Remove html and random double newlines from Miro
def fix_miro_tree(flat_data):
    # Otherwise it will randomly insert line breaks....
    h = html2text.HTML2Text()
    h.body_width = 0

    id_to_node = {d["id"]: d for d in flat_data}
    for d in flat_data:
        # Only fix miro text
        if "text" not in d or all([tag not in d["text"] for tag in ["<p>", "</p"]]):
            continue

        d["text"] = h.handle(d["text"])

        # p tags lead to double newlines
        d["text"] = d["text"].replace("\n\n", "\n")

        # Remove single leading and trailing newlines added by p tag wrappers
        if d["text"].startswith("\n"):
            d["text"] = d["text"][1:]
        if d["text"].endswith("\n"):
            d["text"] = d["text"][:-1]

        # No ending spaces, messes with generation
        d["text"] = d["text"].rstrip(" ")

        # If the text and its parent starts without a new line, it needs a space:
        if not d["text"].startswith("\n") and \
                ("parent_id" not in d or not id_to_node[d["parent_id"]]["text"].endswith("\n")):
            d["text"] = " " + d["text"]


