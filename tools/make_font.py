#!/usr/bin/env python3
"""Generate the embedded bitmap font for main.py.

Renders DejaVu Sans (Regular + Bold) at 64 px with PIL, thresholds each
glyph to 1 bit, packs the bits, zlib-compresses and base64-encodes them.
The output is a Python fragment that is pasted into main.py by hand, so
the generated lines are part of the entry's authored source.

DejaVu Sans is free software (Bitstream Vera / Arev licences); the glyph
bitmaps here are a mechanical rendering of that font at one size.
Run:  python3 tools/make_font.py
Writes: /tmp/font_fragment.txt
"""
import base64
import zlib

from PIL import Image, ImageDraw, ImageFont

MASTER = 64
CHARS = (
    "".join(chr(c) for c in range(32, 127))
    + "\u2013\u2014\u00b0\u2022\u00b7\u2018\u2019\u201c\u201d\u2026\u00d7"
)
FONTS = {
    "REGULAR": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "BOLD": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}


def build(path):
    font = ImageFont.truetype(path, MASTER)
    ascent, descent = font.getmetrics()
    glyphs = []  # (advance, w, h, xoff, yoff, bits bytes)
    bits = bytearray()
    bitpos = 0

    def push_bit(b):
        nonlocal bitpos
        byte_i = bitpos // 8
        while len(bits) <= byte_i:
            bits.append(0)
        if b:
            bits[byte_i] |= 0x80 >> (bitpos % 8)
        bitpos += 1

    for ch in CHARS:
        adv = int(round(font.getlength(ch)))
        # Draw the glyph alone, anchored left/ascender at (0, 0).
        img = Image.new("L", (adv + 8, MASTER + descent + 8), 0)
        d = ImageDraw.Draw(img)
        d.text((0, 0), ch, font=font, fill=255, anchor="la")
        bbox = img.getbbox()
        if bbox is None or ch == " ":
            glyphs.append((adv, 0, 0, 0, 0))
            continue
        left, top, right, bottom = bbox
        w, h = right - left, bottom - top
        crop = img.crop(bbox)
        px = crop.load()
        for y in range(h):
            for x in range(w):
                push_bit(1 if px[x, y] >= 128 else 0)
        # yoff: distance from the baseline down to the glyph's top row.
        glyphs.append((adv, w, h, left, top - ascent))

    blob = base64.b85encode(zlib.compress(bytes(bits), 9)).decode("ascii")
    lines = []
    lines.append(f"FONT_{'REG' if 'Sans.ttf' in path else 'BOLD'} = {{")
    lines.append(f"    'chars': {CHARS!r},")
    lines.append(f"    'ascent': {ascent}, 'descent': {descent}, 'master': {MASTER},")
    lines.append("    'glyphs': [")
    for g in glyphs:
        lines.append(f"        {g},")
    lines.append("    ],")
    lines.append("    'data': (")
    for i in range(0, len(blob), 100):
        lines.append(f"        {blob[i:i + 100]!r}")
    lines.append("    ),")
    lines.append("}")
    return "\n".join(lines), len(blob), len(glyphs)


def main():
    out = []
    for name, path in FONTS.items():
        frag, blob_len, n = build(path)
        out.append(frag)
        print(f"{name}: {n} glyphs, blob {blob_len} chars")
    with open("/tmp/font_fragment.txt", "w") as f:
        f.write("\n\n".join(out) + "\n")
    print("wrote /tmp/font_fragment.txt")


if __name__ == "__main__":
    main()
