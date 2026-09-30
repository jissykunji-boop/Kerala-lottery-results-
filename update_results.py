import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.lotteryagent.kerala.gov.in"
RESULTS_URL = BASE + "/result/public/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Android; Mobile)"
}


def get_detail(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)

        prizes = []

        pattern = re.compile(
            r"(1st Prize|2nd Prize|3rd Prize|4th Prize|5th Prize|"
            r"6th Prize|7th Prize|8th Prize|9th Prize|"
            r"Cons Prize)[^|]{0,1000}",
            re.I
        )

        for match in pattern.finditer(text):
            value = " ".join(match.group(0).split())
            prizes.append(value)

        return {
            "detail_url": url,
            "details": text,
            "prizes": prizes
        }

    except Exception as e:
        return {
            "detail_url": url,
            "details": "",
            "prizes": [],
            "error": str(e)
        }


def main():
    response = requests.get(
        RESULTS_URL,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    for tr in soup.find_all("tr"):
        text = " ".join(tr.stripped_strings)

        if not text:
            continue

        match = re.search(
            r"\b(SS|BT|SM|BR|SK|KN|DL|KR|AK|NR|RN|SR|ST|FN|PL|FT|PN|PO|SA|VA)-\s*(\d+)\b",
            text,
            re.I
        )

        if not match:
            continue

        code = match.group(1).upper()
        draw_no = int(match.group(2))

        date_match = re.search(
            r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b",
            text
        )

        date = date_match.group(1) if date_match else ""

        link = ""

        a = tr.find("a", href=True)

        if a:
            link = urljoin(BASE, a["href"])

        item = {
            "code": code,
            "draw_no": draw_no,
            "date": date,
            "title": text,
            "source": link or RESULTS_URL
        }

        if link:
            detail = get_detail(link)
            item.update(detail)

        results.append(item)

    unique = {}

    for item in results:
        key = f"{item['code']}-{item['draw_no']}"
        unique[key] = item

    results = list(unique.values())

    latest = (
        results[0]
        if results
        else {
            "message": "Official result page has no new result yet.",
            "source": RESULTS_URL
        }
    )

    Path("latest_result.json").write_text(
        json.dumps(
            latest,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    old_file = Path("results.json")

    if old_file.exists():
        try:
            old = json.loads(
                old_file.read_text(encoding="utf-8")
            )
        except Exception:
            old = []
    else:
        old = []

    if not isinstance(old, list):
        old = []

    old_map = {}

    for item in old:
        if isinstance(item, dict):
            key = f"{item.get('code', '')}-{item.get('draw_no', '')}"
            old_map[key] = item

    for item in results:
        key = f"{item['code']}-{item['draw_no']}"
        old_map[key] = item

    Path("results.json").write_text(
        json.dumps(
            list(old_map.values()),
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("Automatic Kerala Lottery result update completed.")
    print("Results found:", len(results))
    print("Latest:", latest)


if __name__ == "__main__":
    main()
