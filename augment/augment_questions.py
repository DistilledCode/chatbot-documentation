import json
import pickle
import requests
import re
import concurrent.futures
from time import perf_counter
from datetime import datetime
from keras_nlp import models
from pathlib import Path


dirp = Path("../processed_data")
dirp.mkdir(parents=True, exist_ok=True)

tokenizer = models.MistralTokenizer.from_preset("mistral_7b_en")


CATEGORY = "criminal-law"
MAX_QUERY_LENGTH = 2200

"""
./server -m ../.data/model/others/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
-t 12 \
-c 26000 \
-ngl 33 \
-cb \
-n 2100 \
--port 8080 \
--host :: \
-np 6 \
--threads-http 12
"""

prompt = """
Your task is to pharaphrase the give legal query into first person perspective.

The query:
* should *ONLY* be in first person perspective.
* should sound *organic* and *natural*.
* Donot start the query with "As a.."
* *DONOT* use the names mentioned in the text.
* Dont always start the query with "I"
* Only output the query and nothing else
"""

q = "\n## PARAPHRASED QUERY: "

mlen = len(tokenizer(prompt))



headersList = {
    "Accept": "*/*",
    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
    "Content-Type": "application/json",
}


questions = []


_payload = {
    "prompt": "Building a website can be done in 10 simple steps:",
    "temperature": 0.80,
    "dynatemp_range": 0.25,
    "cache_prompt": True,
}
workers = 6
cindex = 0
timings = []
st = perf_counter()


def to_string(post: dict):
    conv = []
    for message in post["conversation"][:1]:
        conv.append("\n## MESSAGE BEGINS")
        _body = re.sub(r"(?![\n])\s+", " ", message["body"]).strip()
        conv.append(f"Query: {_body}")
        conv.append("## MESSAGE ENDS\n")
        break
    return "\n".join(conv)




with open("../dump/combined.json", "r") as f:
    discussion = json.load(f)
discussions = [d for d in discussion if d["category"] == CATEGORY]
del discussion
print(f"Loaded {len(discussions)} posts of category {CATEGORY}")
reqUrl = "http://localhost:8080/completion"



def augment_question(p_index, post):
    global slots
    global timings
    global cindex
    global questions
    
    if len(tokenizer(post["conversation"][0]["body"])) + mlen + 10 > MAX_QUERY_LENGTH:
        cindex += 1
        questions.append((p_index, "[!] Payload too long"))
        print(f"[!] [{cindex:>04}] Context too long, skipping.")
        return
    conversation = to_string(post)
    _payload["prompt"] = f"<s>[INST]{prompt} {conversation} {q}[/INST]"
    payload = json.dumps(_payload)
    response = requests.request("POST", reqUrl, data=payload, headers=headersList)
    rjson = response.json()
    _q = rjson["content"].strip()
    questions.append((p_index, _q))
    token_ps = round(rjson["timings"]["predicted_per_second"], 1)
    total_time = round(rjson["timings"]["predicted_ms"] / 1000, 1)
    prompt_time = round(rjson["timings"]["prompt_per_second"] / 1000, 1)
    cindex += 1
    timings.append(perf_counter())
    if len(timings) > 100:
        sp100 = round((perf_counter() - timings[-100]) / 100, 3)
    else:
        sp100 = 0
    print(
        f"[*] [{cindex:>04}] [{str(datetime.now().strftime('%b %d, %X'))}] "
        f"[{len(tokenizer(_q)):>04}] [{round((perf_counter()-st)/cindex,3):>05}] "
        f"[{sp100:>05}] {total_time=} {token_ps=} {prompt_time=}"
    )


with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
    for index, post in enumerate(discussions):
        executor.submit(augment_question, index, post)

questions.sort(key=lambda x: x[0])
for index, q in enumerate(questions):
    discussions[index]["question"] = q[1]


with open(f"../processed_data/{CATEGORY}-q-fp.json", "w", encoding="utf-8") as f:
    json.dump(discussions, f, indent=4)
