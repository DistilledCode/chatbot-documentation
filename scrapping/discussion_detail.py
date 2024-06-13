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
LAST_PAGE = 14077
LAST_PAGE = 14 # For Testing
payload = ""
posts = []
bad_results = []


def process_page(offset):
    global posts
    reqUrl = f"https://www.lawyersclubindia.com/forum/display.asp?offset={offset}"
    resp = requests.request("GET", reqUrl, data=payload, headers=headersList)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.content, "html.parser")
        # if offset == 1:
        # cat_title = re.sub(
        #     r"\s+",
        #     " ",
        #     soup.find_all("title")[0].get_text().lower(),
        # ).strip()
        anchors = soup.find_all("a", class_="text-dark")
        tds = soup.find_all("td", class_="text-center")
        for anchor, td in zip(anchors, tds):
            post_title = anchor.get("title", "").strip().lower()
            href = anchor.get("href", "").strip()
            _r = td.find_all("font")
            replies = int(_r[1].text.split()[0]) if len(_r) == 2 else 0

            if post_title != "" and href != "":
                url = "https://www.lawyersclubindia.com/forum/" + href
                posts.append(
                    {
                        "title": post_title,
                        "replies": replies,
                        "url": url,
                    }
                )
                print(
                    f"[*] [offset={offset:>05}] {len(posts):>06} posts scrapped. [{round(len(posts)/offset,2):>05}] "
                    f"Title: {len(post_title):>03}. Replies: {replies:>02}. URL: {href}"
                )
                if offset % 100 == 0:
                    dump_questions(posts, offset)
            else:
                print(f"[!] Anchor title (and/or) href empty: {href=}. {post_title=}")
    else:
        bad_results.append((reqUrl, resp.text))
        with open("../dump/other/bad_reqs_discussion_url", "wb") as f:
            pickle.dump(bad_results, f)
        print(f"[!] [{resp.status_code}]: {resp.url}: {resp.reason}")


def dump_questions(posts, offset):
    with open(f"../dump/discussion_urls.json", "w") as f:
        json.dump(posts, f, indent=4)
    with open(f"../dump/other/discussion_detail_offsets", "w") as f:
        f.write(str(offset))


with concurrent.futures.ThreadPoolExecutor() as executor:
    for offset in range(CURRENT_OFFSET, LAST_PAGE):
        executor.submit(process_page, offset)

dump_questions(posts, -1)

print(len(posts))
