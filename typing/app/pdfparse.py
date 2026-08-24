"""PDF importer for MonkeyLearn.

PDFs are layout, not structure, so this module works to recover structure:
- chapters from the PDF's own outline (bookmarks), picking the outline depth
  that looks like a chapter list; text-heuristic fallback otherwise
- running headers/footers removed by fingerprinting lines that repeat across
  many pages; standalone page numbers dropped
- hard-wrapped lines rebuilt into paragraphs, hyphenated words rejoined
- scanned (image-only) PDFs rejected with a clear message instead of garbage

Output matches bookparse: {title, edition, chapters:[{n,title,pw,cw}],
blocks:[{k,l?,c,t}], notes:[...]}.
"""
import os
import re
import statistics
from collections import Counter

from pypdf import PdfReader


PAGENUM_RE = re.compile(r"^(page\s+)?[0-9]{1,4}$|^[ivxlcdm]{1,7}$", re.I)
SENT_END_RE = re.compile(r"[.!?:][\"')\]]?$")
CHAPTER_RE = re.compile(r"^(chapter|part|book|section)\b", re.I)


def _norm(line):
    """Fingerprint for repeated-line detection: digits wildcarded."""
    return re.sub(r"\d+", "#", line.strip()).lower()


def _page_lines(reader, notes):
    pages = []
    for p in reader.pages:
        try:
            text = p.extract_text() or ""
        except Exception:
            text = ""
        pages.append([l.rstrip() for l in text.split("\n")])
    total_words = sum(len(l.split()) for lines in pages for l in lines)
    if total_words < 100:
        raise ValueError(
            "This PDF has no usable text layer - it is probably scanned "
            "images. Run OCR on it first (e.g. with OCRmyPDF), then import.")
    return pages


def _strip_furniture(pages, notes):
    """Remove running headers/footers and page numbers."""
    top, bottom = Counter(), Counter()
    for lines in pages:
        nz = [l for l in lines if l.strip()]
        if not nz:
            continue
        for l in nz[:2]:
            top[_norm(l)] += 1
        for l in nz[-2:]:
            bottom[_norm(l)] += 1
    n = max(1, len(pages))
    threshold = max(4, int(n * 0.3))
    repeated = {k for k, v in (top + bottom).items()
                if v >= threshold and k}
    stripped = 0
    out = []
    for lines in pages:
        nz_idx = [i for i, l in enumerate(lines) if l.strip()]
        edge = set(nz_idx[:2] + nz_idx[-2:])
        kept = []
        for i, l in enumerate(lines):
            s = l.strip()
            if i in edge and s and (_norm(l) in repeated or PAGENUM_RE.match(s)):
                stripped += 1
                continue
            kept.append(l)
        out.append(kept)
    if stripped:
        notes.append("removed %d header/footer/page-number lines" % stripped)
    return out


def _paragraphs(lines):
    """Rebuild paragraphs from hard-wrapped lines."""
    lengths = [len(l.strip()) for l in lines if l.strip()]
    med = statistics.median(lengths) if lengths else 60
    short = med * 0.7
    paras, cur = [], []

    def close():
        if cur:
            paras.append(" ".join(cur))
            cur.clear()

    for raw in lines:
        l = raw.strip()
        if not l:
            close()
            continue
        if cur and cur[-1].endswith("-") and l[:1].islower():
            cur[-1] = cur[-1][:-1] + l  # rejoin hyphenated word
        else:
            cur.append(l)
        # a sentence that ends well short of the text width ends the paragraph
        if SENT_END_RE.search(l) and len(l) < short:
            close()
    close()
    return paras


def _flatten_outline(outline, depth=0):
    flat = []
    for item in outline:
        if isinstance(item, list):
            flat.extend(_flatten_outline(item, depth + 1))
        else:
            flat.append((depth, item))
    return flat


