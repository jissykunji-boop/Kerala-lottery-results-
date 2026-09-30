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


def get_pdf_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=40)
        r.raise_for_status()

        reader = PdfReader(io.BytesIO(r.content))

        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")

        return "\n".join(pages)

    except Exception as e:
        print("PDF error:", url, e)
        return ""


def parse_result(text, url):
    clean = " ".join(text.split())

    m = re.search(
        r"LOTTERY NO\.?\s*([A-Z]+-\d+).*?"
        r"DRAW held on:-\s*(\d{1,2}/\d{1,2}/\d{4})",
        clean,
        re.I
    )

    if not m:
        m = re.search(
            r"([A-Z]+-\d+).*?"
            r"held on:-\s*(\d{1,2}/\d{1,2}/\d{4})",
            clean,
            re.I
        )

    if not m:
        return None

    code = m.group(1).upper()
    date = m.group(2)

    number_match = re.search(
        rf"{re.escape(code)}",
        clean,
        re.I
    )

    draw_no = 0

    if number_match:
        n = re.search(r"-(\d+)", code)
        if n:
            draw_no = int(n.group(1))

    prizes = []

    prize_pattern = re.compile(
        r"(1st Prize|2nd Prize|3rd Prize|4th Prize|"
        r"5th Prize|6th Prize|7th Prize|8th Prize|9th Prize)"
        r".*?(?=(?:1st Prize|2nd Prize|3rd Prize|4th Prize|"
        r"5th Prize|6th Prize|7th Prize|8th Prize|9th Prize)|"
        r"The prize winners|Next [A-Z]|$)",
        re.I
    )

    for match in prize_pattern.finditer(clean):
        prizes.append(" ".join(match.group(0).split()))

    return {
        "code": code.split("-")[0],
        "draw_no": draw_no,
        "lottery": code,
        "date": date,
        "title": clean[:250],
        "source": url,
        "details": clean,
        "prizes": prizes
    }


def main():

    response = requests.get(
        RESULTS_URL,
        headers=HEADERS,
        timeout=40
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    found = []

    for a in soup.find_all("a", href=True):

        href = a["href"]

        if "viewlotisresult.php" not in href:
            continue

        url = urljoin(BASE, href)

        row = a.find_parent("tr")

        if row:
            row_text = " ".join(row.stripped_strings)
        else:
            row_text = a.parent.get_text(
                " ",
                strip=True
            )

        print("Found:", row_text)
        print("PDF:", url)

        pdf_text = get_pdf_text(url)

        if not pdf_text:
            continue

        result = parse_result(
            pdf_text,
            url
        )

        if result:
            found.append(result)

    unique = {}

    for item in found:
        key = item["lottery"]

        if key not in unique:
            unique[key] = item

    results = list(unique.values())

    print("TOTAL RESULTS:", len(results))

    if results:
        latest = results[0]
    else:
        latest = {
            "message": "No result PDF found yet.",
            "source": RESULTS_URL
        }

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

    print("Lottery update completed.")
    print("Latest:", latest)


if __name__ == "__main__":
    main()
