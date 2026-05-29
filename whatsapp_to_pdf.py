"""
WhatsApp Chat → PDF Converter  (v3 — Unicode + Emoji)
======================================================
Converts an exported WhatsApp chat (.txt) into a styled PDF that visually
resembles the WhatsApp UI.  Uses DejaVuSans (full Unicode text) and
NotoEmoji (emoji glyphs) loaded via add_font() — never built-in fonts.

Fonts are downloaded automatically into ./fonts/ on first run.

HOW TO CONFIGURE:
  MY_NAME     – your name exactly as it appears in the chat
  INPUT_FILE  – filename relative to this script (or an absolute path)
  OUTPUT_FILE – output PDF filename
"""

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
MY_NAME     = "Your Name"
INPUT_FILE  = "chat.txt"
OUTPUT_FILE = "whatsapp_chat.pdf"
# ───────────────────────────────────────────────────────────────────────────────

import re
import sys
from datetime import datetime
from pathlib import Path
import urllib.request
from fpdf import FPDF

# ─── COLORS ────────────────────────────────────────────────────────────────────
COLOR_MY_BUBBLE    = (217, 253, 211)   # #D9FDD3  — your messages
COLOR_OTHER_BUBBLE = (240, 240, 240)   # #F0F0F0  — others' messages
COLOR_BG           = (236, 229, 221)   # #ECE5DD  — page background
COLOR_HEADER_BG    = (7,   94,  84)    # #075E54  — header bar
COLOR_HEADER_TEXT  = (255, 255, 255)
COLOR_MY_NAME      = (7,   94,  84)    # dark green sender label
COLOR_OTHER_NAME   = (100, 100, 100)
COLOR_TIMESTAMP    = (130, 130, 130)
COLOR_DATE_LINE    = (160, 160, 160)
COLOR_DATE_TEXT    = (80,  80,  80)
COLOR_PAGE_NUM     = (150, 150, 150)

# ─── FONT AUTO-DOWNLOAD ────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
FONT_DIR   = SCRIPT_DIR / "fonts"

_FONT_URLS = {
    "DejaVuSans.ttf": (
        "https://github.com/py-pdf/fpdf2/raw/master/test/fonts/DejaVuSans.ttf"
    ),
    "DejaVuSans-Bold.ttf": (
        "https://github.com/py-pdf/fpdf2/raw/master/test/fonts/DejaVuSans-Bold.ttf"
    ),
    # NotoSansSymbols2 — symbols/math/misc Unicode coverage
    "NotoSansSymbols2.ttf": (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/"
        "notosanssymbols2/NotoSansSymbols2-Regular.ttf"
    ),
    # TwemojiMozilla — full colour-outline emoji glyphs (COLR/CPAL)
    # The release asset is named 'Twemoji.Mozilla.ttf' (with dots)
    "TwemojiMozilla.ttf": (
        "https://github.com/mozilla/twemoji-colr/releases/download/v0.7.0/Twemoji.Mozilla.ttf",
    ),
}


def ensure_fonts() -> None:
    """
    Download required font files into ./fonts/ if they are not already present.
    For entries with multiple URLs (tuple of strings), each URL is tried in order
    until one succeeds.  Exits with a clear error if a required font can't be fetched.
    """
    FONT_DIR.mkdir(exist_ok=True)
    for fname, urls in _FONT_URLS.items():
        dest = FONT_DIR / fname
        if dest.exists():
            continue
        # Normalise: single string → one-element tuple
        if isinstance(urls, str):
            urls = (urls,)
        print(f"  ⬇  Downloading {fname} …")
        downloaded = False
        for url in urls:
            try:
                urllib.request.urlretrieve(url, dest)
                print(f"     ✓  saved → {dest}")
                downloaded = True
                break
            except Exception as exc:
                print(f"     ✗  {url.split('/')[-1]} failed: {exc}")
        if not downloaded:
            # Non-critical fonts: warn and continue; critical fonts: exit
            if fname in ("TwemojiMozilla.ttf", "NotoSansSymbols2.ttf"):
                print(f"     ⚠  Could not download {fname}. Emoji may render as □.")
            else:
                print(f"     Place it manually in: {FONT_DIR}")
                sys.exit(1)


# ─── ZERO-WIDTH CHARACTER HANDLING ─────────────────────────────────────────────
# WhatsApp prefixes many lines with U+200E (LRM) and embeds others inside text.
_ZW = "\u200e\u200f\u200b\u200c\u200d\ufeff\u2060"


def _strip_zw(text: str) -> str:
    """Remove every zero-width / invisible Unicode character from text."""
    for ch in _ZW:
        text = text.replace(ch, "")
    return text

