import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader

SOURCES = {
    "baronian_icsnl56": "https://lingpapers.sites.olt.ubc.ca/files/2021/08/ICSNL56_KamigakiBaron_final.pdf",
    "dolatian_schwa": "https://bpb-us-e1.wpmucdn.com/you.stonybrook.edu/dist/c/2461/files/2021/03/Dolatian-schwa.pdf",
    "armenian_phonology_zenodo": "https://zenodo.org/records/5893697/files/Armenian%20phonology%20and%20phonetics.pdf",
}

KEYWORDS = [
    "schwa",
    "epenthesis",
    "cluster",
    "clusters",
    "sonority",
    "western armenian",
    "initial",
    "medial",
    "final",
]


def fetch(url: str, out_path: Path) -> bool:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=30) as resp:
            out_path.write_bytes(resp.read())
        return True
    except Exception as e:
        print(f"[download-fail] {url} :: {e}")
        return False


def extract_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        pages = []
        for p in reader.pages:
            pages.append(p.extract_text() or "")
        return "\n".join(pages)
    except Exception as e:
        print(f"[parse-fail] {pdf_path} :: {e}")
        return ""


def contexts(text: str, kw: str, width: int = 220) -> list[str]:
    out = []
    for m in re.finditer(re.escape(kw), text, flags=re.IGNORECASE):
        s = max(0, m.start() - width)
        e = min(len(text), m.end() + width)
        chunk = text[s:e].replace("\n", " ")
        out.append(re.sub(r"\s+", " ", chunk).strip())
        if len(out) >= 12:
            break
    return out


def main() -> int:
    base = Path("_wa_source_extract")
    base.mkdir(exist_ok=True)

    for name, url in SOURCES.items():
        pdf_path = base / f"{name}.pdf"
        if not pdf_path.exists():
            print(f"[download] {name}")
            if not fetch(url, pdf_path):
                continue
        text = extract_text(pdf_path)
        if not text.strip():
            continue
        txt_path = base / f"{name}.txt"
        txt_path.write_text(text, encoding="utf-8")
        print(f"[ok] {name} chars={len(text)}")

        report_path = base / f"{name}_contexts.txt"
        with report_path.open("w", encoding="utf-8") as f:
            for kw in KEYWORDS:
                hits = contexts(text, kw)
                if not hits:
                    continue
                f.write(f"\n=== {kw} ===\n")
                for h in hits:
                    f.write(f"- {h}\n")
        print(f"[contexts] {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

