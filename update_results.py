import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

BASE = "https://result.keralalotteries.com"
RESULTS_URL = BASE + "/"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def download_pdf(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=60
        )
        r.raise_for_status()

        reader = PdfReader(io.BytesIO(r.content))

        text = []

        for page in reader.pages:
            text.append(page.extract_text() or "")

        return "\n".join(text)

    except Exception as e:
        print("PDF ERROR:", url, e)
        return ""


def parse_result(text, url):
    clean = " ".join(text.split())

    m = re.search(
        r"([A-Z]+-\d+)(?:st|nd|rd|th)?\s+DRAW\s+held\s+on:-\s*"
        r"(\d{1,2}/\d{1,2}/\d{4})",
        clean,
        re.I
    )

    if not m:
        print("Could not identify lottery:", url)
        return None

    lottery = m.group(1).upper()
    date = m.group(2)

    code, number = lottery.split("-")

    prizes = {}

    prize_names = [
        "1st Prize",
        "Cons Prize",
        "2nd Prize",
        "3rd Prize",
        "4th Prize",
        "5th Prize",
        "6th Prize",
        "7th Prize",
        "8th Prize",
        "9th Prize"
    ]

    for i, name in enumerate(prize_names):
        if i + 1 < len(prize_names):
            next_names = prize_names[i + 1:]
        else:
            next_names = []

        pattern = re.escape(name) + r".*?"

        if next_names:
            pattern += "(?=" + "|".join(
                re.escape(x) for x in next_names
            ) + r"|The prize winners)"
        else:
            pattern += r"(?=The prize winners|$)"

        match = re.search(
            pattern,
            clean,
            re.I
        )

        if match:
            prizes[name] = " ".join(
                match.group(0).split()
            )

    return {
        "code": code,
        "draw_no": int(number),
        "lottery": lottery,
        "date": date,
        "source": url,
        "prizes": prizes,
        "details": clean
    }


def main():

    response = requests.get(
        RESULTS_URL,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    html = response.text

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    links = []

    # Method 1: normal HTML links
    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "viewlotisresult.php" in href:
            links.append(
                urljoin(BASE + "/", href)
            )

    # Method 2: raw HTML fallback
    raw_links = re.findall(
        r"""(?:href|url)\s*=\s*["']([^"']*viewlotisresult\.php\?drawserial=\d+[^"']*)["']""",
        html,
        re.I
    )

    for href in raw_links:
        links.append(
            urljoin(BASE + "/", href)
        )

    # Remove duplicates
    links = list(dict.fromkeys(links))

    print("RESULT LINKS FOUND:", len(links))

    results = []

    for url in links:

        print("Reading:", url)

        pdf_text = download_pdf(url)

        if not pdf_text:
            continue

        result = parse_result(
            pdf_text,
            url
        )

        if result:
            results.append(result)

    # Remove duplicate lottery draws
    unique = {}

    for item in results:
        key = item["lottery"]
        unique[key] = item

    results = list(unique.values())

    print("RESULTS FOUND:", len(results))

    if not results:
        print("NO RESULTS FOUND.")
        print("Keeping existing results.json.")

        if not Path("results.json").exists():
            Path("results.json").write_text(
                "[]",
                encoding="utf-8"
            )

        return

    # Newest first
    results.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    latest = results[0]

    Path("latest_result.json").write_text(
        json.dumps(
            latest,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    Path("results.json").write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("SUCCESS")
    print("Latest:", latest["lottery"])
    print("Date:", latest["date"])


if __name__ == "__main__":
    main()