def _outline_chapters(reader, npages, notes):
    """Chapter list (start_page, title) from bookmarks, or None.

    Starts with top-level bookmarks and pulls in deeper levels while any
    single entry still spans a big slice of the book (a "Part I" bookmark
    with the real chapters nested under it).
    """
    try:
        flat = _flatten_outline(reader.outline)
    except Exception:
        return None
    entries = []
    for depth, item in flat:
        try:
            page = reader.get_destination_page_number(item)
            title = str(item.title or "").strip()
        except Exception:
            continue
        if title and page is not None:
            entries.append((depth, page, title))
    if not entries:
        return None
    max_depth = max(d for d, _, _ in entries)
    big = max(10, int(npages * 0.25))
    for depth in range(max_depth + 1):
        seen, chapters = set(), []
        for d, page, title in sorted(entries, key=lambda e: (e[1], e[0])):
            if d <= depth and page not in seen:
                seen.add(page)
                chapters.append((page, title))
        if len(chapters) < 3 or len(chapters) > 200:
            continue
        spans = [b - a for (a, _), (b, _) in zip(chapters, chapters[1:])]
        spans.append(npages - chapters[-1][0])
        if max(spans) <= big or depth == max_depth:
            notes.append("chapters from the PDF outline")
            return chapters
    return None


def parse_pdf(path):
    notes = ["PDF import is best-effort - skim the first chapters to check"]
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError("This PDF is password-protected.")

    pages = _strip_furniture(_page_lines(reader, notes), notes)
    outline = _outline_chapters(reader, len(pages), notes)

    title = None
    try:
        title = (reader.metadata.title or "").strip() or None
    except Exception:
        pass
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]

    from bookparse import asciify, squash, words  # shared cleanup

    chapters, blocks = [], []

    def add_chapter(name):
        chapters.append({"n": len(chapters) + 1,
                         "title": squash(asciify(name))[:120] or
                                  "Part %d" % (len(chapters) + 1),
                         "pw": 0, "cw": 0})
        return chapters[-1]

    def add_paras(ch, paras, skip_title=None):
        skip = _norm(skip_title) if skip_title else None
        for p in paras:
            t = squash(asciify(p))
            if not t:
                continue
            # drop the chapter-title line the page repeats under the heading
            if skip and _norm(t) == skip:
                skip = None
                continue
            w = words(t)
            if w == 0:
                continue
            if len(t) <= 60 and not SENT_END_RE.search(t) and w <= 8:
                blocks.append({"k": "h", "l": 2, "c": ch["n"], "t": t})
            else:
                blocks.append({"k": "p", "c": ch["n"], "t": t})
                ch["pw"] += w

    if outline:
        # front matter before the first bookmarked chapter is skipped
        bounds = [p for p, _ in outline] + [len(pages)]
        skipped = sum(len(l.split()) for lines in pages[:bounds[0]]
                      for l in lines)
        if skipped > 200:
            notes.append("skipped ~%d words of front matter" % skipped)
        for i, (page, name) in enumerate(outline):
            lines = [l for pl in pages[bounds[i]:bounds[i + 1]] for l in pl]
            ch = add_chapter(name)
            add_paras(ch, _paragraphs(lines), skip_title=name)
    else:
        notes.append("no usable PDF outline - chapters guessed from the text")
        all_lines = [l for pl in pages for l in pl]
        paras = _paragraphs(all_lines)
        marks = [i for i, p in enumerate(paras)
                 if CHAPTER_RE.match(p.strip()) and len(p) <= 60]
        if len(marks) >= 2:
            if marks[0] != 0:
                marks.insert(0, 0)
            marks.append(len(paras))
            for i in range(len(marks) - 1):
                seg = paras[marks[i]:marks[i + 1]]
                name = seg[0] if CHAPTER_RE.match(seg[0].strip()) else "Beginning"
                ch = add_chapter(name)
                add_paras(ch, seg[1:] if name == seg[0] else seg)
        else:
            ch, wsum = None, 0
            for p in paras:
                if ch is None or wsum >= 4000:
                    ch = add_chapter("Part %d" % (len(chapters) + 1))
                    wsum = 0
                before = ch["pw"]
                add_paras(ch, [p])
                wsum += ch["pw"] - before

    kept = [c for c in chapters if c["pw"] > 0]
    renum = {c["n"]: i for i, c in enumerate(kept, 1)}
    blocks = [dict(b, c=renum[b["c"]]) for b in blocks if b["c"] in renum]
    for c in kept:
        c["n"] = renum[c["n"]]
    chapters = kept
    if not chapters:
        raise ValueError("No readable text found in this PDF.")
    return {"title": squash(asciify(title)), "edition": "",
            "chapters": chapters, "blocks": blocks, "notes": notes}
