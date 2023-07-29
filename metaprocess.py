import openai
import os
import json
from util.gpt_util import logprobs_to_probs



def metaprocess(input, input_transform, prompt_template, model_call, output_transform):
    # print(f"Input: '{input}'\n")
    transformed_input = input_transform(input)
    # print(f"Transformed input: '{transformed_input}'\n")
    prompt = prompt_template(transformed_input)
    # print(f"Prompt: '{prompt}'\n")
    output = model_call(prompt)
    # print(f"Output: '{output}'\n")
    transformed_output = output_transform(output)
    # print(f"Transformed output: '{transformed_output}'")
    return transformed_output

def call_model(prompt, engine="ada", n=1, temperature=1, max_tokens=20, logprobs=0, stop=None):
    openai.api_key = os.environ.get("OPENAI_API_KEY", None)
    response = openai.Completion.create(
        engine=engine,
        prompt=prompt,
        n=n,
        temperature=temperature,
        max_tokens=max_tokens,
        logprobs=logprobs,
        stop=stop
    )
    return response

def get_completion_text(response):
    return response.choices[0].text

def get_completion_branches(response):
    # returns an array of text of completion branches
    return [choice.text for choice in response.choices]

def get_judgement_probability(response, yes_tokens=["Yes", "yes", "Y", "y", " Yes", " yes", " Y", " y"], no_tokens=["No", "no", "N", "n", " No", " no", " N", " n"]):
    # gets the probability of the first token of the response being a yes or no
    logprobs = response.choices[0]['logprobs']['top_logprobs'][0]
    yes_tokens = [token for token in yes_tokens if token in logprobs]
    no_tokens = [token for token in no_tokens if token in logprobs]
    yes_probability = sum([logprobs_to_probs(logprobs.get(token, 0)) for token in yes_tokens])
    no_probability = sum([logprobs_to_probs(logprobs.get(token, 0)) for token in no_tokens])
    return yes_probability / (yes_probability + no_probability)


def author_attribution(input):
    return metaprocess(
        input,
        input_transform=lambda x: x,
        prompt_template=lambda x: f"Text: '{x}'\nAuthor:",
        model_call=lambda x: call_model(x, engine='davinci', n=3),
        output_transform=lambda x: get_completion_branches(x)
    )

def detect_swearing(input):
    return metaprocess(
        input,
        input_transform=lambda x: x,
        prompt_template=lambda x: f"Text: '{x}'\nContains swearing? (Yes/No):",
        model_call=lambda x: call_model(x, engine='davinci', max_tokens=1, logprobs=10),
        output_transform=lambda x: get_judgement_probability(x)
    )

metaprocesses = {
    "author_attribution": author_attribution,
    "detect_swearing": detect_swearing
}

# load metaprocesses from files
for filename in os.listdir("./data/metaprocesses"):
    if filename.endswith(".json"):
        with open(f"./data/metaprocesses/{filename}", "r") as f:
            data = json.load(f)
        metaprocesses[data["name"]] = lambda x : metaprocess(
            x,
            input_transform=eval(data["input_transform"]),
            prompt_template=eval(data["prompt_template"]),
            model_call=eval(data["model_call"]),
            output_transform=eval(data["output_transform"])
        )