def _sanitize(text: str) -> str:
    """Strip zero-width chars and null bytes. Text is passed to multi_cell() unchanged."""
    return _strip_zw(text).replace("\x00", "")


# ─── WHATSAPP EXPORT PARSING ───────────────────────────────────────────────────
# Format A (newer iOS/Android): [YYYY-MM-DD, HH:MM:SS] Sender: Body
_PAT_BRACKET = re.compile(
    r"^\["
    r"(\d{4}-\d{2}-\d{2}),\s+"        # date
    r"(\d{1,2}:\d{2}(?::\d{2})?)"     # time
    r"\]\s+"
    r"([^:]+?):\s*"                    # sender (lazy, allow empty body)
    r"(.*)$",                          # body  — (.*)$ so empty lines match
    re.IGNORECASE,
)

# Format B (older / some regions): DD/MM/YYYY, HH:MM - Sender: Body
_PAT_DASH = re.compile(
    r"^(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),?\s+"
    r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)"
    r"\s*[\-\u2013]\s+"
    r"([^:]+?):\s*"
    r"(.*)$",
    re.IGNORECASE,
)

# System lines — bracket style (no sender: body pattern)
_SYS_BRACKET = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s+(.+)$"
)

# System lines — dash style
_SYS_DASH = re.compile(
    r"^(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),?\s+"
    r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)"
    r"\s*[\-\u2013]\s+(.+)$"
)


def _friendly_date(date_str: str) -> str:
    """Parse a raw date string and return 'May 07, 2025'."""
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y", "%m/%d/%Y",
        "%d/%m/%y", "%m/%d/%y",
        "%d-%m-%Y", "%m-%d-%Y",
        "%d-%m-%y", "%m-%d-%y",
    ):
        try:
            return datetime.strptime(date_str, fmt).strftime("%B %d, %Y")
        except ValueError:
            pass
    return date_str  # fallback: return as-is


def parse_chat(filepath: str) -> list[dict]:
    """
    Parse a WhatsApp .txt export into a list of message dicts:
        { date, time, sender, message, is_mine }

    Rules applied:
    • Zero-width chars stripped from every line before matching
    • Both bracket [YYYY-MM-DD] and dash DD/MM/YYYY formats handled
    • Empty body after strip → replaced with '[media]'
    • Multi-line messages merged into a single bubble
    • System lines (no sender colon) → skipped
    """
    messages: list[dict] = []
    current: dict | None = None

    try:
        with open(filepath, encoding="utf-8") as fh:
            raw_lines = fh.readlines()
    except UnicodeDecodeError:
        with open(filepath, encoding="latin-1") as fh:
            raw_lines = fh.readlines()

    for raw in raw_lines:
        # Strip line ending, then ALL leading invisible chars
        line = _strip_zw(raw.rstrip("\r\n").lstrip(_ZW))

        m = _PAT_BRACKET.match(line) or _PAT_DASH.match(line)
        if m:
            date_str, time_str, sender, body = m.groups()
            body   = _sanitize(body).strip() or "[media]"
            sender = _sanitize(sender).strip()
            current = {
                "date":    date_str.strip(),
                "time":    time_str.strip(),
                "sender":  sender,
                "message": body,
                "is_mine": sender == MY_NAME,
            }
            messages.append(current)
            continue

        # System / event line (encryption notice, call events without sender)
        if _SYS_BRACKET.match(line) or _SYS_DASH.match(line):
            current = None
            continue

        # Continuation of a multi-line message
        if current is not None and line.strip():
            current["message"] += "\n" + _sanitize(line.strip())

    return messages


# ─── DRAWING HELPERS ───────────────────────────────────────────────────────────

def _rounded_rect(pdf: FPDF, x: float, y: float, w: float, h: float, r: float) -> None:
    """
    Draw a filled rounded rectangle using rect() + ellipse() only.
    fpdf2 v2.8.x does NOT have rounded_rect() — this is the compatible approach.
    """
    r = min(r, w / 2, h / 2)
    d = r * 2
    # Three rectangles covering the interior
    pdf.rect(x + r, y,         w - d, h,     style="F")   # centre column
    pdf.rect(x,     y + r,     r,     h - d, style="F")   # left strip
    pdf.rect(x + w - r, y + r, r,     h - d, style="F")   # right strip
    # Four corner circles
    pdf.ellipse(x,           y,           d, d, style="F")
    pdf.ellipse(x + w - d,   y,           d, d, style="F")
    pdf.ellipse(x,           y + h - d,   d, d, style="F")
    pdf.ellipse(x + w - d,   y + h - d,   d, d, style="F")


