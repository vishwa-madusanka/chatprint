# chatprint

Convert a WhatsApp chat export (`.txt`) into a styled PDF that visually resembles the WhatsApp UI — chat bubbles, sender names, timestamps, date separators, and emoji glyphs, all rendered with Unicode-compatible fonts.

---

## Overview

**chatprint** reads a WhatsApp `.txt` export and generates a paginated PDF styled to match the WhatsApp interface. Your messages appear in green bubbles on the right; everyone else's in grey on the left. The only setup required is setting your name in the config block at the top of the script.

### Features

- **Both export formats supported** — new iOS/Android `[YYYY-MM-DD, HH:MM:SS] Sender: Message` and old `DD/MM/YYYY, HH:MM - Sender: Message`
- **Chat bubbles** — green (`#D9FDD3`) for your messages, grey (`#F0F0F0`) for others, with sender names and timestamps
- **Date separators** — centered pill between day groups, matching WhatsApp's UI
- **Header and footer** — dark green header bar on every page, page numbers in the footer
- **Emoji rendered as glyphs** — uses TwemojiMozilla as a fallback font; emoji appear as visible outlines, not text labels like `[crying_face]`
- **Auto-downloads fonts** — DejaVuSans, NotoSansSymbols2, and TwemojiMozilla are fetched into `./fonts/` on first run; no manual setup needed
- **Works with any WhatsApp export** — just change `MY_NAME` in the config block

---

## Requirements

- Python 3.10+
- [fpdf2](https://pypi.org/project/fpdf2/)

```bash
pip install fpdf2
```

Font files are downloaded automatically into `./fonts/` the first time you run the script. No other dependencies are required.

---

## Usage

1. **Export your WhatsApp chat**  
   In WhatsApp → open the chat → ⋮ Menu → More → Export chat → **Without media**

2. **Place the file in the script folder**  
   Rename the export to `chat.txt` and put it in the same directory as `whatsapp_to_pdf.py`

3. **Set your name in the config block**  
   Open `whatsapp_to_pdf.py` and edit line 17:
   ```python
   MY_NAME = "YourName"   # must match exactly how your name appears in the chat
   ```

4. **Run the script**
   ```bash
   python whatsapp_to_pdf.py
   ```

5. **Open the output**  
   The PDF is saved as `whatsapp_chat.pdf` in the same folder.

---

## Configuration

All user-facing settings are at the top of `whatsapp_to_pdf.py`:

| Variable | Default | Description |
|---|---|---|
| `MY_NAME` | `"Your Name"` | Your name exactly as it appears in the chat. Controls which bubbles appear on the right (green). |
| `INPUT_FILE` | `"chat.txt"` | Filename of the WhatsApp export, relative to the script. |
| `OUTPUT_FILE` | `"whatsapp_chat.pdf"` | Filename for the generated PDF. |

---

## Notes

- **Emoji rendering** — TwemojiMozilla uses the COLR/CPAL layered format. fpdf2 renders these as monochrome outlines; full colour is not supported at the PDF level.
- **Tested on** WhatsApp exports from iOS and Android, covering both date formats.
- **Fonts folder** — the `./fonts/` directory is created automatically. Add it to `.gitignore` if you are committing this project:
  ```
  fonts/
  ```
- **Multi-line messages** are handled correctly — continuation lines are merged into a single bubble.
- **Media-only lines** (stickers, images, documents) appear as `[media]` in the bubble.

---

## License

MIT
