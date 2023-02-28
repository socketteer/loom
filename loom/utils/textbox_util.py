import bisect
import re

from diff_match_patch import diff_match_patch

from loom.utils.util_tree import ancestor_text_end_indices, ancestor_text_start_indices


# given a textbox index, returns the index of the ancestor node that contains it,
# and the index of the text within that node
def textbox_index_to_node(textbox_index, ancestry):
    ancestor_end_indices = ancestor_text_end_indices(ancestry)
    ancestor_start_indices = ancestor_text_start_indices(ancestry)
    # print("textbox_index: ", textbox_index)
    # print("ancestor_end_indices: ", ancestor_end_indices)
    # print("ancestor_start_indices: ", ancestor_start_indices)
    # ancestor_index = bisect.bisect_left(ancestor_end_indices, textbox_index)
    ancestor_index = bisect.bisect_right(ancestor_start_indices, textbox_index) - 1
    # print("ancestor_index: ", ancestor_index)
    ancestor_text_index = textbox_index - ancestor_end_indices[ancestor_index - 1]
    return ancestor_index, ancestor_text_index


# given node ancestry and index of text in last node, returns the index of the
# text in textbox
def node_to_textbox_index(node_text_index, ancestry):
    ancestor_end_indices = ancestor_text_end_indices(ancestry)
    textbox_index = ancestor_end_indices[-1] + node_text_index
    return textbox_index


def apply_diff(old_text, position, diff):
    if diff[0] == 1:
        # insertion
        return old_text[:position] + diff[1] + old_text[position:]
    elif diff[0] == -1:
        # deletion
        return old_text[: position - len(diff[1])] + old_text[position:]


# given a new textbox state and node ancestry, computes changes to nodes in ancestry
# and returns a list of modified ancestors
def distribute_textbox_changes(new_text, ancestry):
    old_text = "".join([ancestor["text"] for ancestor in ancestry])
    if old_text == new_text:
        return []
    dmp = diff_match_patch()
    diffs = dmp.diff_main(old_text, new_text)
    # a = diff_linesToWords(old_text, new_text, delimiter=re.compile(' '))
    # diffs = dmp.diff_main(a[0], a[1], False)
    # dmp.diff_charsToLines(diffs, a[2])
    # print([ancestor['text'] for ancestor in ancestry])
    # print('old text: ', old_text)
    # print('new text: ', new_text)
    diff_pos = 0
    changed_ancestor_ids = []
    for d in diffs:
        # print(changed_ancestor_ids)
        # print(d)
        if d[0] == 0:
            diff_pos += len(d[1])
        else:
            diff_start = diff_pos
            diff_end = diff_pos + len(d[1])
            node_index_start, text_index_start = textbox_index_to_node(diff_start, ancestry)
            node_index_end, text_index_end = textbox_index_to_node(diff_end, ancestry)

            if node_index_start != node_index_end and d[0] == -1:
                # deletion spanning multiple nodes
                old_text_start = ancestry[node_index_start]["text"]
                old_text_end = ancestry[node_index_end]["text"]
                new_text_start = old_text_start[:text_index_start]
                new_text_end = old_text_end[-text_index_end:]
                ancestry[node_index_start]["text"] = new_text_start
                ancestry[node_index_end]["text"] = new_text_end
                changed_ancestor_ids.append(ancestry[node_index_start]["id"])
                changed_ancestor_ids.append(ancestry[node_index_end]["id"])

                # if there are any nodes in between, set their text to empty
                for i in range(node_index_start + 1, node_index_end):
                    ancestry[i]["text"] = ""
                    changed_ancestor_ids.append(ancestry[i]["id"])

            else:
                node_index, text_index = (
                    (node_index_start, text_index_start) if d[0] == 1 else (node_index_end, text_index_end)
                )
                # apply changes off the end of textbox to last node
                node_index = node_index if node_index < len(ancestry) else len(ancestry) - 1
                # print('changed node index: ', node_index)
                old_node_text = ancestry[node_index]["text"]
                new_node_text = apply_diff(old_node_text, text_index, d)
                ancestry[node_index]["text"] = new_node_text
                changed_ancestor_ids.append(ancestry[node_index]["id"])

            diff_pos = diff_end if d[0] == 1 else diff_start

    # print('new ancestry:', [ancestor['text'] for ancestor in ancestry])
    # print('changed ids:', changed_ancestor_ids)
    changed_ancestors = [ancestor for ancestor in ancestry if ancestor["id"] in changed_ancestor_ids]
    # print('changed ancestors:', [ancestor['text'] for ancestor in changed_ancestors])
    return changed_ancestors
