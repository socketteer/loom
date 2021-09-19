import collections
import csv
import datetime
import functools
import itertools
import json
import logging
import os
import random
import string
import sys
import time
from functools import reduce, partial, wraps
import operator
from pprint import pprint
from random import shuffle
from util.gpt_util import tokenize_ada
import difflib
import re

import numpy as np
import pandas as pd


def init_logs(logfile=None, stdout=True):
    if logfile is None:
        logfile = f"logs/{timestamp()}.log"

    logging.basicConfig(filename=logfile,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    # Also log to stdout
    if stdout:
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def what_is_this_thing(thing):
    print(f"What is this thing? It's a {type(thing)}!")
    pprint(thing)


def print_array(arr, name="array"):
    print(f"Array {name}")
    print(f"\tShape: {arr.shape}, Max: {np.max(arr)}, Min: {np.min(arr)}")
    for line in np.array2string(arr).split("\n"):
        print(f"\t\t{line}")
    print()


################################################################################
# Strings
################################################################################


def datestamp():
    return datetime.date.today()


def timestamp():
    ts = time.time()
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d-%H.%M.%S')


def remove_whitespace(x):
    return x.translate(str.maketrans('', '', string.whitespace))


def split_text(text, d):
    if not text:
        return []
    word_list = text.split(d)
    if word_list[0] == '':
        token_list = []
    else:
        token_list = [word_list[0]]
    return token_list + [d+e for e in word_list[1:] if e]


# String class which can be formatted with brackets other than {}
class FString:
    def __init__(self, s, brackets="<>"):
        self.string = s
        self.brackets = brackets

    def remove_commented_lines(self, s):
        uncommented_lines = [line for line in s.split("\n") if not line.strip().startswith("#")]
        return "\n".join(uncommented_lines)

    # Replaces { with {{ and the FString bracket type with {
    # The string is ready to format with .format
    def switch_brackets(self, string):
        return string.replace("{", "{{") \
            .replace("}", "}}") \
            .replace(self.brackets[0], "{") \
            .replace(self.brackets[1], "}")

    def format(self, *args, **kwargs):
        return self.switch_brackets(self.remove_commented_lines(self.string)).format(*args, **kwargs)

    def __str__(self):
        return self.string.__str__()

    # Pass all undefined attribute requests to the underlying string
    # Composition >> Inheritance, at least because I'm afraid to override format
    def __getattr__(self, attr):
        return getattr(self.string, attr)


# https://stackoverflow.com/questions/13734451/string-split-with-indices-in-python
def split_indices(s):
    """Splits a string on whitespaces and records the indices of each in the original string.
    @:return generator((word, (start_idx, end_idx)), ...)
    """
    return ((m.group(0), (m.start(), m.end())) for m in re.finditer(r'\S+', s))
    

def word_ngrams(s, n):
    """Splits a string into ngram words"""
    tokens = s.split()  # not a generator :(
    ngram_seqs = form_ngrams(iter(tokens), n)
    return (" ".join(ngram) for ngram in ngram_seqs)


def word_ngrams_indices(s, n):
    """Splits a string into pairs of (ngram words, their start/end indices)"""
    tokens_with_indices = split_indices(s)

    # Generator of ngrams of (word, idx_pairs)
    # (
    #   [(word, (start,end)), (word, (start, end))...],
    #   [(word, (start, end)), ...],
    #   ...
    # )
    ngram_seqs_with_indices = form_ngrams(tokens_with_indices, n)

    # Generator of pairs of word and index ngrams
    # (
    #   ([word, word, ...], [(start,end), (start,end), ...]),
    #   ...
    # )
    ngram_indices_pairs = (zip(*ngram_with_indices) for ngram_with_indices in ngram_seqs_with_indices)

    # Generator of ( (word_ngram, (start, end)), (word_ngram, (start, end)), ...)
    return ((" ".join(ngram_seq), (indices[0][0], indices[-1][1])) for ngram_seq, indices in ngram_indices_pairs)


def diff(old, new):
    added = []
    removed = []
    added_index = 0
    removed_index = 0
    old_tokens, old_positions = old
    new_tokens, new_positions = new
    ndiff = difflib.ndiff(old_tokens, new_tokens)
    for i, s in enumerate(ndiff):
        word = s.split(' ')[-1]
        if s[0] == ' ':
            added_index += 1
            removed_index += 1
        elif s[0] == '-':
            removed.append({'word': s.split()[-1], 'indices': (old_positions[removed_index],
                                                               old_positions[removed_index] + len(word) + 1)})
            removed_index += 1
        elif s[0] == '+':
            added.append({'word': s.split()[-1], 'indices': (new_positions[added_index],
                                                             new_positions[added_index] + len(word) + 1)})
            added_index += 1
    # print('added:', added)
    # print('removed:', removed)
    return {'added': added, 'removed': removed, 'old': old, 'new': new}


# https://evandrocoan.github.io/debugtools/html/classdebug__tools_1_1utilities_1_1diffmatchpatch.html
def diff_linesToWords(text1, text2, delimiter=re.compile('\n')):
    """
        
        Split two texts into an array of strings.  Reduce the texts to a string
        of hashes where each Unicode character represents one line.

        95% of this function code is copied from `diff_linesToChars` on:
            https://github.com/google/diff-match-patch/blob/895a9512bbcee0ac5a8ffcee36062c8a79f5dcda/python3/diff_match_patch.py#L381

        Copyright 2018 The diff-match-patch Authors.
        https://github.com/google/diff-match-patch
        Licensed under the Apache License, Version 2.0 (the "License");
        you may not use this file except in compliance with the License.
        You may obtain a copy of the License at
        http://www.apache.org/licenses/LICENSE-2.0

        Args:
            text1: First string.
            text2: Second string.
            delimiter: a re.compile() expression for the word delimiter type

        Returns:
            Three element tuple, containing the encoded text1, the encoded text2 and
            the array of unique strings.  The zeroth element of the array of unique
            strings is intentionally blank.
    """
    lineArray = []  # e.g. lineArray[4] == "Hello\n"
    lineHash = {}   # e.g. lineHash["Hello\n"] == 4

    # "\x00" is a valid character, but various debuggers don't like it.
    # So we'll insert a junk entry to avoid generating a null character.
    lineArray.append('')

    def diff_linesToCharsMunge(text):
        """Split a text into an array of strings.  Reduce the texts to a string
        of hashes where each Unicode character represents one line.
        Modifies linearray and linehash through being a closure.
        Args:
            text: String to encode.
        Returns:
            Encoded string.
        """
        chars = []
        # Walk the text, pulling out a substring for each line.
        # text.split('\n') would would temporarily double our memory footprint.
        # Modifying text would create many large strings to garbage collect.
        lineStart = 0
        lineEnd = -1
        while lineEnd < len(text) - 1:
            lineEnd = delimiter.search(text, lineStart)

            if lineEnd:
                lineEnd = lineEnd.start()

            else:
                lineEnd = len(text) - 1

            line = text[lineStart:lineEnd + 1]

            if line in lineHash:
                chars.append(chr(lineHash[line]))
            else:
                if len(lineArray) == maxLines:
                    # Bail out at maxLines because unichr(maxLines+1) throws.
                    line = text[lineStart:]
                    lineEnd = len(text)
                lineArray.append(line)
                lineHash[line] = len(lineArray) - 1
                chars.append(chr(len(lineArray) - 1))
            lineStart = lineEnd + 1
        return "".join(chars)

    # Allocate 2/3rds of the space for text1, the rest for text2.
    maxLines = 666666
    chars1 = diff_linesToCharsMunge(text1)
    maxLines = 1114111
    chars2 = diff_linesToCharsMunge(text2)
    return (chars1, chars2, lineArray)

################################################################################
# I/O
################################################################################


def read_file(filename):
    with open(filename) as f:
        content = f.readlines()
        content = [x.strip() for x in content if x.strip()]
    return content


def csv_open(filename):
    with open(filename, encoding='utf-8') as f:
        reader = csv.reader(f)
        return list(reader)


def csv_create(filename, headers=None, rows=None):
    with open(filename, 'w') as f:
        writer = csv.writer(f)
        if headers:
            writer.writerow(headers)
        if rows:
            for row in rows:
                writer.writerow(row)


def csv_append_row(filename, row):
    with open(filename, 'a') as f:
        writer = csv.writer(f)
        writer.writerow(row)


# If headers is omitted, first col of the CSV is used
def csv_open_as_json(filename, headers=None):
    with open(filename, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, fieldnames=headers))


