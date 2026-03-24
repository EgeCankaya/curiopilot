"""Generate CurioPilot app icons — premium, bold, reads clean at 16 px."""

from pathlib import Path
from PIL import Image, ImageDraw
import math

ROOT = Path(__file__).resolve().parent.parent

# ── Palette ──────────────────────────────────────────────────────────
BG        = (15, 23, 42)       # slate-900
RING_DARK = (30, 41, 59)       # slate-800
FACE      = (248, 250, 252)    # slate-50
LINE_CLR  = (190, 200, 215, 160)  # muted text bars
RED       = (220, 38, 38)      # compass north
SOUTH     = (51, 65, 85)       # compass south
CAP_OUTER = (30, 41, 59)
CAP_INNER = (100, 116, 139)


def rounded_rect_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    return mask


def draw_icon(size: int = 512) -> Image.Image:
    """Render the icon at *size* px.  Design: centred compass whose face
    contains newspaper-style horizontal bars — merges both brand ideas
    into one bold, scalable shape."""

    # Supersample 4× then downscale for smooth edges at small sizes
    ss = 4 if size <= 64 else (2 if size <= 128 else 1)
    real = size * ss
    sc = real / 512  # scale factor

    img = Image.new("RGBA", (real, real), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx = cy = real // 2
    R = lambda v: int(v * sc)  # noqa: E731 — shorthand scaler

    # ── Background ───────────────────────────────────────────────────
    corner = R(112)
    d.rounded_rectangle([0, 0, real - 1, real - 1], radius=corner, fill=BG)

    # ── Compass outer ring ───────────────────────────────────────────
    r_ring = R(215)
    d.ellipse([cx - r_ring, cy - r_ring, cx + r_ring, cy + r_ring],
              fill=RING_DARK)

    # ── White compass face ───────────────────────────────────────────
    r_face = R(194)
    d.ellipse([cx - r_face, cy - r_face, cx + r_face, cy + r_face],
              fill=FACE)

    # ── Newspaper text bars inside face ──────────────────────────────
    # Thick, bold bars — read clearly even at 16 px
    bar_h = R(14)
    bar_offsets = [-66, -28, 12, 50]  # y-offsets from centre
    for y_off in bar_offsets:
        by = cy + R(y_off)
        # Width: fit inside circle with padding
        dy = abs(y_off)
        max_half = math.sqrt(max(0, 194**2 - dy**2)) * sc
        half_w = max_half * 0.68
        x1 = int(cx - half_w)
        x2 = int(cx + half_w)
        d.rounded_rectangle([x1, by - bar_h // 2, x2, by + bar_h // 2],
                            radius=max(1, bar_h // 2), fill=LINE_CLR)

    # ── Compass needle — north (red) ────────────────────────────────
    nw = R(24)  # needle half-width — bold
    n_tip = R(170)
    d.polygon([
        (cx, cy - n_tip),
        (cx - nw, cy),
        (cx + nw, cy),
    ], fill=RED)

    # ── Compass needle — south (dark) ───────────────────────────────
    s_tip = R(170)
    d.polygon([
        (cx, cy + s_tip),
        (cx - nw, cy),
        (cx + nw, cy),
    ], fill=SOUTH)

    # ── Centre cap ───────────────────────────────────────────────────
    cap_r = R(16)
    d.ellipse([cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r],
              fill=CAP_OUTER)
    cap_r2 = R(9)
    d.ellipse([cx - cap_r2, cy - cap_r2, cx + cap_r2, cy + cap_r2],
              fill=CAP_INNER)

    # ── Cardinal dots (N / E / S / W) ────────────────────────────────
    dot_r = R(6)
    dot_dist = R(182)  # just inside face edge
    for angle in [0, 90, 180, 270]:
        dx = int(dot_dist * math.sin(math.radians(angle)))
        dy = int(-dot_dist * math.cos(math.radians(angle)))
        d.ellipse([cx + dx - dot_r, cy + dy - dot_r,
                   cx + dx + dot_r, cy + dy + dot_r],
                  fill=RING_DARK)

    # ── Mask to rounded rect ─────────────────────────────────────────
    mask = rounded_rect_mask(real, corner)
    img.putalpha(mask)

    # Downscale from supersample
    if ss > 1:
        img = img.resize((size, size), Image.LANCZOS)

    return img


# ── SVG version (for favicon.svg) ───────────────────────────────────

SVG_TEMPLATE = """\
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="112" fill="#0f172a"/>

  <!-- Compass outer ring -->
  <circle cx="256" cy="256" r="215" fill="#1e293b"/>

  <!-- White face -->
  <circle cx="256" cy="256" r="194" fill="#f8fafc"/>

  <!-- Newspaper text bars -->
  <rect x="137" y="183" width="238" height="14" rx="7" fill="#bec8d7" opacity="0.63"/>
  <rect x="148" y="221" width="216" height="14" rx="7" fill="#bec8d7" opacity="0.63"/>
  <rect x="155" y="261" width="202" height="14" rx="7" fill="#bec8d7" opacity="0.63"/>
  <rect x="148" y="299" width="216" height="14" rx="7" fill="#bec8d7" opacity="0.63"/>

  <!-- Needle — north (red) -->
  <polygon points="256,86 232,256 280,256" fill="#dc2626"/>
  <!-- Needle — south -->
  <polygon points="256,426 232,256 280,256" fill="#334155"/>

  <!-- Centre cap -->
  <circle cx="256" cy="256" r="16" fill="#1e293b"/>
  <circle cx="256" cy="256" r="9" fill="#64748b"/>

  <!-- Cardinal dots -->
  <circle cx="256" cy="74"  r="6" fill="#1e293b"/>
  <circle cx="438" cy="256" r="6" fill="#1e293b"/>
  <circle cx="256" cy="438" r="6" fill="#1e293b"/>
  <circle cx="74"  cy="256" r="6" fill="#1e293b"/>
</svg>
"""


def main():
    # ── PNG 512 ──
    icon_512 = draw_icon(512)
    icon_512.save(ROOT / "frontend" / "public" / "curiopilot-icon-512.png", "PNG")
    icon_512.save(ROOT / "frontend" / "public" / "curiopilot-logo-newspaper.png", "PNG")
    print("Saved 512 px PNGs")

    # ── SVG favicon ──
    svg_path = ROOT / "frontend" / "public" / "favicon.svg"
    svg_path.write_text(SVG_TEMPLATE, encoding="utf-8")
    print("Saved favicon.svg")

    # ── Multi-size ICO ──
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_images = [draw_icon(sz) for sz in sizes]

    for dest in [
        ROOT / "frontend" / "public" / "favicon.ico",
        ROOT / "src" / "curiopilot" / "assets" / "app.ico",
        ROOT / "scripts" / "curiopilot.ico",
    ]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        ico_images[0].save(
            dest, format="ICO",
            sizes=[(im.width, im.height) for im in ico_images],
            append_images=ico_images[1:],
        )
        print(f"Saved {dest.name}")

    print("\nDone — all icons generated.")


if __name__ == "__main__":
    main()
