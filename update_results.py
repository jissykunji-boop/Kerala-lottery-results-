import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.lotteryagent.kerala.gov.in"
RESULTS_URL = BASE + "/result/public/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def main():
    r = requests.get(RESULTS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    for tr in soup.find_all("tr"):
        text = " ".join(tr.stripped_strings)

        if not text:
            continue

        m = re.search(
            r"\b(SS|BT|SM|BR|SK|KN|DL|AK|NR|KR|RN|SR|ST|FN|PL|FT|PN|PO|SA|VA)-\s*(\d+)\b",
            text,
            re.I
        )

        if not m:
            continue

        code = m.group(1).upper()
        draw_no = int(m.group(2))

        date_match = re.search(
            r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b",
            text
        )

        date = date_match.group(1) if date_match else ""

        link = ""
        a = tr.find("a", href=True)

        if a:
            link = urljoin(BASE, a["href"])

        results.append({
            "code": code,
            "draw_no": draw_no,
            "date": date,
            "title": text,
            "source": link or RESULTS_URL
        })

    unique = {}

    for item in results:
        key = f"{item['code']}-{item['draw_no']}"
        unique[key] = item

    results = list(unique.values())

    latest = results[0] if results else {
        "message": "Official result page has no new result yet.",
        "source": RESULTS_URL
    }

    Path("latest_result.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    old_file = Path("results.json")

    if old_file.exists():
        try:
            old = json.loads(old_file.read_text(encoding="utf-8"))
        except Exception:
            old = []
    else:
        old = []

    if not isinstance(old, list):
        old = []

    old_map = {}

    for item in old:
        if isinstance(item, dict):
            key = f"{item.get('code','')}-{item.get('draw_no','')}"
            old_map[key] = item

    for item in results:
        key = f"{item['code']}-{item['draw_no']}"

        if key in old_map:
            old_map[key].update({
                "date": item["date"],
                "source": item["source"]
            })
        else:
            old_map[key] = item

    Path("results.json").write_text(
        json.dumps(list(old_map.values()), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Automatic lottery result update completed.")
    print("Latest:", latest)

if __name__ == "__main__":
    main()