def json_open(filename):
    with open(filename) as f:
        return json.load(f)


def json_create(filename, data=None):
    data = data if data else []
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)


def json_append_dict(filename, data_dict):
    with open(filename) as f:
        old_json = json.load(f)
    old_json += [data_dict]
    json_create(filename, old_json)


def json_update_dict(filename, data_dict):
    with open(filename) as f:
        old_json = json.load(f)
    old_json.update(data_dict)
    json_create(filename, old_json)


def json_save_as_csv(filename, json_dicts):
    df = pd.DataFrame(json_dicts)
    df.to_csv(filename, index=False)


def merge_json_lists(directory):
    # Start with an opening bracket
    big_json_string = "["

    files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    for file in files:
        with open(file, 'r') as f:
            json_string = f.read()

            # Remove opening and closing bracket, add a comma
            json_string = json_string[1:-1] + ","
            # Add it to my big string
            big_json_string += json_string

    # Remove last comma and add end bracket
    big_json_string = big_json_string[:-1] + "]"
    return big_json_string


################################################################################
# Function decorators
################################################################################

# Adds a dictionary of metadata to a function so they can be accessed as global variables under func.meta["key"]
def metadata(func=None, **data):
    if not func:
        return functools.partial(metadata, **data)

    @functools.wraps(func)
    def f(*args, **kwargs):
        func.meta = {**data}
        return func(*args, **kwargs)

    f.meta = {**data}
    return f


