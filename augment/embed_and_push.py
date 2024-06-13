from pinecone import Pinecone, ServerlessSpec
import json
import os
from augment.augment_questions import CATEGORY 
os.environ["HF_HOME"] = "/media/sda1/Share/Anurag/.data/model/"
os.environ["HF_HUB_CACHE"] = "/media/sda1/Share/Anurag/.data/model/hub"
from transformers import AutoTokenizer
from FlagEmbedding import BGEM3FlagModel



pc = Pinecone(api_key="YOUR-API-KEY")


with open(f"./proc_data/answer-{CATEGORY}-q-fp.json") as f:
    data = json.load(f)
stringify = lambda x: f"## QUESTION: {x['question']}\n\n## ANSWER: {x['answer']}"
data_ = [stringify(i) for i in data]



tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-m3')
toklen = lambda x: len(tokenizer(x)['input_ids'])


sentences = data_
count = 0
for ind, i in enumerate(data_, start=1):
    tklen = toklen(i)
    b = True if tklen > 8192 else False
    count +=bool(b)
    print(f"\r[{ind:>05}] {tklen:>05} {b}", end="")
print()
print(f"Number of sentences that will be truncated: {count}")
model = BGEM3FlagModel("BAAI/bge-m3")
embeddings = model.encode(sentences, batch_size=10, max_length=8192)["dense_vecs"]


pinecone_index_name = "ai-law"
if pinecone_index_name not in pc.list_indexes().names():
    pc.create_index(
        name=pinecone_index_name,
        dimension=1024,
        metric="dotproduct",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

vectors = []
for ind, (pair, embed) in enumerate(zip(data, embeddings), start=1):
    vectors.append(
        {
            "id": f"{CATEGORY}-{ind:>05}",
            "values": embed,
            "metadata": {
                "question": pair["question"],
                "answer": pair["answer"],
            },
        }
    )

index = pc.Index(pinecone_index_name)

print("Number of vectors to be encoded and pushed:", len(vectors))

for i in range(0, len(vectors), 100):
    index.upsert(vectors=vectors[i : i + 100])
    print(f"\rUploaded batch {i//100} out of {len(vectors)//100}", end="")

print(index.describe_index_stats())