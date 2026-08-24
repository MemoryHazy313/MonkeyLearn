"""Generic book importers for MonkeyLearn: EPUB and plain text.

Produces the same shape as the bundled data.json:
{id, title, edition, chapters:[{n,title,pw,cw}], blocks:[{k,l?,c,t}]}
"""
import hashlib
import os
import posixpath
import re
import zipfile
from html.parser import HTMLParser

# --- text cleanup (same table the PCC build uses) --------------------------

SUBS = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "--", "−": "-", "‐": "-", "‑": "-",
    "…": "...", " ": " ", " ": " ", " ": " ", "​": "",
    "×": "x", "→": "->", "←": "<-", "≠": "!=",
    "≤": "<=", "≥": ">=", "·": ".", "•": "-",
}
for _ch in "❶❷❸❹❺❻❼❽❾❿":
    SUBS[_ch] = ""
for _ch in "①②③④⑤⑥⑦⑧⑨⑩":
    SUBS[_ch] = ""


def asciify(s):
    for k, v in SUBS.items():
        s = s.replace(k, v)
    return "".join(c for c in s if c in "\n\t" or 32 <= ord(c) < 127)


def squash(s):
    return re.sub(r"\s+", " ", s.replace("\r", "")).strip()


def words(s):
    return len(s.split())


# --- generic XHTML document parser -----------------------------------------

BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre",
              "blockquote", "dt", "dd"}
DROP_TAGS = ("figure", "figcaption", "style", "script", "svg", "table")


class DocParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.buf = []
        self.tag = None
        self.dropping = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TAGS:
            self.dropping += 1
            return
        if self.dropping:
            return
        if tag == "br":
            if self.tag:
                self.buf.append("\n" if self.tag == "pre" else " ")
            return
        if tag in BLOCK_TAGS:
            # <pre> swallows nested block tags; keep collecting into it
            if self.tag == "pre":
                return
            self.flush()
            self.tag = tag

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self.tag and not self.dropping:
            self.buf.append("\n" if self.tag == "pre" else " ")

    def handle_endtag(self, tag):
        if tag in DROP_TAGS:
            self.dropping = max(0, self.dropping - 1)
            return
        if self.dropping:
            return
        if tag == self.tag:
            self.flush()

    def handle_data(self, data):
        if not self.dropping and self.tag is not None:
            self.buf.append(data)

    def flush(self):
        if self.tag is None:
            return
        raw = "".join(self.buf)
        tag = self.tag
        self.buf, self.tag = [], None
        if tag == "pre":
            text = "\n".join(l.rstrip() for l in raw.split("\n")).strip("\n")
            if text.strip():
                self.blocks.append({"k": "c", "t": text})
            return
        text = squash(raw)
        if not text:
            return
        if tag[0] == "h" and tag[1:].isdigit():
            self.blocks.append({"k": "h", "l": min(int(tag[1:]), 3), "t": text})
        elif tag == "li":
            self.blocks.append({"k": "p", "t": "- " + text})
        else:
            self.blocks.append({"k": "p", "t": text})


# --- EPUB ------------------------------------------------------------------

def _toc_titles(z, opf_dir, manifest):
    """Best-effort map of content-file basename -> toc title."""
    titles = {}

    def note(src, label):
        base = posixpath.basename(src.split("#")[0])
        label = squash(asciify(label))
        if base and label and base not in titles:
            titles[base] = label

    for href, mt, props in manifest.values():
        path = posixpath.normpath(posixpath.join(opf_dir, href))
        try:
            doc = z.read(path).decode("utf-8", "replace")
        except KeyError:
            continue
        if "dtbncx" in mt:  # EPUB2 toc.ncx
            for m in re.finditer(
                    r"<navLabel>\s*<text>(.*?)</text>.*?<content[^>]*src=\"([^\"]+)\"",
                    doc, re.S):
                note(m.group(2), re.sub(r"<[^>]+>", " ", m.group(1)))
        elif "nav" in props:  # EPUB3 nav doc
            m = re.search(r"<nav[^>]*epub:type=\"toc\".*?</nav>", doc, re.S)
            for a in re.finditer(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                                 m.group(0) if m else doc, re.S):
                note(a.group(1), re.sub(r"<[^>]+>", " ", a.group(2)))
    return titles


