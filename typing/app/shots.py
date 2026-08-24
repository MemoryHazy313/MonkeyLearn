import time, os, json, sys
import webview
from PIL import ImageGrab
import main as appmod

OUT = r"C:\Users\solom\AppData\Local\Temp\claude\E--Matthes-Eric---Python-Crash-Course--3rd-Edition---2023\69dbcf24-2c47-4193-85ab-2e182b18f7e3\scratchpad"
os.makedirs(OUT, exist_ok=True)

# protect the user's real progress during the run
backup = None
if os.path.exists(appmod.STATE_FILE):
    backup = open(appmod.STATE_FILE, encoding="utf-8").read()

def grab(window, name):
    time.sleep(0.5)
    x, y = window.x, window.y
    img = ImageGrab.grab(bbox=(x, y, x+window.width, y+window.height))
    img.save(os.path.join(OUT, name+".png"))

def probe(window):
    try:
        for _ in range(60):
            time.sleep(0.25)
            if window.evaluate_js("!!(window.S && BOOKS.length>0)"): break
        window.evaluate_js("showShelf()")
        grab(window, "1-shelf")
        window.evaluate_js("openBook('pcc3')")
        time.sleep(0.8)
        grab(window, "2-library")
        window.evaluate_js("B().len='medium'; buildChunks(); openPassage(chunks.find(c=>c.hasCode).idx, false)")
        time.sleep(0.5)
        grab(window, "3-passage-code")
        window.evaluate_js("B().len='chapter'; buildChunks(); openPassage(2, false)")
        time.sleep(0.7)
        grab(window, "4-passage-chapter")
        window.evaluate_js("showLibrary()")
        time.sleep(0.4)
        grab(window, "5-library-chapter-len")
    except Exception as e:
        print("ERROR", repr(e))
    finally:
        window.destroy()

with open(appmod.res_path("ui.html"), encoding="utf-8") as f:
    html = f.read()
appmod.window = webview.create_window("MonkeyLearn", html=html, js_api=appmod.Api(),
                                      width=1000, height=800, background_color="#ECE9D8", frameless=True, easy_drag=False, on_top=True)
webview.start(probe, appmod.window)

if backup is not None:
    open(appmod.STATE_FILE, "w", encoding="utf-8").write(backup)
print("done, state restored:", backup is not None)
