import openai
import numpy as np
import math


def normalize(probs):
    return [float(i) / sum(probs) for i in probs]


def logprobs_to_probs(probs):
    if isinstance(probs, list):
        return [math.exp(x) for x in probs]
    else:
        return math.exp(probs)


def dict_logprobs_to_probs(prob_dict):
    return {key: math.exp(prob_dict[key]) for key in prob_dict.keys()}


def total_logprob(response):
    logprobs = response['logprobs']['token_logprobs']
    logprobs = [i for i in logprobs if not math.isnan(i)]
    return sum(logprobs)


def tokenize_ada(prompt):
    response = openai.Completion.create(
        engine='ada',
        prompt=prompt,
        max_tokens=0,
        echo=True,
        n=1,
        logprobs=0
    )
    tokens = response.choices[0]["logprobs"]["tokens"]
    positions = response.choices[0]["logprobs"]["text_offset"]
    return tokens, positions


# evaluates logL(prompt+target | prompt)
def conditional_logprob(prompt, target, engine='ada'):
    combined = prompt + target
    response = openai.Completion.create(
        engine=engine,
        prompt=combined,
        max_tokens=0,
        echo=True,
        n=1,
        logprobs=0
    )
    positions = response.choices[0]["logprobs"]["text_offset"]
    logprobs = response.choices[0]["logprobs"]["token_logprobs"]
    word_index = positions.index(len(prompt))
    total_conditional_logprob = sum(logprobs[word_index:])
    return total_conditional_logprob





# TODO use threading
# returns the conditional probabilities for each event happening after prompt
def event_probs(prompt, events, engine='ada'):
    probs = []
    for event in events:
        logprob = conditional_logprob(prompt, event, engine)
        probs.append(logprobs_to_probs(logprob))

    normal_probs = normalize(probs)
    return probs, normal_probs


# like event_probs, returns conditional probabilities (normalized & unnormalized) for each token occurring after prompt
def token_probs(prompt, tokens, engine='ada'):
    pass


# returns a list of positions and counterfactual probability of token at position
# if token is not in top_logprobs, probability is treated as 0
# all positions if actual_token=None, else only positions where the actual token in response is actual_token
# TODO next sequence instead of next token
def counterfactual(response, token, actual_token=None, next_token=None, sort=True):
    counterfactual_probs = []
    tokens = response.choices[0]['logprobs']['tokens']
    top_logprobs = response.choices[0]['logprobs']['top_logprobs']
    positions = response.choices[0]['logprobs']['text_offset']
    for i, probs in enumerate(top_logprobs):
        if (actual_token is None and next_token is None) \
                or actual_token == tokens[i] \
                or (i < len(tokens) - 1 and next_token == tokens[i+1]):
            if token in probs:
                counterfactual_probs.append({'position': positions[i+1],
                                             'prob': logprobs_to_probs(probs[token])})
            else:
                counterfactual_probs.append({'position': positions[i+1], 'prob': 0})
    if sort:
        counterfactual_probs = sorted(counterfactual_probs, key=lambda k: k['prob'])
    return counterfactual_probs


# returns a list of substrings of content and
# logL(preprompt+substring+target | preprompt+substring) for each substring
def substring_probs(preprompt, content, target, engine='ada', quiet=0):
    logprobs = []
    substrings = []
    _, positions = tokenize_ada(content)
    for position in positions:
        substring = content[:position]
        prompt = preprompt + substring
        logprob = conditional_logprob(prompt, target, engine)
        logprobs.append(logprob)
        substrings.append(substring)
        if not quiet:
            print(substring)
            print('logprob: ', logprob)

    return substrings, logprobs


# returns a list of substrings of content
# logL(substring+target | substring) for each substring
def token_conditional_logprob(content, target, engine='ada'):
    response = openai.Completion.create(
        engine=engine,
        prompt=content,
        max_tokens=0,
        echo=True,
        n=1,
        logprobs=100
    )
    tokens = response.choices[0]['logprobs']['tokens']
    top_logprobs = response.choices[0]['logprobs']['top_logprobs']
    logprobs = []
    substrings = []
    substring = ''
    for i, probs in enumerate(top_logprobs):
        substrings.append(substring)
        if target in probs:
            logprobs.append(probs[target])
        else:
            logprobs.append(None)
        substring += tokens[i]
    return substrings, logprobs



def sort_logprobs(substrings, logprobs, n_top=None):
    sorted_indices = np.argsort(logprobs)
    top = []
    if n_top is None:
        n_top = len(sorted_indices)
    for i in range(n_top):
        top.append({'substring': substrings[sorted_indices[-(i + 1)]],
                    'logprob': logprobs[sorted_indices[-(i + 1)]]})
    return top


def top_logprobs(preprompt, content, target, n_top=None, engine='ada', quiet=0):
    substrings, logprobs = substring_probs(preprompt, content, target, engine, quiet)
    return sort_logprobs(substrings, logprobs, n_top)


def decibels(prior, evidence, target, engine='ada'):
    prior_target_logprob = conditional_logprob(prompt=prior, target=target, engine=engine)
    evidence_target_logprob = conditional_logprob(prompt=evidence, target=target, engine=engine)
    return (evidence_target_logprob - prior_target_logprob), prior_target_logprob, evidence_target_logprob
