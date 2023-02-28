import json
import os

import openai
import requests
from celery import Celery

from loom.utils.gpt_util import parse_logit_bias, parse_stop
from loom.utils.util import retry, timestamp

# response dictionary type
"""
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
"""

# token data dictionary type
"""
{
    'generatedToken': {'logprob': float,
                       'token': string}
    'position': {'end': int, 'start': int}
    ? 'counterfactuals': [{'token': float)}]
}
"""

# finishReason
"""
"finishReason": {"reason": "stop" | "length",
                 ? "sequence": string }
"""

POSSIBLE_MODELS = [
    "ada",
    "babbage",
    "content-filter-alpha-c4",
    "content-filter-dev",
    "curie",
    "cursing-filter-v6",
    "davinci",
    "instruct-curie-beta",
    "instruct-davinci-beta",
    "j1-large",
    "j1-jumbo",
]


def gen(prompt, settings, config, **kwargs):
    if settings["stop"]:
        stop = parse_stop(settings["stop"])
    else:
        stop = None
    if settings["logit_bias"]:
        logit_bias = parse_logit_bias(settings["logit_bias"])
    else:
        logit_bias = None
    model_info = config["models"][settings["model"]]
    ai21_api_key = kwargs.get("AI21_API_KEY", None)
    ai21_api_key = ai21_api_key if ai21_api_key else os.environ.get("AI21_API_KEY", None)

    if model_info["type"] == "gooseai":
        openai.api_base = "https://api.goose.ai/v1"
        gooseai_api_key = kwargs.get("GOOSEAI_API_KEY", None)
        openai.api_key = gooseai_api_key if gooseai_api_key else os.environ.get("GOOSEAI_API_KEY", None)
    elif model_info["type"] == "openai":
        openai.api_base = "https://api.openai.com/v1"
        openai_api_key = kwargs.get("OPENAI_API_KEY", None)
        openai.api_key = openai_api_key if openai_api_key else os.environ.get("OPENAI_API_KEY", None)

    response, error = generate(
        prompt=prompt,
        length=settings["response_length"],
        num_continuations=settings["num_continuations"],
        temperature=settings["temperature"],
        logprobs=settings["logprobs"],
        top_p=settings["top_p"],
        model=settings["model"],
        stop=stop,
        logit_bias=logit_bias,
        config=config,
        ai21_api_key=ai21_api_key,
    )
    return response, error


def generate(config, **kwargs):
    model_type = config["models"][kwargs["model"]]["type"]
    if model_type == "ai21":
        response, error = ai21_generate(api_key=kwargs["ai21_api_key"], **kwargs)
        if not error:
            formatted_response = format_ai21_response(response.json(), model=kwargs["model"])
            return formatted_response, error
        else:
            return response, error
    elif model_type in ("openai", "openai-custom", "gooseai"):
        response, error = openAI_generate(custom=model_type == "openai-custom", **kwargs)
        formatted_response = format_openAI_response(response, kwargs["prompt"], echo=True)
        return formatted_response, error


def completions_text(response):
    return [completion["text"] for completion in response["completions"]]


def save_response_json(response, filename):
    with open(filename, "w") as f:
        json.dump(response, f)


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
def openAI_token_position(token, text_offset):
    return {"start": text_offset, "end": text_offset + len(token)}


def format_openAI_token_dict(completion, token, i):
    token_dict = {
        "generatedToken": {"token": token, "logprob": completion["logprobs"]["token_logprobs"][i]},
        "position": openAI_token_position(token, completion["logprobs"]["text_offset"][i]),
    }

    if completion["logprobs"].get("top_logprobs", None) is not None and completion["logprobs"]["top_logprobs"]:
        openai_counterfactuals = completion["logprobs"]["top_logprobs"][i]
        if openai_counterfactuals:
            sorted_counterfactuals = {
                k: v for k, v in sorted(openai_counterfactuals.items(), key=lambda item: item[1], reverse=True)
            }
            token_dict["counterfactuals"] = sorted_counterfactuals
    else:
        token_dict["counterfactuals"] = None
    return token_dict


def format_openAI_completion(completion, prompt, prompt_end_index):
    completion_dict = {
        "text": completion["text"][len(prompt) :],
        "finishReason": completion["finish_reason"],
        "tokens": [],
    }
    for i, token in enumerate(completion["logprobs"]["tokens"][prompt_end_index:]):
        j = i + prompt_end_index
        token_dict = format_openAI_token_dict(completion, token, j)
        completion_dict["tokens"].append(token_dict)
    return completion_dict