def retry(func=None, exception=Exception, n_tries=5, delay=0.1,
          backoff=2, logger=True, on_failure=None):
    """Retry decorator with exponential backoff.
    https://stackoverflow.com/questions/42521549/retry-function-in-python

    Parameters
    ----------
    func : typing.Callable, optional
        Callable on which the decorator is applied, by default None
    exception : Exception or tuple of Exceptions, optional
        Exception(s) that invoke retry, by default Exception
    n_tries : int, optional
        Number of tries before giving up, by default 5
    delay : int, optional
        Initial delay between retries in seconds, by default 0.1
    backoff : int, optional
        Backoff multiplier e.g. value of 2 will double the delay, by default 1
    logger : bool, optional
        Option to log or print, by default True

    Returns
    -------
    typing.Callable
        Decorated callable that calls itself when exception(s) occur.

    Examples
    --------
    ... import random
    ... @retry(exception=Exception, n_tries=4)
    ... def test_random(text):
    ...    x = random.random()
    ...    if x < 0.5:
    ...        raise Exception("Fail")
    ...    else:
    ...        print("Success: ", text)
    ... test_random("It works!")
    """
    # Not sure why this is here
    if func is None:
        return partial(
            retry,
            exception=exception,
            n_tries=n_tries,
            delay=delay,
            backoff=backoff,
            logger=logger,
            on_failure=on_failure,
        )

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ntries, ndelay = n_tries, delay
        exe = None
        while ntries > 0:
            try:
                return func(*args, **kwargs)
            except exception as e:
                exe = e
                msg = f"Failed with exception: {str(e)}, Retrying in {ndelay} seconds..."
                if logger:
                    logging.warning(msg)
                else:
                    print(msg)
                time.sleep(ndelay)
                ntries -= 1
                ndelay *= backoff

        if on_failure is not None:
            on_failure(*args, **kwargs)
        else:
            raise exe

    return wrapper


def log(func, logger=logging.info):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger(f"Calling function {f.__name__}\n\twith args: {args}\n\tkwargs: {kwargs}")
        returned = func(*args, **kwargs)
        logger(f"Function {f.__name__} succeeded. Returned: {returned}")
        return returned

    return wrapper


