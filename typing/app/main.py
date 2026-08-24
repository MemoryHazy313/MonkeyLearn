"""Copywork - desktop companion for typing books on MonkeyType.

Serves the bundled ui.html in a WebView2 window, feeds passages to the
clipboard, imports EPUB/TXT books, and keeps progress in %APPDATA%/Copywork.
"""
import json
import os
import sys
import webbrowser

import pyperclip
import webview

import bookparse

BUILTIN_ID = "pcc3"


def res_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                       "Copywork")
STATE_FILE = os.path.join(APP_DIR, "state.json")
BOOKS_DIR = os.path.join(APP_DIR, "books")

window = None
maximized = False


def _book_meta(data, builtin=False):
    return {
        "id": data.get("id", BUILTIN_ID),
        "title": data["title"],
        "edition": data.get("edition", ""),
        "chapters": len(data["chapters"]),
        "words": sum(c["pw"] + c["cw"] for c in data["chapters"]),
        "hasCode": any(c["cw"] for c in data["chapters"]),
        "builtin": builtin,
    }


class Api:
    def _builtin(self):
        with open(res_path("data.json"), encoding="utf-8") as f:
            data = json.load(f)
        data["id"] = BUILTIN_ID
        return data

    def list_books(self):
        books = [_book_meta(self._builtin(), builtin=True)]
        if os.path.isdir(BOOKS_DIR):
            for fn in sorted(os.listdir(BOOKS_DIR)):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(BOOKS_DIR, fn), encoding="utf-8") as f:
                        books.append(_book_meta(json.load(f)))
                except Exception:
                    pass
        return books

    def get_book(self, book_id):
        if book_id == BUILTIN_ID:
            return self._builtin()
        path = os.path.join(BOOKS_DIR, book_id + ".json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def import_book(self, path=None):
        try:
            if path is None:
                picked = window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    file_types=("Books (*.epub;*.txt;*.md)",
                                "All files (*.*)"))
                if not picked:
                    return {"cancelled": True}
                path = picked[0]
            data = bookparse.parse_book(path)
            os.makedirs(BOOKS_DIR, exist_ok=True)
            out = os.path.join(BOOKS_DIR, data["id"] + ".json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, separators=(",", ":"))
            return {"meta": _book_meta(data)}
        except Exception as e:
            return {"error": str(e)}

    def delete_book(self, book_id):
        if book_id == BUILTIN_ID:
            return False
        try:
            os.remove(os.path.join(BOOKS_DIR, book_id + ".json"))
            return True
        except Exception:
            return False

    def get_state(self):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_state(self, state):
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp, STATE_FILE)
            return True
        except Exception:
            return False

    def copy(self, text):
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def open_url(self, url):
        if isinstance(url, str) and url.startswith("https://"):
            webbrowser.open(url)
        return True

    # window controls for the frameless retro chrome
    def win_minimize(self):
        window.minimize()
        return True

    def win_toggle_max(self):
        global maximized
        if maximized:
            window.restore()
            maximized = False
        else:
            window.maximize()
            maximized = True
        return maximized

    def win_close(self):
        window.destroy()
        return True

    def win_resize_by(self, dw, dh):
        try:
            w = max(700, int(window.width + dw))
            h = max(540, int(window.height + dh))
            window.resize(w, h)
            return True
        except Exception:
            return False


def main():
    global window
    with open(res_path("ui.html"), encoding="utf-8") as f:
        html = f.read()
    window = webview.create_window(
        "Copywork", html=html, js_api=Api(),
        width=1000, height=800, min_size=(700, 540),
        background_color="#ECE9D8",
        frameless=True, easy_drag=False,
    )
    webview.start()


if __name__ == "__main__":
    main()
