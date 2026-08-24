"""Feed the next typing chunk to the clipboard, and remember where you are.

  python typing/mt.py next          copy the next chunk, advance
  python typing/mt.py again         re-copy the current chunk
  python typing/mt.py back          step back one chunk
  python typing/mt.py status        where you are, how much is left
  python typing/mt.py goto 9        jump to chapter 9
  python typing/mt.py goto ch09/ch09_014.txt
  python typing/mt.py mode prose    only prose | code | both
  python typing/mt.py toc           chapter list with progress
  python typing/mt.py show          print the current chunk instead of copying
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
INDEX = os.path.join(OUT, "index.json")
STATE = os.path.join(HERE, "state.json")


def load_index():
    if not os.path.exists(INDEX):
        sys.exit("No index.json - run: python typing/build.py")
    with open(INDEX, encoding="utf-8") as f:
        return json.load(f)["chunks"]


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {"pos": 0, "mode": "both", "typed": 0}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)


def view(chunks, mode):
    if mode == "both":
        return chunks
    return [c for c in chunks if c["kind"] == mode]


def to_clipboard(text):
    try:
        subprocess.run(["clip"], input=text.encode("utf-8"),
                       check=True, shell=True)
        return True
    except Exception:
        return False


def render(c, st, total, copied):
    body = open(os.path.join(OUT, c["file"]), encoding="utf-8").read().rstrip("\n")
    pct = 100.0 * (st["pos"]) / total if total else 0
    print("ch%02d  %s" % (c["chapter"], c["title"]))
    print("      %s" % c["section"])
    kind = "CODE  (tick 'replace control characters' in MonkeyType)" if c["kind"] == "code" else "prose"
    print("      %s  %d words  |  %d/%d  %.1f%%" % (kind, c["words"], st["pos"], total, pct))
    print("      %s" % c["file"])
    print("      %s" % ("copied to clipboard - paste into MonkeyType"
                        if copied else "clipboard failed; open the file above"))
    return body


def cmd_next(chunks, st, step=1, advance=True):
    v = view(chunks, st["mode"])
    if not v:
        sys.exit("No chunks match mode " + st["mode"])
    st["pos"] = max(0, min(len(v) - 1, st["pos"] + step))
    c = v[st["pos"]]
    body = render(c, st, len(v), to_clipboard(open(os.path.join(OUT, c["file"]), encoding="utf-8").read().rstrip("\n")))
    if advance:
        st["typed"] = max(st["typed"], st["pos"])
    save_state(st)
    return body


def cmd_status(chunks, st):
    v = view(chunks, st["mode"])
    pos = min(st["pos"], len(v) - 1)
    c = v[pos]
    done_words = sum(x["words"] for x in v[:pos])
    left_words = sum(x["words"] for x in v[pos:])
    print("mode      %s" % st["mode"])
    print("position  %d / %d   (ch%02d %s)" % (pos, len(v), c["chapter"], c["title"]))
    print("section    %s" % c["section"])
    print("typed     ~%d words" % done_words)
    print("remaining ~%d words  (~%d min at 60 wpm)" % (left_words, left_words // 60))


def cmd_toc(chunks, st):
    v = view(chunks, st["mode"])
    pos = min(st["pos"], len(v) - 1)
    seen = {}
    for i, c in enumerate(v):
        d = seen.setdefault(c["chapter"], {"title": c["title"], "n": 0, "first": i, "words": 0})
        d["n"] += 1
        d["words"] += c["words"]
    for ch in sorted(seen):
        d = seen[ch]
        mark = "->" if v[pos]["chapter"] == ch else "  "
        print("%s ch%02d  %-42s %4d chunks  ~%5d words" %
              (mark, ch, d["title"][:42], d["n"], d["words"]))


def cmd_goto(chunks, st, target):
    v = view(chunks, st["mode"])
    if target.isdigit():
        ch = int(target)
        for i, c in enumerate(v):
            if c["chapter"] == ch:
                st["pos"] = i
                save_state(st)
                print("jumped to ch%02d %s" % (c["chapter"], c["title"]))
                return
        sys.exit("chapter %d not found in mode %s" % (ch, st["mode"]))
    t = target.replace("\\", "/")
    for i, c in enumerate(v):
        if c["file"].endswith(t) or c["file"] == t:
            st["pos"] = i
            save_state(st)
            print("jumped to %s" % c["file"])
            return
    sys.exit("no chunk matching " + target)


def main():
    chunks = load_index()
    st = load_state()
    argv = sys.argv[1:] or ["next"]
    cmd = argv[0]

    if cmd in ("next", "n"):
        cmd_next(chunks, st, 1)
    elif cmd in ("again", "a", "current"):
        cmd_next(chunks, st, 0)
    elif cmd in ("back", "b", "prev"):
        cmd_next(chunks, st, -1)
    elif cmd == "show":
        v = view(chunks, st["mode"])
        c = v[min(st["pos"], len(v) - 1)]
        print("")
        print(open(os.path.join(OUT, c["file"]), encoding="utf-8").read().rstrip("\n"))
    elif cmd == "status":
        cmd_status(chunks, st)
    elif cmd == "toc":
        cmd_toc(chunks, st)
    elif cmd == "goto":
        cmd_goto(chunks, st, argv[1])
    elif cmd == "mode":
        if len(argv) < 2 or argv[1] not in ("prose", "code", "both"):
            sys.exit("mode must be prose, code, or both")
        st["mode"] = argv[1]
        st["pos"] = 0
        save_state(st)
        print("mode -> %s (position reset; use goto to jump)" % st["mode"])
    elif cmd == "reset":
        save_state({"pos": 0, "mode": st["mode"], "typed": 0})
        print("progress reset")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
