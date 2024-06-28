import openai
import numpy as np
from util.tokenizer import tokenize, token_to_word
from util.gpt_util import logprobs_to_probs, get_correct_key
import os


def generate(prompt, engine, api_base, api_key):
    openai.base_url, openai.api_key = api_base + '/', api_key
    #print('calling engine', engine, 'at endpoint', openai.api_base)
    #print('prompt:', prompt)
    response = openai.completions.create(prompt=prompt,
                                        max_tokens=1,
                                        n=1,
                                        temperature=0,
                                        logprobs=100,
                                        model=engine).dict()
    return response

# TODO multiple "ground truth" trajectories
def greedy_word_multiverse(prompt, ground_truth='', max_depth=3,  unnormalized_amplitude=1, unnormalized_threshold=0.1,
                           engine='davinci-002', model_type='openai', api_base=None):
    if isinstance(ground_truth, str):
        ground_truth = tokenize(ground_truth)
        ground_truth = [token_to_word(token).replace('Ġ', ' ') for token in ground_truth]
    if max_depth == 0:
        return {}, ground_truth
    api_key, _ = get_correct_key(model_type)
    response = generate(prompt, engine, api_base, api_key)
    logprobs = response['choices'][0]["logprobs"]["top_logprobs"][0]
    probs = {k: logprobs_to_probs(v) for k, v in sorted(logprobs.items(), key=lambda item: item[1], reverse=True)}
    multiverse = {token: {'normalized_prob': prob, 'unnormalized_prob': prob * unnormalized_amplitude, 'children': {}} for token, prob in probs.items()}
    ground_truth_token = ground_truth[0] if ground_truth else 'NO GROUND TRUTH'
    done_ground_truth = False
    for token in multiverse.items():
        if token[1]['unnormalized_prob'] > unnormalized_threshold:
            token[1]['children'], _ = greedy_word_multiverse(prompt + token[0], ground_truth='', max_depth=max_depth-1,
                                                             unnormalized_threshold=unnormalized_threshold,
                                                             unnormalized_amplitude=token[1]['unnormalized_prob'],
                                                             engine=engine,
                                                             api_base=api_base)
        elif token[0] == ground_truth_token:
            token[1]['children'], _ = greedy_word_multiverse(prompt + token[0], ground_truth=ground_truth[1:],
                                                             max_depth=max_depth-1,
                                                             unnormalized_threshold=unnormalized_threshold,
                                                             unnormalized_amplitude=token[1]['unnormalized_prob'],
                                                             engine=engine,
                                                             api_base=api_base)


            done_ground_truth = True
        else:
            break
    if not done_ground_truth:
        if ground_truth_token in multiverse:
            multiverse[ground_truth_token]['children'], _ = greedy_word_multiverse(prompt + ground_truth_token,
                                                                                   ground_truth=ground_truth[1:],
                                                                                   max_depth=max_depth-1,
                                                                                   unnormalized_threshold=unnormalized_threshold,
                                                                                   unnormalized_amplitude=multiverse[ground_truth_token]['unnormalized_prob'],
                                                                                   engine=engine,
                                                                                   api_base=api_base,
                                                                                   api_key=api_key)
    return multiverse, ground_truth