class WhatsAppPDF(FPDF):
    """FPDF subclass with WhatsApp-themed header, background and footer."""

    def header(self) -> None:
        # ① Beige page background (must come first so header bar paints over it)
        self.set_fill_color(*COLOR_BG)
        self.rect(0, 0, self.w, self.h, style="F")

        # ② Dark-green header bar
        self.set_fill_color(*COLOR_HEADER_BG)
        self.rect(0, 0, self.w, 13, style="F")

        self.set_font("DejaVu", "B", 11)
        self.set_text_color(*COLOR_HEADER_TEXT)
        self.set_y(2.5)
        self.cell(0, 8, "WhatsApp Chat Export", align="C")

        self.set_text_color(0, 0, 0)
        self.set_y(17)   # cursor below header + small gap

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("DejaVu", "", 7.5)
        self.set_text_color(*COLOR_PAGE_NUM)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


def _draw_date_sep(pdf: FPDF, label: str) -> None:
    """Render a centered grey pill date separator between day groups."""
    y = pdf.get_y() + 2
    pdf.set_font("DejaVu", "", 7.5)
    pill_w = pdf.get_string_width(label) + 12
    pill_h = 5.5
    pill_x = (pdf.w - pill_w) / 2
    line_y = y + pill_h / 2
    m = 10   # horizontal margin for the flanking lines

    pdf.set_draw_color(*COLOR_DATE_LINE)
    pdf.line(m, line_y, pill_x - 2, line_y)
    pdf.line(pill_x + pill_w + 2, line_y, pdf.w - m, line_y)

    pdf.set_fill_color(*COLOR_DATE_LINE)
    pdf.set_draw_color(*COLOR_DATE_LINE)
    _rounded_rect(pdf, pill_x, y, pill_w, pill_h, r=2.5)

    pdf.set_text_color(*COLOR_DATE_TEXT)
    pdf.set_xy(pill_x, y + 0.5)
    pdf.cell(pill_w, pill_h - 1, label, align="C")

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + pill_h + 3)


def _draw_bubble(pdf: FPDF, msg: dict, page_w: float, margin: float, max_bw: float) -> None:
    """
    Render one complete chat bubble (background + name + body text + timestamp).
    Uses multi_cell() with split_only=True to pre-calculate height before drawing,
    then renders with exact positioning.
    """
    is_mine = msg["is_mine"]
    sender  = msg["sender"]
    text    = msg["message"]
    ts      = msg["time"]

    # ── Layout constants ──────────────────────────────────────────────────────
    PAD_X   = 3.5    # horizontal inner padding (mm)
    PAD_Y   = 2.5    # vertical inner padding (mm)
    LINE_H  = 5.2    # line height for body text (mm)
    NAME_H  = 4.5    # row height for sender name
    TS_H    = 3.5    # row height for timestamp
    RADIUS  = 3.0    # bubble corner radius

    # ── Step 1: measure everything ────────────────────────────────────────────
    # Name
    pdf.set_font("DejaVu", "B", 8)
    name_w_inner = pdf.get_string_width(sender)

    # Timestamp
    pdf.set_font("DejaVu", "", 7)
    ts_w_inner = pdf.get_string_width(ts)

    # Wrap body text within maximum available inner width
    inner_max = max_bw - PAD_X * 2
    pdf.set_font("DejaVu", "", 9.5)
    wrapped = pdf.multi_cell(w=inner_max, h=LINE_H, text=text, dry_run=True, output="LINES")
    text_w_inner = max([pdf.get_string_width(ln) for ln in wrapped] + [0.0])

    # Bubble width = snug fit around widest element
    required_inner = max(name_w_inner, text_w_inner, ts_w_inner)
    bubble_w = min(required_inner + PAD_X * 4, max_bw)
    text_area_w = bubble_w - PAD_X * 2

    # Re-wrap with the actual (possibly narrower) text_area_w
    pdf.set_font("DejaVu", "", 9.5)
    wrapped = pdf.multi_cell(w=text_area_w, h=LINE_H, text=text, dry_run=True, output="LINES")
    text_block_h = max(len(wrapped), 1) * LINE_H

    # Total bubble height
    bubble_h = PAD_Y + NAME_H + PAD_Y + text_block_h + PAD_Y + TS_H + PAD_Y

    # ── Step 2: determine horizontal position ─────────────────────────────────
    bubble_x = (page_w - margin - bubble_w) if is_mine else margin
    text_x   = bubble_x + PAD_X

    # ── Step 3: page-break check ──────────────────────────────────────────────
    if pdf.get_y() + bubble_h + 6 > pdf.h - 14:
        pdf.add_page()

    bubble_y = pdf.get_y()

    # ── Step 4: draw background ───────────────────────────────────────────────
    fill = COLOR_MY_BUBBLE if is_mine else COLOR_OTHER_BUBBLE
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*fill)
    _rounded_rect(pdf, bubble_x, bubble_y, bubble_w, bubble_h, RADIUS)

    # ── Step 5: sender name ───────────────────────────────────────────────────
    pdf.set_text_color(*(COLOR_MY_NAME if is_mine else COLOR_OTHER_NAME))
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_xy(text_x, bubble_y + PAD_Y)
    pdf.cell(text_area_w, NAME_H, sender, align="L")

    # ── Step 6: body text (multi_cell handles wrapping automatically) ─────────
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("DejaVu", "", 9.5)
    pdf.set_xy(text_x, bubble_y + PAD_Y + NAME_H + PAD_Y)
    pdf.multi_cell(w=text_area_w, h=LINE_H, text=text, align="L")

    # ── Step 7: timestamp pinned to bottom of bubble ──────────────────────────
    ts_y = bubble_y + bubble_h - PAD_Y - TS_H
    pdf.set_text_color(*COLOR_TIMESTAMP)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_xy(text_x, ts_y)
    pdf.cell(text_area_w, TS_H, ts, align="R" if is_mine else "L")

    # ── Step 8: advance cursor below bubble ───────────────────────────────────
    pdf.set_xy(0, bubble_y + bubble_h + 4)
    pdf.set_text_color(0, 0, 0)


