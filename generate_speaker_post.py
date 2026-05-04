#!/usr/bin/env python3
"""
WSW Speaker Post Generator — Women Shaping Wealth Summit
Generates 1080x1350 speaker posts automatically.

Usage:
  python3 generate_speaker_post.py \
    --image speaker.jpg \
    --role "Judge" \
    --name "HAZLEEN AHMAD" \
    --title "Founder, Neuropower World" \
    --output output.png
"""

import argparse, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# ── CONFIG ─────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
FONT_BOLD    = BASE_DIR / "TT_Drugs_Trial_Bold.otf"
FONT_REGULAR = BASE_DIR / "TT_Drugs_Trial_Regular.otf"
LOGO_FILE    = BASE_DIR / "wsw_logo_clean.png"
BG_FILE      = BASE_DIR / "wsw_background.png"

W, H = 1080, 1350

# Colors
NAME_COLOR  = (166, 255, 62)
WHITE       = (255, 255, 255)
WHITE_DIM   = (220, 220, 220)
PURPLE_MID  = (81, 17, 120)      # sampled from actual background bottom

# Layout — matched to template
MARGIN_LEFT = 54
ROLE_Y      = 900
NAME_Y      = 955
TITLE_Y     = 1075
URL_Y       = 1270

# Logo — top left
LOGO_X        = 40
LOGO_Y        = 36
LOGO_TARGET_W = 280

# Font sizes
ROLE_SIZE   = 32
NAME_SIZE   = 96
TITLE_SIZE  = 32
URL_SIZE    = 21

URL_TEXT = "https://www.get-playbook.com/women-shaping-wealth"


def font(bold=False, size=40):
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(str(path), size)
    except Exception as e:
        print(f"Font load error ({path}): {e}", file=sys.stderr)
        return ImageFont.load_default()


def composite_speaker(bg, speaker_path):
    """Place speaker image over background, fade to solid purple at bottom."""
    speaker  = Image.open(speaker_path).convert("RGBA")
    sw, sh   = speaker.size

    # Fill upper 70% of canvas
    target_w = W
    target_h = int(H * 0.70)
    scale    = max(target_w / sw, target_h / sh)
    nsw, nsh = int(sw * scale), int(sh * scale)
    speaker  = speaker.resize((nsw, nsh), Image.LANCZOS)

    # Center crop, slight top bias for face
    x_off = (nsw - target_w) // 2
    y_off = max(0, (nsh - target_h) // 10)
    speaker = speaker.crop((x_off, y_off, x_off + target_w, y_off + target_h))

    canvas = bg.convert("RGBA")
    canvas.paste(speaker, (0, 0), speaker)

    # Gradient fade: start at 38%, fully solid purple by 70%
    fade_start = int(H * 0.38)
    fade_end   = int(H * 0.70)
    overlay    = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw       = ImageDraw.Draw(overlay)

    # Sample actual bg color at bottom for seamless blend
    bg_arr    = np.array(bg)
    bot_color = tuple(bg_arr[int(H*0.85), W//2].tolist())

    for y in range(fade_start, fade_end):
        t     = (y - fade_start) / (fade_end - fade_start)
        alpha = int(255 * (t ** 1.5))
        draw.line([(0, y), (W, y)], fill=(*bot_color, alpha))

    draw.rectangle([(0, fade_end), (W, H)], fill=(*bot_color, 255))

    return Image.alpha_composite(canvas, overlay).convert("RGB")


def place_logo(canvas):
    """Place WSW logo top-left. Single instance."""
    try:
        logo   = Image.open(LOGO_FILE).convert("RGBA")
        lw, lh = logo.size
        scale  = LOGO_TARGET_W / lw
        new_lh = int(lh * scale)
        logo   = logo.resize((LOGO_TARGET_W, new_lh), Image.LANCZOS)
        out    = canvas.convert("RGBA")
        out.paste(logo, (LOGO_X, LOGO_Y), logo)
        return out.convert("RGB")
    except Exception as e:
        print(f"Logo error: {e}", file=sys.stderr)
        return canvas


def wrap_text(text, font_obj, max_width):
    """Wrap text into lines that fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = font_obj.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def auto_size_name(name, max_width):
    size = NAME_SIZE
    while size > 40:
        f    = font(bold=True, size=size)
        bbox = f.getbbox(name)
        if bbox[2] - bbox[0] <= max_width:
            return f, size
        size -= 2
    return font(bold=True, size=size), size


def draw_text(canvas, role, name, title):
    draw     = ImageDraw.Draw(canvas)
    max_text = int(W * 0.84)

    # ── Role (Regular, white dim) ──
    draw.text((MARGIN_LEFT, ROLE_Y), role,
              font=font(False, ROLE_SIZE), fill=WHITE_DIM)

    # ── Name (Bold, lime green, auto-sizes) ──
    name_font, _ = auto_size_name(name, max_text)
    draw.text((MARGIN_LEFT, NAME_Y), name, font=name_font, fill=NAME_COLOR)

    # ── Title — wrapped if too long ──
    title_font = font(False, TITLE_SIZE)
    lines      = wrap_text(title, title_font, max_text)
    line_h     = int(TITLE_SIZE * 1.35)
    for i, line in enumerate(lines):
        draw.text((MARGIN_LEFT, TITLE_Y + i * line_h), line,
                  font=title_font, fill=WHITE)

    # ── URL (Regular, centered, dimmed) ──
    url_font = font(False, URL_SIZE)
    bbox     = url_font.getbbox(URL_TEXT)
    url_x    = (W - (bbox[2] - bbox[0])) // 2
    draw.text((url_x, URL_Y), URL_TEXT, font=url_font, fill=(190, 190, 190))

    return canvas


def generate(speaker_path, role, name, title, output_path):
    print(f"  Generating: {name}")

    # Use real background — no generation
    bg     = Image.open(BG_FILE).convert("RGB").resize((W, H), Image.LANCZOS)
    canvas = composite_speaker(bg, speaker_path)
    canvas = place_logo(canvas)
    canvas = draw_text(canvas, role, name, title)
    canvas.save(output_path, "PNG")
    print(f"  ✓ Saved → {output_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--image",  required=True)
    p.add_argument("--role",   default="Speaker")
    p.add_argument("--name",   required=True)
    p.add_argument("--title",  required=True)
    p.add_argument("--output", default="speaker_post.png")
    args = p.parse_args()
    generate(args.image, args.role, args.name, args.title, args.output)
