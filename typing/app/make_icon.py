"""Draw monkeylearn.ico: a paper page with the red bookmark ribbon on a
Luna-blue rounded tile. Regenerate with: python make_icon.py"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 256


def draw_icon():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # rounded tile with a vertical Luna gradient
    bg = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(bg)
    top, bot = (16, 116, 208), (10, 36, 106)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)],
                fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([6, 6, S - 6, S - 6], radius=38, fill=255)
    img.paste(bg, (0, 0), mask)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, S - 6, S - 6], radius=38,
                        outline=(255, 255, 255, 60), width=5)

    # paper page with drop shadow and retro border
    px0, py0, px1, py1 = 56, 46, 200, 218
    d.rectangle([px0 + 9, py0 + 9, px1 + 9, py1 + 9], fill=(0, 0, 0, 70))
    d.rectangle([px0, py0, px1, py1], fill=(241, 233, 217, 255))
    d.rectangle([px0, py0, px1, py1], outline=(113, 111, 100, 255), width=3)

    # text lines
    ly = py0 + 34
    while ly + 9 < py1 - 16:
        d.rectangle([px0 + 20, ly, px1 - 20, ly + 9], fill=(176, 166, 142, 255))
        ly += 28

    # bookmark ribbon over the page's top-right, notched at the bottom
    rx0, rx1 = 148, 186
    ry0, ry1 = py0 - 14, py0 + 78
    d.polygon([(rx0, ry0), (rx1, ry0), (rx1, ry1),
               ((rx0 + rx1) // 2, ry1 - 20), (rx0, ry1)],
              fill=(178, 59, 46, 255))
    return img


def main():
    img = draw_icon()
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    out = os.path.join(HERE, "monkeylearn.ico")
    img.save(out, sizes=sizes)
    print("wrote", out, os.path.getsize(out), "bytes")

    # preview sheet for eyeballing every size
    sheet = Image.new("RGBA", (470, 300), (32, 32, 36, 255))
    sheet.paste(img, (16, 16), img)
    x = 290
    for w in (64, 48, 32, 24, 16):
        small = img.resize((w, w), Image.LANCZOS)
        sheet.paste(small, (x, 40), small)
        sheet.paste(small, (x, 150), small)
        x += w + 14
    d = ImageDraw.Draw(sheet)
    d.rectangle([280, 130, 470, 230], fill=(230, 228, 216, 255))
    x = 290
    for w in (64, 48, 32, 24, 16):
        small = img.resize((w, w), Image.LANCZOS)
        sheet.paste(small, (x, 150), small)
        x += w + 14
    prev = os.path.join(HERE, "_icon_preview.png")
    sheet.save(prev)
    print("wrote", prev)


if __name__ == "__main__":
    main()
