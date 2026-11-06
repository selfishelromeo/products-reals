#!/usr/bin/env python3
"""
Make 1080x1920 product reels from photos. Free tools only: Pillow + FFmpeg.

Usage:
    pip install pillow
    # FFmpeg must be installed (apt install ffmpeg / brew install ffmpeg)
    python make_reels.py                      # uses products.json
    python make_reels.py --music music.mp3    # add background music

products.json format:
[
  {
    "name": "Leather Wallet",
    "price": "$25",
    "images": ["images/wallet1.jpg", "images/wallet2.jpg", "images/wallet3.jpg"],
    "cta": "Order now - link in bio"
  }
]
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1920
SECONDS_PER_SLIDE = 2.5
FPS = 30

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # GitHub Actions / Ubuntu
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",     # macOS
    "C:/Windows/Fonts/arialbd.ttf",                          # Windows
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "product"


def fit_photo(path):
    """Blurred, zoomed copy as background + sharp photo fitted on top."""
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    bg = ImageOps.fit(img, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    fg = ImageOps.contain(img, (W, int(H * 0.7)), Image.LANCZOS)
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2 - 80))
    return bg


def draw_centered(draw, text, y, font, fill="white", max_width=W - 120):
    # simple word wrap
    words, lines, line = text.split(), [], ""
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            lines.append(line)
            line = word
    lines.append(line)
    for ln in lines:
        w = draw.textlength(ln, font=font)
        draw.text(((W - w) / 2, y), ln, font=font, fill=fill,
                  stroke_width=4, stroke_fill="black")
        y += font.size + 10
    return y


def make_slide(photo, lines, out_path):
    img = fit_photo(photo)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([0, H - 520, W, H], fill=(0, 0, 0, 140))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    y = H - 470
    for text, size, color in lines:
        y = draw_centered(draw, text, y, load_font(size), color) + 20
    img.save(out_path, quality=92)


def make_reel(product, out_dir, music=None):
    images = product["images"]
    name, price = product["name"], product.get("price", "")
    cta = product.get("cta", "Order now - link in bio")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        slides = []
        for i, photo in enumerate(images):
            if i == 0:
                lines = [(name, 90, "white"), (price, 110, "#FFD84D")]
            elif i == len(images) - 1:
                lines = [(cta, 70, "white"), (price, 100, "#FFD84D")]
            else:
                lines = [(name, 70, "white")]
            slide = tmp / f"slide{i:02d}.jpg"
            make_slide(photo, lines, slide)
            slides.append(slide)

        # ffmpeg concat list
        concat = tmp / "list.txt"
        with open(concat, "w") as f:
            for s in slides:
                f.write(f"file '{s}'\nduration {SECONDS_PER_SLIDE}\n")
            f.write(f"file '{slides[-1]}'\n")  # concat demuxer quirk

        out = out_dir / f"{slugify(name)}.mp4"
        total = SECONDS_PER_SLIDE * len(slides)
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat)]
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music)]
        cmd += ["-vf", f"fps={FPS},format=yuv420p", "-t", str(total),
                "-c:v", "libx264", "-preset", "medium", "-crf", "20"]
        if music:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-map", "0:v", "-map", "1:a",
                    "-af", f"afade=t=out:st={total - 1}:d=1"]
        cmd += ["-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"Created {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", default="products.json")
    ap.add_argument("--out", default="reels")
    ap.add_argument("--music", default=None, help="optional mp3 (use royalty-free music)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    products = json.loads(Path(args.products).read_text())
    for p in products:
        make_reel(p, out_dir, args.music)


if __name__ == "__main__":
    main()
          
