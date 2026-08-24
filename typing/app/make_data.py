"""Parse the EPUB into data.json for the Copywork desktop app.

Reuses the parser from typing/build.py; emits one ordered stream of blocks
(headings, prose, code) plus chapter metadata.
"""
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from build import read_chapter, asciify, find_epub


def main():
    z = zipfile.ZipFile(find_epub())
    names = sorted(n for n in z.namelist()
                   if re.fullmatch(r"OEBPS/c\d\d\.xhtml", n))
    chapters, blocks = [], []
    for name in names:
        cid = int(re.search(r"c(\d\d)", name).group(1))
        bs = read_chapter(z, name)
        title = next((b["text"] for b in bs if b["kind"] == "head"),
                     "Chapter %d" % cid)
        title = re.sub(r"^\d+\s+", "", asciify(title))
        pw = cw = 0
        for b in bs:
            t = asciify(b["text"])
            if not t.strip():
                continue
            if b["kind"] == "head":
                blocks.append({"k": "h", "l": b.get("level", 2), "c": cid,
                               "t": re.sub(r"^\d+\s+", "", t)})
            elif b["kind"] == "prose":
                blocks.append({"k": "p", "c": cid, "t": t})
                pw += len(t.split())
            else:
                blocks.append({"k": "c", "c": cid, "t": t})
                cw += len(t.split())
        chapters.append({"n": cid, "title": title, "pw": pw, "cw": cw})

    out = {"title": "Python Crash Course", "edition": "3rd edition",
           "chapters": chapters, "blocks": blocks}
    path = os.path.join(HERE, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=True, separators=(",", ":"))

    words = sum(c["pw"] + c["cw"] for c in chapters)
    print("%d chapters, %d blocks, %d words -> %s"
          % (len(chapters), len(blocks), words, path))


if __name__ == "__main__":
    main()