# ─── PDF GENERATION ────────────────────────────────────────────────────────────

def generate_pdf(messages: list[dict], output_path: str) -> int:
    """Build and save the PDF.  Returns the number of messages written."""

    pdf = WhatsAppPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)   # manual page-break control

    # ── Register fonts ────────────────────────────────────────────────────────
    pdf.add_font("DejaVu", "",  str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))

    fallback_fonts: list[str] = []

    noto_path = FONT_DIR / "NotoSansSymbols2.ttf"
    if noto_path.exists():
        pdf.add_font("NotoSymbols", "", str(noto_path))
        fallback_fonts.append("NotoSymbols")

    twemoji_path = FONT_DIR / "TwemojiMozilla.ttf"
    if twemoji_path.exists():
        pdf.add_font("Twemoji", "", str(twemoji_path))
        fallback_fonts.append("Twemoji")

    if fallback_fonts:
        pdf.set_fallback_fonts(fallback_fonts)  # tried in order for missing glyphs

    # ── Layout constants ──────────────────────────────────────────────────────
    pdf.add_page()
    PAGE_W      = pdf.w
    MARGIN      = 10.0
    BUBBLE_MAXW = (PAGE_W - MARGIN * 2) * 0.74   # bubbles span up to 74% of width

    last_date = None
    written   = 0

    for msg in messages:
        # Date separator when the day changes
        if msg["date"] != last_date:
            label = _friendly_date(msg["date"])
            if pdf.get_y() + 14 > pdf.h - 14:
                pdf.add_page()
            _draw_date_sep(pdf, label)
            last_date = msg["date"]

        _draw_bubble(pdf, msg, PAGE_W, MARGIN, BUBBLE_MAXW)
        written += 1

    pdf.output(output_path)
    return written


# ─── ENTRY POINT ───────────────────────────────────────────────────────────────

def main() -> None:
    input_path  = SCRIPT_DIR / INPUT_FILE
    output_path = str(SCRIPT_DIR / OUTPUT_FILE)

    # ① Validate input
    if not input_path.exists():
        print(f"\n❌  '{INPUT_FILE}' not found in:\n    {SCRIPT_DIR}")
        print("    Make sure the file is in the same folder as this script.")
        sys.exit(1)

    # ② Fonts
    print("\n🔤  Checking fonts …")
    ensure_fonts()

    # ③ Parse
    print(f"\n📂  Reading '{INPUT_FILE}' …")
    messages = parse_chat(str(input_path))
    print(f"💬  Parsed  : {len(messages)} messages")

    if not messages:
        print("\n⚠️  No messages were found.")
        print("    Check that the file is a valid WhatsApp export.")
        sys.exit(1)

    # ④ Generate PDF
    print("📄  Generating PDF …")
    written = generate_pdf(messages, output_path)

    # ⑤ Summary
    print(f"\n✅  Done!")
    print(f"    Messages parsed  : {len(messages)}")
    print(f"    Messages written : {written}")
    print(f"    Output file      : {output_path}\n")


if __name__ == "__main__":
    main()
