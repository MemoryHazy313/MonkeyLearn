"""Build monkeylearn.ico: the pixel-art glasses from icon_source.png on a
paper tile with the retro border. Regenerate with: python make_icon.py"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
INK = (26, 22, 18, 255)
PAPER = (241, 233, 217, 255)
FRAME = (113, 111, 100, 255)


def load_glyph():
    src = Image.open(os.path.join(HERE, "icon_source.png")).convert("RGBA")
    px = src.load()
    w, h = src.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            px[x, y] = (0, 0, 0, 0) if r + g + b > 600 else INK
    return src.crop(src.getbbox())


def icon_at(glyph, size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = max(1, size // 42)
    r = max(2, size // 7)
    d.rounded_rectangle([m, m, size - 1 - m, size - 1 - m], radius=r, fill=PAPER)
    d.rounded_rectangle([m, m, size - 1 - m, size - 1 - m], radius=r,
                        outline=FRAME, width=max(1, size // 32))
    gw, gh = glyph.size
    s = min(size * 0.72 / gw, size * 0.72 / gh)
    # nearest keeps the pixel-art edges crisp at every size
    g = glyph.resize((max(1, round(gw * s)), max(1, round(gh * s))), Image.NEAREST)
    img.paste(g, ((size - g.size[0]) // 2, (size - g.size[1]) // 2), g)
    return img


def main():
    glyph = load_glyph()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [icon_at(glyph, s) for s in sizes]
    out = os.path.join(HERE, "monkeylearn.ico")
    frames[-1].save(out, sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
