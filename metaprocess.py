import openai
import os
import json
from util.gpt_util import logprobs_to_probs



def metaprocess(input, aux_input, input_transform, prompt_template, generation_settings, output_transform):
    # print(f"Input: '{input}'\n")
    transformed_input = input_transform(input)
    # print(f"Transformed input: '{transformed_input}'\n")
    prompt = prompt_template(transformed_input, aux_input)
    # print(f"Prompt: '{prompt}'\n")
    # output = model_call(prompt)
    output = call_model(prompt, **generation_settings)
    # print(f"Output: '{output}'\n")
    transformed_output = output_transform(output)
    # print(f"Transformed output: '{transformed_output}'")
    process_log = {
        "input": input,
        "transformed_input": transformed_input,
        "prompt": prompt,
        "output": output,
        "transformed_output": transformed_output
    }
    return transformed_output, process_log

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


metaprocesses = {
    # "author_attribution": author_attribution,
    #"detect_swearing": detect_swearing
}


# load metaprocesses from files
for filename in os.listdir("./config/metaprocesses"):
    if filename.endswith(".json"):
        with open(f"./config/metaprocesses/{filename}", "r") as f:
            data = json.load(f)
        name = filename.split(".")[0]
        metaprocesses[name] = {
            "description": data["description"],
            "input_transform": data["input_transform"],
            "prompt_template": data["prompt_template"],
            "output_transform": data["output_transform"],
            "generation_settings": data["generation_settings"],
            "output_type": data["output_type"]
        }

def save_metaprocess(metaprocess_name, data):
    with open(f"./config/metaprocesses/{metaprocess_name}.json", "w") as f:
        json.dump(data, f, indent=4)

def execute_metaprocess(metaprocess_name, input, aux_input=None):
    # print("Executing metaprocess", metaprocess_name, "with input", input, "and aux input", aux_input)
    metaprocess_data = metaprocesses[metaprocess_name]
    return metaprocess(
        input,
        aux_input,
        input_transform=eval(metaprocess_data["input_transform"]),
        prompt_template=eval(metaprocess_data["prompt_template"]),
        generation_settings=metaprocess_data["generation_settings"],
        output_transform=eval(metaprocess_data["output_transform"])
    )
