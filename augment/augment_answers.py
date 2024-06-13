import json
import requests
import re
import concurrent.futures
from time import perf_counter
from datetime import datetime
from augment.augment_questions import CATEGORY
from keras_nlp import models

MAX_TOKEN_LEN = 4400

tokenizer = models.MistralTokenizer.from_preset("mistral_7b_en")

prompt = """<s>[INST] Task: Extract the answer to the provided question using the perspective of a trained legal expert.
Guidelines for Answer:
1. Context-Free Response: The answer should not directly reference or cite the conversation, context, or any specific information provided. It must be an independent, self-contained response.
2. Factual Statement: The response should be presented as a factual statement, devoid of personal opinion or interpretation.
3. Legal Perspective: Ensure that the answer reflects the viewpoint of a trained legal expert.
4. Polite Declination: If unable to generate an answer without referencing the context, politely decline providing the answer.
5. Banned Word/Phrases:
    - a. Avoid phrases such as "based on the conversation/context/information."
    - b. Refrain from using expressions like "according to the conversation/information/context."
Specific Instructions:
- Emphasize the importance of strict adherence to the guidelines provided.
- Reiterate the necessity of generating context-free, factual, and legally informed responses.
- Clarify that the model should only use the context silently to guide the answer, without explicitly referring to it in the response.
- Give emphasis to reference of any act/law mentioned in the context. [/INST] I understand the importance of adhering to the guidelines provided. I will ensure that my responses are context-free, factual, and legally informed. I will maintain a professional and legal perspective while generating answers. I will not use any phrases that directly reference the conversation, context, or specific information provided. If unable to generate an answer without referencing the context, I will politely decline providing the answer. Furthermore, if any act or law is mentioned in the context, I will make sure to reference it in the response.</s>"""

example = """
<s>[INST]
## QUESTION
I want to register a marriage in Bangalore, but my spouse and I got married in Kolkata. How can we register our marriage under the Special Marriage Act in Bangalore, where we currently reside?

## CONTEXT BEGINS: (DO NOT CITE THE CONTEXT IN ANSWER)

## MESSAGE 1 BEGINS
A marriage can be registered under the jurisdiction where the couple currently resides.
## MESSAGE 1 ENDS

## MESSAGE 2 BEGINS
For registration under the Special Marriage Act, presence of both spouses and witnesses at the registrar’s office in Bangalore will be necessary.
## MESSAGE 2 ENDS

## CONTEXT ENDS

## ANSWER [/INST]
To register your marriage in Bangalore under the Special Marriage Act, despite being married in Kolkata, you can apply at the local registrar's office in Bangalore, where you both currently reside. The process includes submitting the marriage application form along with necessary documents such as your marriage certificate from Kolkata, proof of residence in Bangalore, identity proofs, and photographs. Both spouses must be present along with witnesses at the time of registration. It is essential to check with the Bangalore marriage registrar for any additional specific requirements or documentation needed for registration. </s>

<s>[INST]
## QUESTION
I'm looking to challenge an eviction notice served by my landlord in Delhi, but I currently live in Chennai. Can I file a petition against this eviction in Chennai courts?

## CONTEXT BEGINS: (DO NOT CITE THE CONTEXT IN ANSWER)

## MESSAGE 1 BEGINS
Jurisdiction generally lies where the property is located, but exceptions can apply based on the defendant's residence.
## MESSAGE 1 ENDS

## MESSAGE 2 BEGINS
It’s possible to seek temporary relief from local courts where the tenant resides.
## MESSAGE 2 ENDS

## CONTEXT ENDS

## ANSWER [/INST]
To challenge an eviction notice served by your landlord in Delhi while you reside in Chennai, you would typically need to address this issue through the courts in Delhi where the property is located. However, for temporary relief, such as a stay on the eviction, you may approach the local courts in Chennai. It is advisable to file a petition in Delhi for the main proceedings but consider consulting a legal expert to explore the possibility of obtaining temporary relief from Chennai courts based on your current residence and circumstances. </s>"""


headersList = {
    "Accept": "*/*",
    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
    "Content-Type": "application/json",
}


answers = []



_payload = {
    "prompt": "Building a website can be done in 10 simple steps:",
    "temperature": 0.85,
    "dynatemp_range": 0.25,
    "cache_prompt": True,
}
cindex = 0
timings = []
st = perf_counter()
promt_len = len(tokenizer(f"{prompt} {example}"))
print(promt_len)



def to_string(post: dict):
    conv = []
    conv.append("\n## CONTEXT BEGINS: (DO NOT CITE THE CONTEXT IN ANSWER)\n")
    for ind, message in enumerate(post["conversation"][1:], start=1):
        conv.append((f"## MESSAGE {ind} BEGINS"))
        _body = re.sub(r"(?![\n])\s+", " ", message["body"]).strip()
        conv.append(_body)
        conv.append(f"## MESSAGE {ind} ENDS\n")
    conv.append("## CONTEXT ENDS")
    return f"\n## QUESTION\n{post['question']}" + "\n".join(conv) + "\n\n## ANSWER "


with open(f"../processed_data/{CATEGORY}-q-fp.json", "r") as f:
    discussion = json.load(f)
print(f"Loaded {len(discussion)} posts")
reqUrl = "http://localhost:8080/completion"


def get_answer(p_index, post):
    global slots
    global timings
    global cindex
    global answers
    if post["question"] == "[!] Payload too long":
        cindex += 1
        answers.append((p_index, "[!] Question was too long. Was skipped."))
        print(f"[!] [{cindex:>04}] Answer not generated: Question was long.")
        return
    conversation = to_string(post)
    # TODO: For family it was 3100, might need to redo it i guess
    if promt_len + len(tokenizer(conversation)) > MAX_TOKEN_LEN:
        cindex += 1
        answers.append(
            (p_index, f"[!] Overall context is too long ({tokenizer(conversation)})")
        )
        print(f"[!] [{cindex:>04}] Answer not generated: Context was long.")
        return

    _payload["prompt"] = f"{prompt} {example}\n<s>[INST]{conversation}[/INST]"
    payload = json.dumps(_payload)
    response = requests.request("POST", reqUrl, data=payload, headers=headersList)
    rjson = response.json()
    _q = rjson["content"].strip()
    answers.append((p_index, _q))
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


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    for index, post in enumerate(discussion):
        executor.submit(get_answer, index, post)

print(perf_counter() - st)
answers.sort(key=lambda x: x[0])
for index, q in enumerate(answers):
    discussion[index]["answer"] = q[1].strip()


with open(f"../processed_data/answer-{CATEGORY}-q-fp.json", "w", encoding="utf-8") as f:
    json.dump(discussion, f, indent=4)