def parse_epub(path):
    z = zipfile.ZipFile(path)
    container = z.read("META-INF/container.xml").decode("utf-8", "replace")
    opf_path = re.search(r"full-path=\"([^\"]+)\"", container).group(1)
    opf = z.read(opf_path).decode("utf-8", "replace")
    opf_dir = posixpath.dirname(opf_path)

    book_title = None
    m = re.search(r"<dc:title[^>]*>(.*?)</dc:title>", opf, re.S)
    if m:
        book_title = squash(asciify(re.sub(r"<[^>]+>", " ", m.group(1))))

    manifest = {}
    for item in re.finditer(r"<item\b[^>]*>", opf):
        tag = item.group(0)
        gid = re.search(r"\bid=\"([^\"]+)\"", tag)
        href = re.search(r"\bhref=\"([^\"]+)\"", tag)
        mt = re.search(r"media-type=\"([^\"]+)\"", tag)
        props = re.search(r"properties=\"([^\"]+)\"", tag)
        if gid and href:
            manifest[gid.group(1)] = (href.group(1),
                                      mt.group(1) if mt else "",
                                      props.group(1) if props else "")
    spine = re.findall(r"<itemref\b[^>]*idref=\"([^\"]+)\"", opf)
    titles = _toc_titles(z, opf_dir, manifest)

    chapters, blocks = [], []
    for idref in spine:
        if idref not in manifest:
            continue
        href, mt, _ = manifest[idref]
        if "html" not in mt:
            continue
        full = posixpath.normpath(posixpath.join(opf_dir, href))
        try:
            doc = z.read(full).decode("utf-8", "replace")
        except KeyError:
            continue
        p = DocParser()
        p.feed(doc)
        p.flush()
        bs = []
        for b in p.blocks:
            t = asciify(b["t"])
            if t.strip():
                bs.append(dict(b, t=t))
        total = sum(words(b["t"]) for b in bs if b["k"] != "h")
        if total < 20:
            continue
        title = titles.get(posixpath.basename(full)) or next(
            (b["t"] for b in bs if b["k"] == "h"), None)
        if title is None and chapters:
            cid = chapters[-1]["n"]  # untitled continuation: same chapter
        else:
            cid = len(chapters) + 1
            chapters.append({"n": cid, "title": title or "Part %d" % cid,
                             "pw": 0, "cw": 0})
        ch = chapters[cid - 1]
        for b in bs:
            blocks.append({"k": b["k"], "c": cid, "t": b["t"],
                           **({"l": b["l"]} if b["k"] == "h" else {})})
            if b["k"] == "p":
                ch["pw"] += words(b["t"])
            elif b["k"] == "c":
                ch["cw"] += words(b["t"])
    if not chapters:
        raise ValueError("No readable chapters found in this EPUB.")
    return {"title": book_title or os.path.splitext(os.path.basename(path))[0],
            "edition": "", "chapters": chapters, "blocks": blocks}


# --- plain text ------------------------------------------------------------

CHAPTER_RE = re.compile(r"^(chapter|part|book|section)\b", re.I)


def parse_txt(path):
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", "replace")
    text = asciify(text.replace("\r\n", "\n").replace("\r", "\n"))
    paras = [squash(p) for p in re.split(r"\n\s*\n", text)]
    paras = [p for p in paras if p]

    def is_heading(p):
        return len(p) <= 60 and not re.search(r"[.!?,;:]$", p) and words(p) <= 8

    breaks = [i for i, p in enumerate(paras) if is_heading(p) and CHAPTER_RE.match(p)]
    chapters, blocks = [], []

    def new_chapter(title):
        chapters.append({"n": len(chapters) + 1, "title": title, "pw": 0, "cw": 0})
        return chapters[-1]

    if len(breaks) >= 2:
        ch = None
        for i, p in enumerate(paras):
            if i in set(breaks):
                ch = new_chapter(p)
                continue
            if ch is None:
                ch = new_chapter("Beginning")
            k = "h" if is_heading(p) else "p"
            blocks.append({"k": k, "c": ch["n"], "t": p,
                           **({"l": 2} if k == "h" else {})})
            if k == "p":
                ch["pw"] += words(p)
    else:
        ch, wsum = None, 0
        for p in paras:
            if ch is None or wsum >= 4000:
                ch = new_chapter("Part %d" % (len(chapters) + 1))
                wsum = 0
            k = "h" if is_heading(p) else "p"
            blocks.append({"k": k, "c": ch["n"], "t": p,
                           **({"l": 2} if k == "h" else {})})
            if k == "p":
                ch["pw"] += words(p)
                wsum += words(p)
    if not blocks:
        raise ValueError("This text file appears to be empty.")
    return {"title": os.path.splitext(os.path.basename(path))[0],
            "edition": "", "chapters": chapters, "blocks": blocks}


# --- entry -----------------------------------------------------------------

def parse_book(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".epub":
        data = parse_epub(path)
    elif ext in (".txt", ".md"):
        data = parse_txt(path)
    else:
        raise ValueError("Unsupported file type: %s (use .epub or .txt)" % ext)
    slug = re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:40]
    with open(path, "rb") as f:
        digest = hashlib.md5(f.read()).hexdigest()[:6]
    data["id"] = slug + "-" + digest
    return data
