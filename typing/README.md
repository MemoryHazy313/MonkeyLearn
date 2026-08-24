# MonkeyLearn - typing through books on MonkeyType

The app is `MonkeyLearn.exe` in the book folder. Double-click it, no terminal needed.
It holds your books, hands you passages, and keeps a bookmark per book; the
typing itself happens on the official monkeytype.com.

Python Crash Course is built in. **Add a book** on the shelf screen imports any
EPUB or TXT file (parsed locally, stored in `%APPDATA%\MonkeyLearn\books`).

## Using it

1. Open `MonkeyLearn.exe`. Press **Continue** (auto-copies the current passage).
2. On monkeytype.com: mode `custom` -> wrench icon -> paste -> uncheck **random**,
   word count `all` -> save. Type it.
3. Back in the app, click **Done, next** (or press Enter) - progress is recorded
   and the next passage is already on your clipboard.

Passages containing line breaks (code) are copied with them written as literal `\n`; tick
**replace control characters** in MonkeyType's custom text box so line breaks
come back. The app reminds you whenever a passage needs it.

The window is drawn by the app itself (retro Windows style): drag it by the
blue title bar, resize with the grip in the bottom-right corner, and use the
title bar buttons to minimize, maximize, or close.

Settings in the library view: passage length (Short 60 / Medium 150 /
Long 300 / XL 600 / Whole chapter, or type a custom word count) and content
(Prose / Code /
Everything - hidden for books with no code). Passages are continuous runs of
the book, prose and code in printed order, breaking only at the word target or
a chapter's end; short chapter tails are folded into the previous passage.
Changing settings re-slices on the fly without losing your place. Click any
chapter row to jump there.

Shortcuts on the passage view: `C` copy, `Enter` done + next,
arrow keys back/skip, `Esc` contents.

Progress lives in `%APPDATA%\MonkeyLearn\state.json` - it survives moving or
rebuilding the exe. Delete that file to start over.

## Rebuilding the app (only after changing its code)

Sources are in `typing/app/` (`main.py`, `ui.html`, `make_data.py`).

```
python typing/app/make_data.py
cd typing/app
python -m PyInstaller --noconfirm --onefile --windowed ^
    --add-data "ui.html;." --add-data "data.json;." -n MonkeyLearn main.py
copy dist\MonkeyLearn.exe ..\..\MonkeyLearn.exe
```

Needs `pip install pywebview pyperclip pyinstaller` (already installed).
If Windows Defender ever flags the one-file exe, rebuild with `--onedir`
instead and use the exe inside the resulting folder.

## Legacy terminal workflow

`typing/build.py` and `typing/mt.py` are the old clipboard-feeder scripts
(`python typing/mt.py next` etc.). They still work and share the same EPUB
parser, but the app has replaced them.

## Repository note

The book files (EPUB/PDF) and everything derived from their text
(typing/app/data.json, typing/out/) are intentionally not in the repository.
On a fresh clone, place the EPUB next to the typing/ folder and run
python typing/app/make_data.py before building the app.
