import json
from collections import Counter

with open("../dump/expert_queries.json", "r") as f:
    expert = json.load(f)
with open("../dump/discussion_queries.json", "r") as f:
    discussion = json.load(f)

combined = expert + discussion

print("Number of expert queries", len(expert))
print("Number of discussion queries", len(discussion))
print("Combined", len(combined))

with open("../dump/combined.json", "w") as f:
    json.dump(combined, f, indent=4)

categories = [i["category"].split("/")[-1] for i in combined]
print("Category Distribution\n",json.dumps(dict(Counter(categories).most_common()), indent=4))
