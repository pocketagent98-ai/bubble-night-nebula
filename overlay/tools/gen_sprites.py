"""Procedural sprite generator for Bubble Night: Nebula.

Bubbles are rendered as real spheres rather than flat discs: per-pixel surface
normals, a Blinn-Phong specular lobe, a Fresnel rim, a transmitted-light
crescent at the bottom and a contact shadow. That is what separates a bubble
that reads as "3D glass" from a coloured circle with a white dot on it.

Outputs (default):
  app/src/main/assets/nebula/bubbles/*.png     256x256 game bubbles
  app/src/main/assets/nebula/planets/*.png     512x512 orbit planets
  app/src/main/assets/nebula/fx/*.png          additive particles
  app/src/main/assets/nebula/atlas_bubbles.png contact sheet for review
  app/src/main/assets/nebula/sprite_manifest.json

Run:  python3 tools/gen_sprites.py
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SS = 3  # supersampling factor (3 is the quality/speed knee: 256px bubbles render in ~0.6 s)

PALETTE = {
    "blue": "#7AA2F7",
    "purple": "#BB9AF7",
    "green": "#9ECE6A",
    "orange": "#FF9E64",
    "pink": "#F7768E",
    "cyan": "#7DCFFF",
}
# Extra hues used by the Nebula layer (boosters, orbit accents).
ACCENTS = {
    "gold": "#E0AF68",
    "teal": "#73DACA",
    "grey": "#A9B1D6",
    "red": "#F7768E",
    "white": "#E6E9FF",
}


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float64)


def normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=0, keepdims=True)
    return v / np.maximum(n, 1e-9)


def grid(size: int):
    """Pixel centres in [-1, 1] with y pointing down."""
    c = (np.arange(size, dtype=np.float64) + 0.5) / size * 2.0 - 1.0
    x, y = np.meshgrid(c, c)
    return x, y


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def value_noise(size: int, cells: int, seed: int) -> np.ndarray:
    """Tileable-ish smooth noise from a coarse random lattice, bicubic upsampled."""
    r = np.random.default_rng(seed)
    base = r.random((cells, cells))
    img = Image.fromarray((base * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
    return np.asarray(img, dtype=np.float64) / 255.0


def shade_sphere(
    size: int,
    base: np.ndarray,
    *,
    light=(-0.48, -0.60, 0.64),
    shininess: float = 48.0,
    spec_strength: float = 1.0,
    rim_strength: float = 0.55,
    trans_strength: float = 0.38,
    ambient: float = 0.30,
    diffuse: float = 0.85,
    texture: np.ndarray | None = None,
    edge_softness: float = 0.012,
) -> np.ndarray:
    """Returns an RGBA float array in [0,1] of shape (size, size, 4)."""
    x, y = grid(size)
    x = x.astype(np.float32); y = y.astype(np.float32)
    r2 = (x * x + y * y).astype(np.float32)
    mask = r2 <= 1.0
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0)).astype(np.float32)
    N = np.stack([x, y, nz], axis=0)

    L = np.asarray(light, dtype=np.float32)
    L = L / np.linalg.norm(L)
    V = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    H = (L + V)
    H = H / np.linalg.norm(H)

    ndl = np.clip((N * L[:, None, None]).sum(axis=0), 0.0, 1.0)
    ndh = np.clip((N * H[:, None, None]).sum(axis=0), 0.0, 1.0)
    spec = ndh ** shininess

    fres = (1.0 - nz) ** 2.6

    # Light that travelled through the bubble and bounced off the back wall:
    # a warm crescent opposite the key light. This is the "glass" cue.
    T = np.array([0.42, 0.70, -0.58], dtype=np.float32)
    T = T / np.linalg.norm(T)
    ndt = np.clip((N * T[:, None, None]).sum(axis=0), 0.0, 1.0) ** 1.8

    albedo = base.astype(np.float32)
    if texture is not None:
        albedo = albedo[None, None, :] * (0.62 + 0.76 * texture[..., None].astype(np.float32))

    col = albedo * (ambient + diffuse * ndl[..., None])
    col = col + np.array([1.0, 0.98, 0.96], dtype=np.float32)[None, None, :] * (spec[..., None] * spec_strength)
    col = col + albedo * (ndt[..., None] * trans_strength)
    col = col + np.array([1.0, 1.0, 1.0], dtype=np.float32)[None, None, :] * (fres[..., None] * rim_strength)

    # Slight desaturation at the very rim keeps the sprite from looking neon.
    col = col * (1.0 - 0.25 * fres[..., None]) + albedo * 0.25 * fres[..., None]

    alpha = smoothstep(1.0, 1.0 - edge_softness, np.sqrt(r2))
    alpha = alpha * mask.astype(np.float64)

    out = np.concatenate([np.clip(col, 0.0, 1.0), alpha[..., None].astype(np.float32)], axis=2)
    return out


def to_image(rgba: np.ndarray, ss: int = SS) -> Image.Image:
    img = Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), mode="RGBA")
    if ss > 1:
        img = img.resize((img.width // ss, img.height // ss), Image.LANCZOS)
    return img


def draw_glyph(img: Image.Image, glyph: str, color=(255, 255, 255), alpha=150, scale=0.42):
    """Colorblind-mode symbol stamped into the middle of the bubble."""
    d = ImageDraw.Draw(img, "RGBA")
    s = img.width
    r = s * scale * 0.5
    cx, cy = s / 2, s / 2
    col = color + (alpha,)
    lw = max(int(s * 0.035), 2)
    if glyph == "circle":
        d.ellipse([cx - r * .55, cy - r * .55, cx + r * .55, cy + r * .55], outline=col, width=lw)
    elif glyph == "ring":
        d.ellipse([cx - r * .75, cy - r * .75, cx + r * .75, cy + r * .75], outline=col, width=lw)
    elif glyph == "triangle":
        d.polygon([(cx, cy - r * .8), (cx - r * .75, cy + r * .55), (cx + r * .75, cy + r * .55)], outline=col, width=lw)
    elif glyph == "square":
        d.rectangle([cx - r * .62, cy - r * .62, cx + r * .62, cy + r * .62], outline=col, width=lw)
    elif glyph == "cross":
        d.line([cx - r * .7, cy, cx + r * .7, cy], fill=col, width=lw)
        d.line([cx, cy - r * .7, cx, cy + r * .7], fill=col, width=lw)
    elif glyph == "star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = r * (.85 if i % 2 == 0 else .36)
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        d.polygon(pts, fill=col)
    elif glyph == "diamond":
        d.polygon([(cx, cy - r * .8), (cx + r * .7, cy), (cx, cy + r * .8), (cx - r * .7, cy)], outline=col, width=lw)
    elif glyph == "dot":
        d.ellipse([cx - r * .3, cy - r * .3, cx + r * .3, cy + r * .3], fill=col)


GLYPHS = {
    "blue": "circle",
    "purple": "diamond",
    "green": "triangle",
    "orange": "square",
    "pink": "cross",
    "cyan": "ring",
}


def make_bubble(hexcolor: str, size: int = 256, seed: int = 1, glyph: str | None = None,
                tint: np.ndarray | None = None) -> Image.Image:
    px = size * SS
    r = np.random.default_rng(seed)
    # Fine surface mottling so the sphere is not a perfect plastic ball.
    tex = 0.5 + 0.5 * np.tanh(3.0 * (value_noise(px, 24, seed) - 0.5))
    tex = 0.85 + 0.15 * tex
    rgba = shade_sphere(px, hex_rgb(hexcolor), texture=tex, shininess=52.0)
    if tint is not None:
        rgba[..., :3] = np.clip(rgba[..., :3] * (0.55 + 0.9 * tint), 0, 1)
    img = to_image(rgba)
    if glyph:
        draw_glyph(img, glyph)
    return img


def make_special(kind: str, size: int = 256) -> Image.Image:
    px = size * SS
    if kind == "rock":
        tex = value_noise(px, 10, 41)
        tex = (tex > 0.5).astype(np.float64) * 0.35 + tex * 0.65
        rgba = shade_sphere(px, hex_rgb("#8A8FA8"), texture=tex, shininess=8.0,
                            spec_strength=0.25, rim_strength=0.22, trans_strength=0.0,
                            ambient=0.42, diffuse=0.72, edge_softness=0.02)
        # Chipped silhouette: pull the alpha in at a few angles.
        x, y = grid(px)
        ang = np.arctan2(y, x)
        wob = 1.0 + 0.05 * np.sin(ang * 7 + 1.1) + 0.03 * np.sin(ang * 13 + 2.4)
        rgba[..., 3] *= smoothstep(1.0, 0.985, np.sqrt(x * x + y * y) / wob)
        return to_image(rgba)

    if kind == "star":
        rgba = shade_sphere(px, hex_rgb("#E0AF68"), shininess=90.0, spec_strength=1.3)
        img = to_image(rgba)
        draw_glyph(img, "star", (255, 255, 255), 235, scale=0.62)
        return img

    if kind == "bomb":
        rgba = shade_sphere(px, hex_rgb("#2B2F45"), shininess=70.0, spec_strength=0.9,
                            rim_strength=0.35, trans_strength=0.0, ambient=0.5)
        img = to_image(rgba)
        d = ImageDraw.Draw(img, "RGBA")
        s = img.width
        d.line([s * .62, s * .22, s * .74, s * .10], fill=(255, 190, 90, 220), width=max(int(s * .03), 2))
        d.ellipse([s * .70, s * .02, s * .84, s * .16], fill=(255, 150, 60, 235))
        draw_glyph(img, "cross", (255, 120, 90), 200, scale=0.5)
        return img

    if kind == "fireball":
        rgba = shade_sphere(px, hex_rgb("#FF7A45"), shininess=30.0, spec_strength=0.7,
                            trans_strength=0.9, ambient=0.55)
        img = to_image(rgba)
        d = ImageDraw.Draw(img, "RGBA")
        s = img.width
        for i, (rr, aa) in enumerate(((0.42, 120), (0.28, 170), (0.14, 220))):
            d.ellipse([s * (.5 - rr), s * (.5 - rr), s * (.5 + rr), s * (.5 + rr)], fill=(255, 226, 150, aa))
        return img

    if kind == "rainbow":
        px_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        x, y = grid(size)
        r2 = x * x + y * y
        ang = (np.arctan2(y, x) / (2 * np.pi) + 0.5)
        hue = (ang + np.sqrt(np.clip(r2, 0, 1)) * 0.35) % 1.0
        # HSV -> RGB vectorised
        i = (hue * 6).astype(int) % 6
        f = hue * 6 - np.floor(hue * 6)
        s, v = 0.72, 1.0
        p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
        rgb = np.zeros((size, size, 3))
        for k, (rr, gg, bb) in enumerate([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]):
            m = i == k
            rgb[m] = np.stack([np.broadcast_to(rr, (size, size))[m],
                               np.broadcast_to(gg, (size, size))[m],
                               np.broadcast_to(bb, (size, size))[m]], axis=-1)
        base = Image.fromarray((rgb * 255).astype(np.uint8), "RGB")
        mask = Image.fromarray((smoothstep(1.0, 0.97, np.sqrt(r2)) * 255).astype(np.uint8), "L")
        px_img.paste(base, (0, 0), mask)
        # Re-shade with a glass highlight on top of the rainbow fill.
        glass = to_image(shade_sphere(size * 2, np.array([1.0, 1.0, 1.0]), shininess=60.0,
                                      spec_strength=0.55, rim_strength=0.5, trans_strength=0.0,
                                      ambient=0.0, diffuse=0.0))
        glass = glass.resize((size, size), Image.LANCZOS)
        px_img = Image.alpha_composite(px_img, glass)
        return px_img

    if kind == "ice":
        rgba = shade_sphere(px, hex_rgb("#9BD8FF"), shininess=110.0, spec_strength=1.4,
                            rim_strength=0.8, trans_strength=0.6, ambient=0.4)
        img = to_image(rgba)
        draw_glyph(img, "diamond", (255, 255, 255), 190, scale=0.55)
        return img

    if kind == "shield":
        rgba = shade_sphere(px, hex_rgb("#73DACA"), shininess=140.0, spec_strength=1.5,
                            rim_strength=1.0, trans_strength=0.2, ambient=0.25, diffuse=0.4)
        img = to_image(rgba)
        d = ImageDraw.Draw(img, "RGBA")
        s = img.width
        d.ellipse([s * .12, s * .12, s * .88, s * .88], outline=(255, 255, 255, 120), width=max(int(s * .018), 2))
        return img

    raise ValueError(kind)


def make_planet(orbit: int, size: int = 512) -> Image.Image:
    """Orbit planet: a lit sphere with domain-warped latitude bands.

    Bands are warped by smooth noise before they are laid down, which is what
    makes a gas giant read as flowing gas instead of a striped beach ball.
    Rocky orbits get soft craters stamped as a darkening field, not outlines.
    """
    px = size * 2
    seeds = [3, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]
    seed = seeds[(orbit - 1) % len(seeds)]
    r = np.random.default_rng(seed)

    x, y = grid(px)
    x = x.astype(np.float32); y = y.astype(np.float32)
    r2 = x * x + y * y
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0)).astype(np.float32)

    # Surface normal, key light upper-left, Blinn-Phong highlight.
    N = np.stack([x, y, nz], axis=0)
    L = np.array([-0.48, -0.60, 0.64], dtype=np.float32); L /= np.linalg.norm(L)
    V = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    H = L + V; H /= np.linalg.norm(H)
    ndl = np.clip((N * L[:, None, None]).sum(axis=0), 0, 1)
    ndh = np.clip((N * H[:, None, None]).sum(axis=0), 0, 1)

    # Domain-warped latitude bands.
    # Gentle shear only: enough to stop the bands looking like a beach ball,
    # not enough to fold them into contour lines.
    warp = (value_noise(px, 5, seed) - 0.5) * 0.28 + (value_noise(px, 13, seed + 1) - 0.5) * 0.10
    lat = np.arcsin(np.clip(y, -1, 1)) + warp
    freq = r.uniform(5.0, 9.0)
    phase = r.uniform(0, 6.28)
    bands = 0.5 + 0.5 * np.sin(lat * freq + phase)
    bands = bands * 0.72 + 0.28 * (0.5 + 0.5 * np.sin(lat * freq * 0.41 + phase * 1.7))
    bands = smoothstep(0.08, 0.92, bands)

    hue = r.uniform(0, 1)
    base = np.array([
        0.52 + 0.38 * math.sin(hue * 6.28),
        0.50 + 0.38 * math.sin(hue * 6.28 + 2.1),
        0.62 + 0.33 * math.sin(hue * 6.28 + 4.2),
    ], dtype=np.float32)
    base = np.clip(base, 0.22, 1.0)

    light_c = np.clip(base * 1.30 + 0.08, 0, 1)
    dark_c = np.clip(base * 0.62, 0, 1)
    surf = dark_c[None, None, :] + (light_c - dark_c)[None, None, :] * bands[..., None]

    # Polar caps.
    cap = smoothstep(0.72, 0.99, np.abs(y)) * 0.55
    surf = surf * (1 - cap[..., None]) + np.array([0.86, 0.90, 1.0], dtype=np.float32)[None, None, :] * cap[..., None]

    col = surf * (0.14 + 1.02 * ndl[..., None])
    col = col + np.array([1.0, 0.99, 0.97], dtype=np.float32)[None, None, :] * ((ndh ** 14.0) * 0.16)[..., None]

    if orbit in (2, 4, 8, 10):
        craters = np.zeros((px, px), dtype=np.float32)
        rim = np.zeros((px, px), dtype=np.float32)
        for _ in range(int(r.integers(9, 17))):
            cx, cy = r.uniform(-0.62, 0.62, 2)
            if cx * cx + cy * cy > 0.52:
                continue
            rad = r.uniform(0.05, 0.17)
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / rad
            bowl = np.clip(1.0 - d, 0, 1) ** 0.6
            craters = np.maximum(craters, bowl)
            ring = np.exp(-((d - 1.0) * 3.2) ** 2)
            # Rim catches the light on the side facing the key light.
            lit = np.clip((-(x - cx) * 0.5 - (y - cy) * 0.6), 0, 1)
            rim = np.maximum(rim, ring * lit)
        col = col * (1.0 - 0.42 * craters[..., None])
        col = col + np.array([1.0, 0.98, 0.94], dtype=np.float32)[None, None, :] * (rim * 0.30)[..., None]

    fres = (1.0 - nz) ** 2.4
    col = col + base[None, None, :] * (fres * 0.55)[..., None]

    alpha = smoothstep(1.0, 0.994, np.sqrt(r2))
    rgba = np.concatenate([np.clip(col, 0, 1), alpha[..., None]], axis=2)
    return to_image(rgba, ss=2)


def make_particle(kind: str, size: int = 64) -> Image.Image:
    x, y = grid(size)
    r = np.sqrt(x * x + y * y)
    if kind == "spark":
        core = np.exp(-(r * 5.0) ** 2)
        streak = np.exp(-(np.abs(x) * 18.0) ** 2) * np.exp(-(np.abs(y) * 1.6) ** 2) * 0.7
        a = np.clip(core + streak, 0, 1)
        rgb = np.ones((size, size, 3))
    elif kind == "glow":
        a = np.clip(np.exp(-(r * 2.6) ** 2), 0, 1) ** 1.4
        rgb = np.ones((size, size, 3))
    elif kind == "ring":
        a = np.clip(np.exp(-((r - 0.72) * 12.0) ** 2), 0, 1)
        rgb = np.ones((size, size, 3))
    elif kind == "confetti":
        a = np.clip(smoothstep(1.0, 0.86, r) * (0.6 + 0.4 * np.cos(x * 9)), 0, 1)
        rgb = np.ones((size, size, 3))
    else:
        raise ValueError(kind)
    rgba = np.concatenate([rgb, a[..., None]], axis=2)
    return to_image(rgba, ss=1)


def contact_sheet(items: dict[str, Image.Image], cols: int = 6, cell: int = 160) -> Image.Image:
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * (cell + 22)), (16, 18, 32, 255))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
    for i, (name, img) in enumerate(items.items()):
        cx, cy = (i % cols) * cell, (i // cols) * (cell + 22)
        thumb = img.resize((cell - 16, cell - 16), Image.LANCZOS)
        sheet.alpha_composite(thumb, (cx + 8, cy + 6))
        d.text((cx + 8, cy + cell - 6), name, fill=(200, 205, 230, 255), font=font)
    return sheet


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="app/src/main/assets/nebula")
    ap.add_argument("--size", type=int, default=256)
    args = ap.parse_args()

    root = Path(args.out)
    for sub in ("bubbles", "planets", "fx"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    started = time.time()
    manifest = {"bubbles": {}, "specials": {}, "planets": {}, "fx": {}}
    sheet_items: dict[str, Image.Image] = {}

    for i, (name, hexc) in enumerate(PALETTE.items()):
        img = make_bubble(hexc, args.size, seed=100 + i)
        img.save(root / "bubbles" / f"{name}.png")
        manifest["bubbles"][name] = {"file": f"bubbles/{name}.png", "color": hexc}
        sheet_items[name] = img
        gimg = make_bubble(hexc, args.size, seed=100 + i, glyph=GLYPHS[name])
        gimg.save(root / "bubbles" / f"{name}_symbol.png")
        manifest["bubbles"][f"{name}_symbol"] = {"file": f"bubbles/{name}_symbol.png", "color": hexc,
                                                 "glyph": GLYPHS[name]}

    for kind in ("rock", "star", "bomb", "fireball", "rainbow", "ice", "shield"):
        img = make_special(kind, args.size)
        img.save(root / "bubbles" / f"special_{kind}.png")
        manifest["specials"][kind] = {"file": f"bubbles/special_{kind}.png"}
        sheet_items[f"special_{kind}"] = img

    for orbit in range(1, 13):
        img = make_planet(orbit, 512)
        img.save(root / "planets" / f"orbit_{orbit:02d}.png")
        manifest["planets"][f"orbit_{orbit:02d}"] = {"file": f"planets/orbit_{orbit:02d}.png"}

    for kind in ("spark", "glow", "ring", "confetti"):
        img = make_particle(kind, 64)
        img.save(root / "fx" / f"{kind}.png")
        manifest["fx"][kind] = {"file": f"fx/{kind}.png"}

    sheet = contact_sheet(sheet_items)
    sheet.save(root / "atlas_bubbles.png")
    (root / "sprite_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"{len(sheet_items)} bubbles + 12 planets + 4 particles in {time.time() - started:.1f}s")
    print(f"contact sheet: {root / 'atlas_bubbles.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
