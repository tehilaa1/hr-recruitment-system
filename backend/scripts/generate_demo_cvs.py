"""Regenerate the sample CV PDFs of the demo workspace (developer tool).

Writes app/demo_assets/cvs/{key}.pdf for every person in app/services/demo_seed.py.
The PDFs are committed, so the server needs neither this script nor its
dependencies. Run it only after changing the demo people.

Needs, in a separate throwaway venv (not in requirements.txt):
    pip install fpdf2 uharfbuzz
and a TTF font covering Hebrew and Latin, e.g. Rubik (SIL Open Font License):
    https://github.com/google/fonts/raw/main/ofl/rubik/Rubik%5Bwght%5D.ttf

Usage (from backend/):
    /path/to/venv/bin/python scripts/generate_demo_cvs.py --font /path/to/Rubik.ttf
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# demo_seed imports the app's models; only pure-Python pieces are used here
from app.services.demo_seed import CV_ASSETS_DIR, PEOPLE, DemoPerson  # noqa: E402

ACCENT = (37, 99, 235)
MUTED = (100, 116, 139)


def render(person: DemoPerson, font: str):
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(True, 16)
    pdf.add_font("Rubik", "", font)
    pdf.set_text_shaping(use_shaping_engine=True, direction="rtl")
    pdf.set_title(f"קורות חיים - {person.full_name} {person.family_name}")
    pdf.set_author("HireTrack demo")
    pdf.add_page()
    width = pdf.epw

    def line(text: str, size: float, color=(15, 23, 42), h: float = 0, gap: float = 0) -> None:
        pdf.set_font("Rubik", size=size)
        pdf.set_text_color(*color)
        pdf.multi_cell(width, h or size * 0.55, text, align="R", new_x="LMARGIN", new_y="NEXT")
        if gap:
            pdf.ln(gap)

    def heading(text: str) -> None:
        pdf.ln(3)
        line(text, 13, ACCENT)
        pdf.set_draw_color(*ACCENT)
        pdf.line(pdf.l_margin, pdf.get_y() + 0.5, pdf.l_margin + width, pdf.get_y() + 0.5)
        pdf.ln(2.5)

    line(f"{person.full_name} {person.family_name}", 24, gap=1)
    line(person.profession, 14, ACCENT, gap=1)
    line(f"{person.address}  |  {person.phone}  |  {person.email}", 10, MUTED, gap=2)

    heading("תקציר")
    line(person.summary, 11, h=6)
    heading("ניסיון תעסוקתי")
    for years, role, company in person.experience:
        line(f"{role} – {company}", 11.5, h=6)
        line(years, 10, MUTED, h=5, gap=1.5)
    heading("השכלה")
    for item in person.education:
        line(item, 11, h=6)
    heading("כישורים")
    line(" · ".join(person.skills), 11, h=6)
    pdf.ln(6)
    line("מסמך לדוגמה בלבד – הפרטים בדויים.", 8.5, MUTED)
    return bytes(pdf.output())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the demo CV PDFs")
    parser.add_argument("--font", required=True, help="TTF with Hebrew + Latin glyphs (e.g. Rubik)")
    args = parser.parse_args()
    CV_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for person in PEOPLE:
        out = CV_ASSETS_DIR / f"{person.key}.pdf"
        out.write_bytes(render(person, args.font))
        print(f"✓ {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
