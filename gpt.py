import os
import time
import traceback
from pprint import pprint

from celery import Celery
import openai
from util.util import retry

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
POSSIBLE_MODELS = [
    'ada',
    'babbage',
    'content-filter-alpha-c4',
    'content-filter-dev',
    'curie',
    'cursing-filter-v6',
    'davinci',
    'instruct-curie-beta',
    'instruct-davinci-beta'
]


@retry(n_tries=3, delay=1, backoff=2, on_failure=lambda *args, **kwargs: "")
def api_generate(prompt, length=150, num_continuations=1, logprobs=10, temperature=0.8, top_p=1, stop=None, engine='davinci', **kwargs):

    response = openai.Completion.create(
        engine=engine,
        prompt=prompt,
        temperature=temperature,
        max_tokens=length,
        top_p=top_p,
        logprobs=logprobs,
        n=num_continuations,
        stop=stop,
        **kwargs
    )
    # for choice in response.choices:
    #     print(choice['logprobs'])
    return response, None


def search(query, documents, engine="curie"):
    return openai.Engine(engine).search(
        documents=documents,
        query=query
    )


if __name__ == "__main__":
    pass

    print(janus_generate("test"))
    # print(os.environ["OPENAI_API_KEY"])
    # print(api_generate("test"))
