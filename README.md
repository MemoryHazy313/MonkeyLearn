# MonkeyLearn

Type your way through real books on [MonkeyType](https://monkeytype.com) - and actually
learn something while practicing.

MonkeyLearn is a small Windows desktop app that holds your books, slices them into
typing-sized passages, and feeds them to your clipboard one **Copy** at a time. You paste
each passage into MonkeyType's custom text mode and type; the app keeps your bookmark,
per-chapter progress, and shelf of books. The typing itself always happens on the real
MonkeyType site - this is a companion, not a typing engine.

The interface is a deliberate love letter to Windows 98/XP: beveled buttons, engraved
group boxes, segmented progress bars, a gradient title bar, and a PictoChat-style frame
around the text you are about to type.

![Library view](docs/library.png)

![Bookshelf](docs/shelf.png)

## How to use it

1. Start `MonkeyLearn.exe`. Your bookshelf opens; click a book (or **Add Book...** to
   import your own - EPUB, PDF, and TXT are supported, parsed entirely on your machine).
2. Pick a passage length: Short (60 words), Medium (150), Long (300), XL (600),
   Whole chapter, or a custom word count. Pick content: Prose, Code, or Everything
   (the toggle hides itself for books with no code).
3. Press **Begin**. The first passage is already on your clipboard.
4. On monkeytype.com: mode `custom` -> wrench icon -> paste -> uncheck **random**, set
   word count to `all` -> save. Type it.
5. Back in the app, **Done, next** (or Enter) records your progress and puts the next
   passage on the clipboard. That is the whole loop.

If a passage contains line breaks (code listings), it is copied with them written as
literal `\n` and the app shows a reminder: tick **replace control characters** in
MonkeyType's custom text box and the line breaks come back. Plain prose copies clean.

Shortcuts: `C` copy again, `Enter` done + next, arrow keys back/skip, `Esc` contents.
The window is drawn by the app itself - drag it by the blue title bar, resize with the
grip in the bottom-right corner.

## How it works

A book is imported once into a stream of blocks (headings, prose paragraphs, code
listings) and stored as JSON in `%APPDATA%\MonkeyLearn\books\`:

- **EPUB**: the app reads the book's own manifest for reading order and its table of
  contents for chapter names. Figures, captions, and tables are dropped; typographic
  characters are normalized to plain ASCII so every character is typeable.
- **PDF**: chapters come from the PDF's own outline (bookmarks), drilling past
  "Part I"-style groupings to the real chapter level; running headers, footers, and
  page numbers are stripped by detecting lines that repeat across pages; hard-wrapped
  lines are rebuilt into paragraphs and hyphenated words rejoined. Scanned PDFs
  without a text layer are rejected with a pointer to OCR tools rather than
  imported as garbage. Extraction quality still varies with how the PDF was made -
  prefer EPUB when you have both.
- **TXT**: paragraphs split on blank lines; lines like "Chapter 5" become chapter
  breaks, and books without them are cut into navigable parts.

Passages are then built live, on every settings change: whole sentences (and code
blocks) are packed in book order up to your word target, breaking only at a sentence end
or a chapter end, with short chapter tails folded into the previous passage. Your
bookmark is stored as a position in the book rather than a passage number, so changing
passage length never loses your place.

Progress lives in `%APPDATA%\MonkeyLearn\state.json`. Nothing ever leaves your computer.

## Building from source

Requires Python 3.12+ on Windows with WebView2 (preinstalled on Windows 11).

```
pip install pywebview pyperclip pypdf pyinstaller
cd typing/app
python make_data.py        # builds the bundled starter book (see note)
python main.py             # run from source
pyinstaller --noconfirm --onefile --windowed --add-data "ui.html;." --add-data "data.json;." -n MonkeyLearn main.py
```

Note: no book text ships in this repository. `make_data.py` generates the bundled
starter book from an EPUB you place in the repository root; any books you actually
read are imported through the app's own **Add Book...** dialog.

## Running on Linux

The code is portable (config lives in `~/.config/MonkeyLearn` on Linux,
`%APPDATA%\MonkeyLearn` on Windows), but so far it has only been tested on
Windows 11 - reports welcome. To run from source on Linux you need:

- GTK WebKit for pywebview: `sudo apt install python3-gi gir1.2-webkit2-4.1`
  (or use the Qt backend: `pip install pywebview[qt]`)
- A clipboard helper for pyperclip: `sudo apt install xclip` (X11) or
  `wl-clipboard` (Wayland)
- Then: `pip install pywebview pyperclip pypdf` and `python3 typing/app/main.py`

The app draws its own window frame; if your window manager handles frameless
windows poorly, set `MONKEYLEARN_SYSTEM_FRAME=1` to use the normal OS frame
instead. A Linux binary can be built with PyInstaller on a Linux machine using
the same command as the Windows build.

## Roadmap

This README grows with the project.

- [ ] Make the bundled starter book optional so the app builds with an empty shelf
- [ ] Packaged releases
- [ ] Verify and polish Linux support (currently untested)
