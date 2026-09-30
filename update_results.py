import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

BASE = "https://www.lotteryagent.kerala.gov.in"
RESULTS_URL = BASE + "/result/public/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r

def latest_result_link():
    html = fetch(RESULTS_URL).text
    soup = BeautifulSoup(html, "html.parser")

    # Find the first table row containing a lottery/draw code and date.
    for tr in soup.find_all("tr"):
        cells = [x.get_text(" ", strip=True) for x in tr.find_all(["td", "th"])]
        if len(cells) >= 3 and re.search(r"\([A-Z]{2}-\d+\)", " ".join(cells)):
            a = tr.find("a", href=True)
            if a:
                title = " ".join(cells)
                return title, urljoin(BASE, a["href"])

    # Fallback: first Download link on the page.
    a = soup.find("a", string=re.compile("Download", re.I), href=True)
    if a:
        return "Latest Kerala Lottery Result", urljoin(BASE, a["href"])

    raise RuntimeError("Could not find the official result download link.")

def extract_pdf_text(pdf_bytes):
    tmp = Path("latest_result.pdf")
    tmp.write_bytes(pdf_bytes)
    reader = PdfReader(str(tmp))
    return "\n".join((p.extract_text() or "") for p in reader.pages)

def parse_meta(title, text):
    combined = title + "\n" + text
    code = draw_no = lottery = draw_date = None

    m = re.search(r"\(([A-Z]{2})-(\d+)\)", title)
    if m:
        code, draw_no = m.group(1), m.group(2)

    m = re.search(r"([A-Z][A-Z -]+?)\s*[-–]\s*[^(\n]*\([A-Z]{2}-\d+\)", title)
    if m:
        lottery = m.group(1).strip()

    m = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", title)
    if m:
        draw_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    if not draw_date:
        m = re.search(r"(\d{2})[-/](\d{2})[-/](20\d{2})", text)
        if m:
            draw_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    return lottery, code, draw_no, draw_date

def extract_first_prize(text):
    # Common official PDF layouts put the first prize number near "1st Prize".
    patterns = [
        r"1st\s+PRIZE.*?(\d{6})",
        r"FIRST\s+PRIZE.*?(\d{6})",
        r"1st\s+Prize.*?(\d{6})",
    ]
    flat = re.sub(r"[ \t]+", " ", text.replace("\r", "\n"))
    for pat in patterns:
        m = re.search(pat, flat, flags=re.I | re.S)
        if m:
            return m.group(1)
    return None

def main():
    title, pdf_url = latest_result_link()
    pdf = fetch(pdf_url).content
    text = extract_pdf_text(pdf)
    lottery, code, draw_no, draw_date = parse_meta(title, text)
    first = extract_first_prize(text)

    latest = {
        "source": RESULTS_URL,
        "pdf_url": pdf_url,
        "lottery": lottery,
        "code": code,
        "draw_no": draw_no,
        "draw_date": draw_date,
        "first_prize": first,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "parser_status": "ok" if first else "metadata_only"
    }
    Path("latest_result.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Only add to results.json when a prize number was actually extracted.
    if first and lottery and code and draw_no and draw_date:
        p = Path("results.json")
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"results": []}
        data.setdefault("results", [])
        existing = next((x for x in data["results"]
                         if str(x.get("code")) == code and str(x.get("draw_no")) == draw_no), None)
        item = {
            "lottery": lottery,
            "code": code,
            "draw_no": draw_no,
            "draw_date": draw_date,
            "prizes": {
                "1st_prize": {"amount": 0, "numbers": [first]}
            },
            "source": pdf_url
        }
        if existing:
            existing.update(item)
        else:
            data["results"].insert(0, item)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(latest, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