################################################################################
# Data structures
################################################################################


# Clips a number between lower and upper bound, inclusive
def clip_num(n, lower, upper):
    return max(lower, min(n, upper))


# Clips an index to the size of the array
def index_clip(arr, i):
    return arr[clip_num(i, 0, len(arr)-1)]


# Deduplicate a list without losing order
def dedupe(l):
    seen = set()
    return [e for e in l if not (e in seen or seen.add(e))]


def shuffle_and_concat(lists):
    for sublist in lists:
        shuffle(sublist)
    return [item for sublist in lists for item in sublist]


# Break a list into parts of a given size, allowing the last element to be shorter
def grouper(iterable, size):
    # "grouper(3, 'ABCDEFG') --> [ABC, DEF, G]"
    it = iter(iterable)
    while True:
        group = tuple(itertools.islice(it, None, size))
        if not group:
            break
        yield group


# Add an item between each element of a list
# intersperse([1, 2, 3], '-') = [1, '-', 2, '-', 3]
def intersperse(lst, item):
    result = [item] * (len(lst) * 2 - 1)
    result[0::2] = lst
    return result


# Implementation from nltk source
# https://www.nltk.org/_modules/nltk/util.html
def form_ngrams(sequence, n):
    """Return the ngrams generated from a sequence of items, as an iterator. For example:
        list(form_ngrams([1,2,3,4,5], 3))  =>  [(1, 2, 3), (2, 3, 4), (3, 4, 5)]
    """

    history = []
    while n > 1:
        # PEP 479, prevent RuntimeError from being raised when StopIteration bubbles out of generator
        try:
            next_item = next(sequence)
        except StopIteration:
            # no more data, terminate the generator
            return
        history.append(next_item)
        n -= 1
    for item in sequence:
        history.append(item)
        yield tuple(history)
        del history[0]


# Apply a function recursively to all elements in nested lists. Doesn't work for numpy arrays...? :'(
def recursive_map(func, li, on_elements=True, on_list=False):
    if isinstance(li, collections.abc.Sequence) or (isinstance(li, np.ndarray)):
        # Self containing lists... Just give up. No map is worth that recursion.
        if not li in li:
            li = list(map(lambda x: recursive_map(func, x, on_elements, on_list), li))
        return func(li) if on_list else li
    else:
        return func(li) if on_elements else li


# Turn nested lists or numpy arrays into tuples.
# Useful for preparing lists for printing or making them immutable for caching
def tuplify(l):
    return recursive_map(tuple, l, on_elements=False, on_list=True)


# Tuplify and round to n digits. Useful for display
def tupliround(li, num_digits=3):
    return tuplify(recursive_map(lambda x: round(x, num_digits), li))


# Given a dictionary which contains lists, find the longest length L
# Unroll all lists with len(L), creating a list of len(L) of dictionaries with the same
# key:value pairs, but a single value for each key which contained a list of len(L).
# Add a key __index to each dictionary corresponding to its place in the list
# This allows you to create param dicts which interpolate over multiple keys at the same time
#
# E.g. unroll_dict({
#   param1 = True,
#   param2 = [a, b, c],
#   param3 = [d, e, f],
#   param4 = [g, h]
# }) == [
#    {param1=True, param2=a, param3=d, param4=[g, h]}
#    {param1=True, param2=b, param3=e, param4=[g, h]}
#    {param1=True, param2=c, param3=f, param4=[g, h]}
#  ]
def unroll_dict(dict_of_lists):
    # Find longest list in dict
    longest_len = 0
    for key, value in dict_of_lists.items():
        try:
            longest_len = max(longest_len, len(value))
        except Exception:
            pass

    # Make a list of dicts, unrolling the longest key lists
    list_of_dicts = []
    for i in range(longest_len):
        d = {}
        for key, value in dict_of_lists.items():
            try:
                if len(value) == longest_len:
                    d[key] = value[i]
                    continue
            except Exception:
                pass
            d[key] = value
        d["__index"] = i
        list_of_dicts.append(d)

    return list_of_dicts


