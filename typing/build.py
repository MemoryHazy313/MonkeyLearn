"""Slice the local EPUB into MonkeyType-sized custom-text chunks.

Reads the .epub sitting next to this folder and writes paste-ready .txt files
into typing/out/. Nothing leaves the machine.
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# --- text cleanup ---------------------------------------------------------

SUBS = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "--", "−": "-", "‐": "-", "‑": "-",
    "…": "...", " ": " ", " ": " ", " ": " ", "​": "",
    "×": "x", "→": "->", "←": "<-", "≠": "!=",
    "≤": "<=", "≥": ">=", "·": ".", "•": "-",
}
# circled digits are used as callout markers inside code listings
for ch in "❶❷❸❹❺❻❼❽❾❿":
    SUBS[ch] = ""
for ch in "①②③④⑤⑥⑦⑧⑨⑩":
    SUBS[ch] = ""


def asciify(s, enabled=True):
    if not enabled:
        return s
    for k, v in SUBS.items():
        s = s.replace(k, v)
    return "".join(c for c in s if c in "\n\t" or 32 <= ord(c) < 127)


def squash(s):
    return re.sub(r"\s+", " ", s.replace("\r", "")).strip()


# --- epub parsing ---------------------------------------------------------

SKIP_P_CLASSES = {"CodeLabel", "Caption", "FigureCaption"}
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "li", "pre", "blockquote"}
DROP_TAGS = ("figure", "img", "figcaption", "style", "script")


class ChapterParser(HTMLParser):
    """Flattens a chapter's XHTML into an ordered list of typed blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.buf = []
        self.tag = None
        self.cls = ""
        self.dropping = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in DROP_TAGS:
            self.dropping += 1
            return
        if self.dropping:
            return
        if tag == "br" and self.tag:
            self.buf.append(" ")
            return
        if tag in BLOCK_TAGS:
            self.flush()
            self.tag = tag
            self.cls = a.get("class", "")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self.tag and not self.dropping:
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag in DROP_TAGS:
            self.dropping = max(0, self.dropping - 1)
            return
        if self.dropping:
            return
        if tag == self.tag:
            self.flush()

    def handle_data(self, data):
        if self.dropping or self.tag is None:
            return
        self.buf.append(data)

    def flush(self):
        if self.tag is None:
            return
        raw = "".join(self.buf)
        tag, cls = self.tag, self.cls
        self.buf, self.tag, self.cls = [], None, ""
        if cls in SKIP_P_CLASSES:
            return
        if tag == "pre":
            text = "\n".join(l.rstrip() for l in raw.split("\n")).strip("\n")
            if text.strip():
                self.blocks.append({"kind": "code", "text": text})
            return
        text = squash(raw)
        if not text:
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self.blocks.append({"kind": "head", "level": int(tag[1]), "text": text})
        elif tag == "li":
            self.blocks.append({"kind": "prose", "text": "- " + text})
        else:
            self.blocks.append({"kind": "prose", "text": text})


def read_chapter(z, name):
    p = ChapterParser()
    p.feed(z.read(name).decode("utf-8", "replace"))
    p.flush()
    return p.blocks


# --- chunking -------------------------------------------------------------

SENT = re.compile(r"(?<=[.!?:])\s+(?=[\"'(A-Z0-9])")


def split_sentences(text):
    return [s for s in (p.strip() for p in SENT.split(text)) if s]


def chunk_prose(paragraphs, target):
    """Pack sentences into ~target-word chunks, never splitting a sentence."""
    out, cur, n = [], [], 0
    for para in paragraphs:
        for sent in split_sentences(para):
            w = len(sent.split())
            if cur and n + w > target:
                out.append(" ".join(cur))
                cur, n = [], 0
            cur.append(sent)
            n += w
    if cur:
        out.append(" ".join(cur))
    return out


def chunk_code(text, max_lines):
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return [text]
    out, cur = [], []
    for line in lines:
        cur.append(line)
        if len(cur) >= max_lines and not line.strip():
            out.append("\n".join(cur).strip("\n"))
            cur = []
    if cur:
        out.append("\n".join(cur).strip("\n"))
    return [c for c in out if c.strip()]


def escape_code(text):
    """MonkeyType only keeps layout via literal backslash-n / backslash-t."""
    return text.replace("\\", "\\\\").replace("\t", "    ").replace("\n", "\\n")


# --- build ----------------------------------------------------------------

