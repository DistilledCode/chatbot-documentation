import requests
import concurrent.futures
from bs4 import BeautifulSoup
import pickle
import json


with open("../dump/discussion_urls.json","r",encoding="utf-8") as f:
    data = json.load(f)

print(f"[*] Loaded {len(data)} title info.")

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

payload = ""
discussions = []
bad_results = []
multi_page = []


def _is_multi_page(soup):
    page_list = soup.find(
        "ul", class_="pagination pagination-md justify-content-center"
    )
    return True if page_list else False


def parse_expert_page(text: str, post_url: str):
    conv_dict = {
        "title": "",
        "url": post_url,
        "category": "",
        "conv_len": 0,
        "conversation": [],
    }
    soup = BeautifulSoup(text, "html.parser")
    if _is_multi_page(soup):
        return True
    main_container = soup.find("div", class_="col-lg-8")
    _category_tree = soup.find("ol", class_="breadcrumb bg-white")
    category = "/".join(
        li.get_text().strip().replace(" ", "-").lower()
        for li in _category_tree.find_all("li")
    )
    if not main_container:
        print(f"\t[!] Main Container DNE!")
        return None
    title = main_container.find("h1").get_text().lower().strip()
    conv_dict["title"] = title
    conv_dict["category"] = category
    user_headers = main_container.find_all("div", class_="flex-grow-1 ms-3")
    user_comments = main_container.find_all(
        "div", class_="img-res ft-page-content fluid-column dont-break-out"
    )
    print(
        f"\t[*] Found {len(user_headers):>03} messages. Title: {repr(title)}. Category: {repr(category)}"
    )
    conv_dict["conv_len"] = len(user_headers)
    for ind, (uheaders, ucomments) in enumerate(
        zip(user_headers, user_comments), start=1
    ):
        body = ucomments.get_text()
        _user_details = uheaders.find("a")
        if _user_details:
            user_name = _user_details.get_text().lower().strip()
            user_url = "https://www.lawyersclubindia.com" + _user_details["href"]

        #! if there is no <a> tag inside div tag with class "border p-3 mb-3" then
        #! the post was made by anonymous
        #! if the first post was made by anonymous the 2nd anchor is the "report abuse" link
        elif not _user_details:
            user_name = "anonymous"
            user_url = ""
        _date_tag = uheaders.find("abbr")
        if _date_tag:
            date = _date_tag.get_text().strip()
        else:
            date = "1 January 1990"
        conv_dict["conversation"].append(
            {
                "user_name": user_name,
                "url": user_url,
                "date": date,
                "body": body,
            }
        )
        print(
            f"\t\t[*] [{date}] [{ind:>03}] Message Length: {len(body):>04} "
            f"User: {repr(user_name)} Title: {repr(title)} "
        )
    return conv_dict


def process_page(curr_index, reqUrl):
    global discussions
    global bad_results
    global multi_page
    resp = requests.request("GET", reqUrl, data=payload, headers=headersList)
    if resp.status_code == 200:
        result = parse_expert_page(resp.text, reqUrl)
        if result is None:
            bad_results.append((reqUrl, "Content DNE?!"))
        elif result.__class__ is bool and result is True:
            multi_page.append(reqUrl)
            print(f"[*] [{curr_index:>05}] Found multi-paged post.")
        elif result.__class__ is dict:
            discussions.append(result)
            print(
                f"[*] [{curr_index:>05}] Total Post Scrapped: {len(discussions):>05}. "
                f"Percent: {round(len(discussions)/curr_index*100, 5):>07}"
            )
        if curr_index % 2000 == 0:
            print("[*] Dumping files.")
            dump_queries(discussions, curr_index)
            dump_bad_results(bad_results)
            dump_multi_pages(multi_page)
    else:
        bad_results.append((reqUrl, resp.text))
        print(f"[!] [{resp.status_code}]: {resp.url}: {resp.reason}")


def dump_multi_pages(multi_page):
    print(f"[*] Dumping {len(multi_page)} multi-page results.") 
    with open("../dump/other/discussion_multi_page.pkl", "wb") as f:
        pickle.dump(multi_page, f)
    print(f"[*] Dumped {len(multi_page)} multi-page results.")


def dump_bad_results(bad_results):
    with open("../dump/other/discussion_post_bad_reqs.pkl", "wb") as f:
        pickle.dump(bad_results, f)
    print(f"[*] Dumped {len(bad_results)} bad-results.")


def dump_queries(discussion_queries, curr_index):
    with open(
        f"../dump/discussion_queries.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(discussion_queries, f, indent=4)
    with open(f"../dump/other/discussion_curr_index", "w") as f:
        f.write(str(curr_index))
    print(f"[*] Dumped {len(discussion_queries)} queries.")


with concurrent.futures.ThreadPoolExecutor() as executor:
    for curr_index, post_info in enumerate(data, start=1):
        executor.submit(process_page, curr_index, post_info["url"])

dump_queries(discussions, -1)
dump_bad_results(bad_results)
dump_multi_pages(multi_page)

print(f"Total queries scrapped: {len(discussions)}")
print(f"Total bad results: {len(bad_results)}")
print(f"Total multi paged queries: {len(multi_page)}")
