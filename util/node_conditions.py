from util.util_tree import in_ancestry
from datetime import datetime

conditions = {}
def condition(name):
    def wrapper(fn):
        conditions[name] = fn
        return fn
    return wrapper


@condition("canonical")
def node_is_canonical(node, **kwargs):
    return node['id'] in kwargs['calc_canonical_set']()


@condition("descendent of")
def descendent_of(ancestor_id, node, **kwargs):
    tree_node_dict = kwargs['tree_node_dict']
    ancestor = tree_node_dict[ancestor_id]
    return in_ancestry(ancestor, node, tree_node_dict)


@condition("ancestor of")
def ancestor_of(node, descendent_id, **kwargs):
    tree_node_dict = kwargs['tree_node_dict']
    descendent = tree_node_dict[descendent_id]
    return in_ancestry(node, descendent, tree_node_dict)


@condition("created on or after")
def created_on_after(node, time, **kwargs):
    node_timestamp = node['meta']['creation_timestamp']
    return time < datetime.strptime(node_timestamp, '%Y-%m-%d-%H.%M.%S')


@condition("created before")
def created_before(node, time, **kwargs):
    node_timestamp = node['meta']['creation_timestamp']
    return time >= datetime.strptime(node_timestamp, '%Y-%m-%d-%H.%M.%S')


@condition("test")
def test_condition(a, b, node, **kwargs):
    return a == b
