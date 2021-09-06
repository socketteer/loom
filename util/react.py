def react_changes(old_components, new_components):
    # ids of added components
    added_ids = []
    # ids of deleted components
    deleted_ids = []
    # check for new components
    for new_id in new_components:
        if new_id not in old_components:
            added_ids.append(new_id)
    # check for deleted components
    for old_id in old_components:
        if old_id not in new_components:
            deleted_ids.append(old_id)
    return added_ids, deleted_ids


# for id in node_ids, check if the result of f(node_id) for f in functions
# has changed. Functions is dictionary of the form 
'''
{function_id: {f: lambda
                   cached_value: val}
                   }
'''
# returns a dictionary of the form
'''
{
    modified_node_id: { modified_function_id : new_val}
}
'''
def modifications(node_ids, functions):
    modified_nodes = {}
    for node_id in node_ids:
        for function_id in functions:
            new_val = functions[function_id]['f'](node_id)
            if new_val != functions[function_id]['cached_value']:
                modified_nodes[node_id] = {function_id: new_val}
                functions[function_id]['cached_value'] = new_val
    return modified_nodes
