import os
import time
import traceback
from pprint import pprint

from celery import Celery
import openai
from util.util import retry, timestamp
import requests


# token data dictionary type
'''
{
    'generatedToken': {'logprob': float,
                       'token': string}
    'position': {'end': int, 'start': int}
    ? 'counterfactuals': [{'token': float)}]  

'''

# response dictionary type
'''
{
    "completions": [{'text': string
                     'tokens': [token_data]
                     'finishReason': string}]
    "prompt": {
                'text': string,
                ? 'tokens': [token_data]
              }
    "id": string
    "model": string
    "timestamp": timestamp
}
'''

POSSIBLE_MODELS = [
    'ada',
    'babbage',
    'content-filter-alpha-c4',
    'content-filter-dev',
    'curie',
    'cursing-filter-v6',
    'davinci',
    'instruct-curie-beta',
    'instruct-davinci-beta',
    'j1-large',
    'j1-jumbo',
]


def generate(**kwargs):
    if kwargs['model'] in ('j1-large', 'j1-jumbo'):
        response, error = ai21_generate(**kwargs)
        if not error:
            return format_ai21_response(response.json(), model=kwargs['model']), error
        else:
            return response, error
    else:
        # TODO OpenAI errors
        response, error = openAI_generate(**kwargs)
        return format_openAI_response(response, kwargs['prompt'], False), error

#################################
#   Janus
#################################

redis_url = os.environ.get("JANUS_REDIS", None)
app = Celery(
    # 'janus',
    broker=redis_url,
    backend=redis_url,
)


# get_gpt_response(prompt, memory, retry=True) -> result, error
janus_task = "janus.my_celery.tasks.get_gpt_response"


def janus_generate(prompt, memory=""):
    assert isinstance(prompt, str) and isinstance(memory, str)
    celery_task = app.send_task(janus_task, args=[prompt, memory])
    print("Sent to janus")
    result, error = celery_task.get()
    return result, error


#################################
#   OpenAI
#################################

openai.api_key = os.environ.get("OPENAI_API_KEY", None)

# pprint([d["id"] for d in openai.Engine.list()["data"]])


def openAI_token_position(token, text_offset, prompt):
    text_offset = text_offset - len(prompt)
    return {'start': text_offset,
            'end': text_offset + len(token)}


def format_openAI_completion(completion, prompt):
    completion_dict = {'text': completion['text'],
                       'finishReason': completion['finish_reason'],
                       'tokens': []}
    for i, token in enumerate(completion['logprobs']['tokens']):
        token_dict = {'generatedToken': {'token': token,
                                         'logprob': completion['logprobs']['token_logprobs'][i]},
                      'position': openAI_token_position(token, completion['logprobs']['text_offset'][i], prompt)}
        if completion['logprobs']['top_logprobs']:
            token_dict['counterfactuals'] = completion['logprobs']['top_logprobs'][i]
        completion_dict['tokens'].append(token_dict)
    return completion_dict


# TODO handle echo=True
def format_openAI_response(response, prompt, echo):
    response_dict = {}
    if echo:
        pass
    else:
        response_dict = {'completions': [format_openAI_completion(completion, prompt) for completion in response['choices']],
                         'prompt': {'text': prompt},
                         'id': response['id'],
                         'model': response['model'],
                         'timestamp': timestamp()}
    return response_dict


@retry(n_tries=3, delay=1, backoff=2, on_failure=lambda *args, **kwargs: "")
def openAI_generate(prompt, length=150, num_continuations=1, logprobs=10, temperature=0.8, top_p=1, stop=None,
                    model='davinci', **kwargs):

    response = openai.Completion.create(
        engine=model,
        prompt=prompt,
        temperature=temperature,
        max_tokens=length,
        top_p=top_p,
        logprobs=logprobs,
        n=num_continuations,
        stop=stop,
        **kwargs
    )
    return response, None


def search(query, documents, engine="curie"):
    return openai.Engine(engine).search(
        documents=documents,
        query=query
    )


#################################
#   AI21
#################################

ai21_api_key = os.environ.get("AI21_API_KEY", None)


def fix_ai21_tokens(token):
    return token.replace("▁", " ").replace("<|newline|>", "\n")


def format_ai21_token_data(token):
    token_dict = {'generatedToken': {'token': fix_ai21_tokens(token['generatedToken']['token']),
                                     'logprob': token['generatedToken']['logprob']},
                  'position': token['textRange']}
    if token['topTokens']:
        token_dict['counterfactuals'] = {fix_ai21_tokens(c['token']): c['logprob'] for c in token['topTokens']}
    return token_dict


def format_ai21_completion(completion):
    completion_dict = {'text': completion['data']['text'],
                       'tokens': [format_ai21_token_data(token) for token in completion['data']['tokens']],
                       'finishReason': completion['finishReason']['reason']}
    return completion_dict


def format_ai21_response(response, model):
    response_dict = {'completions': [format_ai21_completion(completion) for completion in response['completions']],
                     'prompt': {'text': response['prompt']['text'],
                                'tokens': [format_ai21_token_data(token) for token in response['prompt']['tokens']]},
                     'id': response['id'],
                     'model': model,
                     'timestamp': timestamp()}
    return response_dict


def ai21_generate(prompt, length=150, num_continuations=1, logprobs=10, temperature=0.8, top_p=1, stop=None,
                  engine='j1-large', **kwargs):
    stop = stop if stop else []
    request_json = {
        "prompt": prompt,
        "numResults": num_continuations,
        "maxTokens": length,
        "stopSequences": stop,
        "topKReturn": logprobs,
        "temperature": temperature,
        "topP": top_p,
    }
    try:
        response = requests.post(
            f"https://api.ai21.com/studio/v1/{engine}/complete",
            headers={"Authorization": f"Bearer {ai21_api_key}"},
            json=request_json,
        )
    except requests.exceptions.ConnectionError:
        return None, 'Connection error'
    error = None
    if response.status_code != 200:
        error = f'Bad status code {response.status_code}'
        print(request_json)
    return response, error





if __name__ == "__main__":
    pass

    #print(janus_generate("test"))
    # print(os.environ["OPENAI_API_KEY"])
    # print(api_generate("test"))