def find_epub():
    for f in sorted(os.listdir(ROOT)):
        if f.lower().endswith(".epub"):
            return os.path.join(ROOT, f)
    sys.exit("No .epub found in " + ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", type=int, default=110, help="target words per prose chunk")
    ap.add_argument("--code-lines", type=int, default=14, help="max lines per code chunk")
    ap.add_argument("--mode", choices=["both", "prose", "code"], default="both")
    ap.add_argument("--break-heading", type=int, default=2, metavar="LEVEL",
                    help="end a chunk at headings this level or higher (1=chapter, "
                         "2=section, 3=subsection). Lower means bigger chunks.")
    ap.add_argument("--min-words", type=int, default=40,
                    help="prose runs shorter than this get glued onto the "
                         "previous prose chunk instead of becoming their own")
    ap.add_argument("--keep-unicode", action="store_true", help="keep curly quotes / dashes")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    args = ap.parse_args()

    epub = find_epub()
    z = zipfile.ZipFile(epub)
    chapters = sorted(n for n in z.namelist()
                      if re.fullmatch(r"OEBPS/c\d\d\.xhtml", n))

    os.makedirs(args.out, exist_ok=True)
    # drop chunks from a previous build so old numbering can't linger
    for d in sorted(os.listdir(args.out)):
        if re.fullmatch(r"ch\d\d", d):
            shutil.rmtree(os.path.join(args.out, d))
    index = []
    total_words = 0

    for name in chapters:
        cid = re.search(r"c(\d\d)", name).group(1)
        blocks = read_chapter(z, name)
        title = next((b["text"] for b in blocks if b["kind"] == "head"), "Chapter " + cid)
        title = asciify(title, not args.keep_unicode)

        cdir = os.path.join(args.out, "ch" + cid)
        os.makedirs(cdir, exist_ok=True)
        rawdir = os.path.join(cdir, "raw")

        state = {"section": title, "pending": [], "seq": 0}
        entries = []

        def emit_prose():
            nonlocal total_words
            if not state["pending"]:
                return
            for text in chunk_prose(state["pending"], args.words):
                text = asciify(text, not args.keep_unicode)
                if not text.strip():
                    continue
                wc = len(text.split())
                prev = entries[-1] if entries else None
                if wc < args.min_words and prev and prev["kind"] == "prose":
                    # too short to be its own test - glue it to the previous one
                    path = os.path.join(args.out, prev["file"])
                    with open(path, encoding="utf-8") as f:
                        head = f.read().rstrip("\n")
                    with open(path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(head + " " + text + "\n")
                    prev["words"] += wc
                    total_words += wc
                    continue
                state["seq"] += 1
                fn = "ch%s_%03d.txt" % (cid, state["seq"])
                with open(os.path.join(cdir, fn), "w", encoding="utf-8", newline="\n") as f:
                    f.write(text + "\n")
                total_words += wc
                entries.append({"file": "ch%s/%s" % (cid, fn), "kind": "prose",
                                "chapter": int(cid), "title": title,
                                "section": state["section"], "words": wc})
            state["pending"] = []

        for b in blocks:
            if b["kind"] == "head":
                # minor headings only relabel; major ones end a typing chunk
                if args.mode != "code" and b.get("level", 2) <= args.break_heading:
                    emit_prose()
                state["section"] = asciify(b["text"], not args.keep_unicode)
            elif b["kind"] == "prose":
                if args.mode != "code":
                    state["pending"].append(b["text"])
            elif b["kind"] == "code":
                if args.mode == "prose":
                    # code is not emitted, so prose reads straight through it
                    continue
                emit_prose()
                for piece in chunk_code(b["text"], args.code_lines):
                    piece = asciify(piece, not args.keep_unicode)
                    if not piece.strip():
                        continue
                    state["seq"] += 1
                    fn = "ch%s_%03d.code.txt" % (cid, state["seq"])
                    with open(os.path.join(cdir, fn), "w", encoding="utf-8", newline="\n") as f:
                        f.write(escape_code(piece))
                    os.makedirs(rawdir, exist_ok=True)
                    with open(os.path.join(rawdir, fn), "w", encoding="utf-8", newline="\n") as f:
                        f.write(piece + "\n")
                    wc = len(piece.split())
                    total_words += wc
                    entries.append({"file": "ch%s/%s" % (cid, fn), "kind": "code",
                                    "chapter": int(cid), "title": title,
                                    "section": state["section"], "words": wc})
        emit_prose()
        index.extend(entries)
        print("ch%s  %-45s %3d chunks" % (cid, title[:45], len(entries)))

    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"source": os.path.basename(epub), "settings": vars(args),
                   "chunks": index}, f, indent=1)

    print("")
    print("%d chunks, ~%d words total -> %s" % (len(index), total_words, args.out))


if __name__ == "__main__":
    main()