def format_openAI_prompt(completion, prompt):
    prompt_dict = {"text": prompt, "tokens": []}
    # loop over tokens until offset >= prompt length
    for i, token in enumerate(completion["logprobs"]["tokens"]):
        if completion["logprobs"]["text_offset"][i] >= len(prompt):
            prompt_end_index = i
            break
        token_dict = format_openAI_token_dict(completion, token, i)
        prompt_dict["tokens"].append(token_dict)

    return prompt_dict, prompt_end_index


def format_openAI_response(response, prompt, echo=True):
    if echo:
        prompt_dict, prompt_end_index = format_openAI_prompt(response["choices"][0], prompt)
    else:
        prompt_dict = {"text": prompt, "tokens": None}
        prompt_end_index = 0
        # prompt = ''

    response_dict = {
        "completions": [
            format_openAI_completion(completion, prompt, prompt_end_index) for completion in response["choices"]
        ],
        "prompt": prompt_dict,
        "id": response["id"],
        "model": response["model"],
        "timestamp": timestamp(),
    }
    return response_dict


@retry(n_tries=3, delay=1, backoff=2, on_failure=lambda *args, **kwargs: ("", None))
def openAI_generate(
    prompt,
    length=150,
    num_continuations=1,
    logprobs=10,
    temperature=0.8,
    top_p=1,
    stop=None,
    model="davinci",
    logit_bias=None,
    custom=False,
    **_,
):
    if not logit_bias:
        logit_bias = {}
    params = {
        "prompt": prompt,
        "temperature": temperature,
        "max_tokens": length,
        "top_p": top_p,
        "echo": True,
        "logprobs": logprobs,
        "logit_bias": logit_bias,
        "n": num_continuations,
        "stop": stop,
    }
    if custom:
        params["model"] = model
    else:
        params["engine"] = model
    response = openai.Completion.create(**params)

    return response, None


def search(query, documents, engine="curie"):
    return openai.Engine(engine).search(documents=documents, query=query)


#################################
#   AI21
#################################
def fix_ai21_tokens(token):
    return token.replace("▁", " ").replace("<|newline|>", "\n")


def ai21_token_position(textRange, text_offset):
    return {"start": textRange["start"] + text_offset, "end": textRange["end"] + text_offset}


def format_ai21_token_data(token, prompt_offset=0):
    token_dict = {
        "generatedToken": {
            "token": fix_ai21_tokens(token["generatedToken"]["token"]),
            "logprob": token["generatedToken"]["logprob"],
        },
        "position": ai21_token_position(token["textRange"], prompt_offset),
    }
    if token["topTokens"]:
        token_dict["counterfactuals"] = {fix_ai21_tokens(c["token"]): c["logprob"] for c in token["topTokens"]}
    else:
        token_dict["counterfactuals"] = None
    return token_dict


def format_ai21_completion(completion, prompt_offset=0):
    completion_dict = {
        "text": completion["data"]["text"],
        "tokens": [format_ai21_token_data(token, prompt_offset) for token in completion["data"]["tokens"]],
        "finishReason": completion["finishReason"]["reason"],
    }
    return completion_dict


def format_ai21_response(response, model):
    prompt = response["prompt"]["text"]
    response_dict = {
        "completions": [
            format_ai21_completion(completion, prompt_offset=len(prompt)) for completion in response["completions"]
        ],
        "prompt": {
            "text": prompt,
            "tokens": [format_ai21_token_data(token, prompt_offset=0) for token in response["prompt"]["tokens"]],
        },
        "id": response["id"],
        "model": model,
        "timestamp": timestamp(),
    }
    return response_dict


def ai21_generate(
    prompt,
    length=150,
    num_continuations=1,
    logprobs=10,
    temperature=0.8,
    top_p=1,
    stop=None,
    engine="j1-large",
    api_key=None,
    **_,
):
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
            headers={"Authorization": f"Bearer {api_key}"},
            json=request_json,
        )
    except requests.exceptions.ConnectionError:
        return None, "Connection error"
    error = None
    if response.status_code != 200:
        error = f"Bad status code {response.status_code}"
        print(request_json)
    return response, error


if __name__ == "__main__":
    pass
