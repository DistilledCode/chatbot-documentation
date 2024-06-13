import requests
from bs4 import BeautifulSoup
import concurrent.futures
import pickle
import json
from pathlib import Path


dump_path = Path("../dump")
other_path = Path("../dump/other")
dump_path.mkdir(parents=True, exist_ok=True)
other_path.mkdir(parents=True, exist_ok=True)


headersList = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "TE": "trailers",
}

CURRENT_OFFSET = 1
LAST_PAGE = 14250
LAST_PAGE = 14 # FOR Testing
payload = ""
experts = []
bad_results = []


def process_page(offset):
    global experts
    reqUrl = f"https://www.lawyersclubindia.com/experts/browse.asp?mode=resolved&offset={offset}"
    resp = requests.request("GET", reqUrl, data=payload, headers=headersList)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.content, "html.parser")
        h4s = soup.find_all("h4", class_=None)
        for h4 in h4s:
            anchor = h4.find_all("a")[0]
            post_title = anchor.get("title", "").strip().lower()
            href = anchor.get("href", "").strip()
            if post_title != "" and href != "":
                url = "https://www.lawyersclubindia.com/experts/" + href
                experts.append({"title": post_title, "url": url})
                print(
                    f"[*] [offset={offset:>05}] {len(experts):>06} posts scrapped. [{round(len(experts)/offset,5):>08}] "
                    f"Title: {len(post_title):>03}. URL: {href}"
                )
                if offset % 100 == 0:
                    dump_questions(experts, offset)
            else:
                print(f"[!] Anchor title (and/or) href empty: {href=}. {post_title=}")
    else:
        bad_results.append((reqUrl, resp.text))
        with open("../dump/other/bad_reqs_expert_urls.pkl", "wb") as f:
            pickle.dump(bad_results, f)
        print(f"[!] [{resp.status_code}]: {resp.url}: {resp.reason}")


def dump_questions(posts, offset):
    with open("../dump/expert_urls.json", "w") as f:
        json.dump(posts, f, indent=4)
    with open("../dump/other/expert_detail_offsets", "w") as f:
        f.write(str(offset))


with concurrent.futures.ThreadPoolExecutor() as executor:
    for offset in range(CURRENT_OFFSET, LAST_PAGE):
        executor.submit(process_page, offset)

dump_questions(experts, -1)

print(len(experts))
