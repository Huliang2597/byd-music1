#!/usr/bin/env python3
"""effectpv.py 用的贴图：每个场景一张底图 + 前景剪影 + 花（全部用 numpy/PIL 程序化生成，只需跑一次）。

用法: python3 fxtex.py <sprites目录> <输出目录>
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PW, PH = 2112, 1188  # 底图比画面大 10%，留给镜头推拉


def fbm(w, h, seed, octaves=6, base=3, gain=0.55):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        small = rng.random((max(2, n * h // w), n)).astype(np.float32)
        out += amp * np.asarray(Image.fromarray(small).resize((w, h), Image.BICUBIC))
        tot += amp
        amp *= gain
    out /= tot
    return (out - out.min()) / (out.max() - out.min())


def grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return x / w, y / h


def hexrgb(s):
    return np.array([int(s[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


def mix(a, b, t):
    t = t[..., None] if np.ndim(t) == 2 else t
    return a * (1 - t) + b * t


def vgrad(h, w, stops):
    """竖直渐变：stops = [(位置, '#rrggbb'), ...]"""
    ys = np.linspace(0, 1, h)
    cols = np.stack([np.interp(ys, [p for p, _ in stops], [hexrgb(c)[k] for _, c in stops]) for k in range(3)], -1)
    return np.repeat(cols[:, None, :], w, 1).astype(np.float32)


def save_rgb(a, path, q=95):
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(path, quality=q)


def vignette(w, h, k=0.55):
    x, y = grid(w, h)
    d = np.sqrt(((x - 0.5) * 1.3) ** 2 + (y - 0.5) ** 2)
    return np.clip(1 - k * d ** 2 * 2.2, 0, 1)


def plate_sepia(out):
    x, y = grid(PW, PH)
    col = vgrad(PH, PW, [(0, "#b9a584"), (0.45, "#ecdfc6"), (1, "#a88d68")])
    fog = fbm(PW, PH, 1)
    wash = fbm(PW, PH, 2, base=2)
    col = mix(col, hexrgb("#6e5538"), np.clip((wash - 0.45) * 1.2, 0, 0.45))
    col = mix(col, hexrgb("#fbf4e6"), np.clip((fog - 0.5) * 1.6, 0, 0.6) * np.exp(-((y - 0.5) / 0.35) ** 2))
    glow = np.exp(-(((x - 0.55) / 0.3) ** 2 + ((y - 0.42) / 0.3) ** 2))
    col = mix(col, hexrgb("#fff8ea"), glow * 0.45)
    save_rgb(col * vignette(PW, PH)[..., None] ** 0.8, os.path.join(out, "sepia.jpg"))


def plate_rain(out):
    x, y = grid(PW, PH)
    col = vgrad(PH, PW, [(0, "#5d636b"), (0.5, "#8c9096"), (1, "#6f747a")])
    fog = fbm(PW, PH, 3)
    col = mix(col, hexrgb("#c9cdd1"), np.clip((fog - 0.4) * 1.3, 0, 0.55))
    save_rgb(col * vignette(PW, PH)[..., None], os.path.join(out, "rain.jpg"))
    # 光束（单独一层，动画里慢慢摇）
    w, h = 1600, 1400
    x, y = grid(w, h)
    ang = np.arctan2(x * w - 0.22 * w, y * h + 0.1 * h)
    r = np.hypot(x * w - 0.22 * w, y * h + 0.1 * h) / h
    stripes = fbm(2048, 8, 4, octaves=5, base=6)[4]
    k = np.interp(ang, np.linspace(-1.4, 1.4, 2048), stripes)
    a = np.clip((k - 0.45) * 2.2, 0, 1) ** 1.6 * np.exp(-r * 1.1) * np.clip(r * 6, 0, 1)
    a *= np.clip(np.minimum(x, 1 - x) * 5, 0, 1) * np.clip((1 - y) * 5, 0, 1)  # 边缘淡出，避免硬边
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(rgba).filter(ImageFilter.GaussianBlur(6)).save(os.path.join(out, "rays.png"))


def plate_paper(out, name, base, fiber_col, seed):
    x, y = grid(PW, PH)
    col = np.ones((PH, PW, 3), np.float32) * hexrgb(base)
    fib = fbm(PW, PH, seed, octaves=7, base=8, gain=0.7)
    col = mix(col, hexrgb(fiber_col), np.clip((fib - 0.5) * 0.5, 0, 0.12))
    fog = fbm(PW, PH, seed + 1)
    col = mix(col, hexrgb(fiber_col), np.clip((fog - 0.55) * 0.6, 0, 0.12))
    save_rgb(col * vignette(PW, PH, 0.35)[..., None], os.path.join(out, name))


def plate_warm(out):
    x, y = grid(PW, PH)
    d = np.sqrt(((x - 0.5) * 1.5) ** 2 + (y - 0.5) ** 2)
    col = mix(np.ones((PH, PW, 3), np.float32) * hexrgb("#fbeee4"), hexrgb("#d6a79c"), np.clip(d * 1.3, 0, 1))
    fog = fbm(PW, PH, 7)
    col = mix(col, hexrgb("#fff6ef"), np.clip((fog - 0.5) * 1.2, 0, 0.35))
    save_rgb(col, os.path.join(out, "warm.jpg"))


def plate_sky(out):
    x, y = grid(PW, PH)
    col = vgrad(PH, PW, [(0, "#050b1c"), (0.45, "#12305a"), (0.78, "#5f9cc4"), (1, "#d8f1fb")])
    band = np.exp(-((y - 0.25 - 0.35 * (x - 0.5)) / 0.16) ** 2) * fbm(PW, PH, 8, base=4)
    col = mix(col, hexrgb("#8fb8e0"), np.clip(band * 0.6, 0, 0.45))
    rng = np.random.default_rng(9)
    img = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8))
    glow = Image.new("L", (PW, PH), 0)
    dg = ImageDraw.Draw(glow)
    d = ImageDraw.Draw(img)
    for _ in range(1400):
        sx, sy = rng.random() * PW, rng.random() ** 1.4 * PH * 0.8
        b = rng.random() ** 3
        rr = 0.6 + 1.6 * b
        c = int(170 + 85 * b)
        d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(c, c, 255))
        if b > 0.4:
            dg.ellipse([sx - 7 * b, sy - 7 * b, sx + 7 * b, sy + 7 * b], fill=int(120 * b))
    glow = np.asarray(glow.filter(ImageFilter.GaussianBlur(5)), np.float32)[..., None] / 255
    a = np.asarray(img, np.float32) / 255 + glow * hexrgb("#bfe3ff")
    save_rgb(a, os.path.join(out, "sky.jpg"))


def blade(d, x0, y0, h, lean, w, fill):
    pts_l, pts_r = [], []
    for k in range(13):
        s = k / 12
        cx = x0 + lean * s * s * h
        cy = y0 - s * h
        hw = w * (1 - s) ** 0.8
        pts_l.append((cx - hw, cy))
        pts_r.append((cx + hw, cy))
    d.polygon(pts_l + pts_r[::-1], fill=fill)


def silhouettes(sprites, w, h, seed, roses=6):
    """前景：草 + 带茎玫瑰的剪影（alpha 蒙版）"""
    s = 2
    m = Image.new("L", (w * s, h * s), 0)
    d = ImageDraw.Draw(m)
    rng = np.random.default_rng(seed)
    for _ in range(520):
        x0 = rng.random() * w * s
        edge = min(x0, w * s - x0) / (w * s)
        hh = (0.25 + 0.75 * rng.random() ** 1.5) * h * s * (1.0 - 0.9 * min(edge * 2.4, 0.85))
        blade(d, x0, h * s + 4, hh, rng.normal(0, 0.35), (3 + 5 * rng.random()) * s, 255)
    names = [f"rose_{c}_{e}_1.00.png" for c in ("white", "blue", "paleblue") for e in (25, 55)]
    for k in range(roses):
        side = -1 if k % 2 == 0 else 1
        x0 = w * s * (0.5 + side * (0.28 + 0.2 * rng.random()))
        top = h * s * (0.15 + 0.4 * rng.random())
        d.line([(x0, h * s), (x0 + rng.normal(0, 20), top)], fill=255, width=5 * s)
        spr = Image.open(os.path.join(sprites, names[rng.integers(len(names))])).split()[3]
        sz = int((150 + 150 * rng.random()) * s)
        spr = spr.resize((sz, sz), Image.LANCZOS).rotate(rng.normal(0, 18), resample=Image.BICUBIC)
        m.paste(255, (int(x0 - sz / 2), int(top - sz / 2)), spr.point(lambda v: 255 if v > 90 else 0))
    return m.resize((w, h), Image.LANCZOS)


def tinted(mask, color, blur=0.0, glow=None):
    a = mask.filter(ImageFilter.GaussianBlur(blur)) if blur else mask
    rgb = (hexrgb(color) * 255).astype(np.uint8)
    arr = np.zeros((mask.size[1], mask.size[0], 4), np.uint8)
    arr[..., :3] = rgb
    arr[..., 3] = np.asarray(a)
    im = Image.fromarray(arr)
    if glow:
        g = np.asarray(mask.filter(ImageFilter.GaussianBlur(14)), np.float32) * 1.4
        base = np.zeros_like(arr)
        base[..., :3] = (hexrgb(glow) * 255).astype(np.uint8)
        base[..., 3] = np.clip(g, 0, 255).astype(np.uint8)
        im = Image.alpha_composite(Image.fromarray(base), im)
    return im


def ink_flowers(sprites, out):
    """心之花：把三渲二玫瑰（俯视）阈值化成纯黑白的墨线稿"""
    for st in ("0.05", "0.40", "0.75", "1.00"):
        spr = Image.open(os.path.join(sprites, f"rose_paleblue_90_{st}.png")).convert("RGBA").resize((1024, 1024), Image.LANCZOS)
        a = np.asarray(spr, np.float32) / 255
        lum = a[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
        ink = (lum > 0.8).astype(np.float32)
        rgba = np.zeros((1024, 1024, 4), np.uint8)
        rgba[..., :3] = (ink[..., None] * 255).astype(np.uint8)
        rgba[..., 3] = ((a[..., 3] > 0.5) * 255).astype(np.uint8)
        Image.fromarray(rgba).filter(ImageFilter.SMOOTH_MORE).save(os.path.join(out, f"inkrose_{st}.png"))


def watercolor(sprites, out):
    """永远之歌：灰色水彩花（晕开的边 + 边缘积色 + 颗粒）"""
    rng = np.random.default_rng(11)
    for k, (c, e) in enumerate([("white", 55), ("paleblue", 25), ("blue", 55), ("white", 90)]):
        spr = Image.open(os.path.join(sprites, f"rose_{c}_{e}_1.00.png")).convert("RGBA").resize((900, 900), Image.LANCZOS)
        spr = spr.rotate(rng.normal(0, 25), resample=Image.BICUBIC)
        arr = np.asarray(spr, np.float32) / 255
        alpha = Image.fromarray((arr[..., 3] * 255).astype(np.uint8))
        bleed = np.asarray(alpha.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255
        inner = np.asarray(alpha.filter(ImageFilter.GaussianBlur(3)), np.float32) / 255
        edge = np.clip(inner - np.asarray(alpha.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255, 0, 1)
        lum = arr[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
        gran = fbm(900, 900, 20 + k, octaves=5, base=24, gain=0.6)
        dens = np.clip(bleed * 0.35 + edge * 0.9 + (1 - lum) * inner * 0.45, 0, 1) * (0.75 + 0.5 * gran)
        rgba = np.zeros((900, 900, 4), np.uint8)
        rgba[..., :3] = (hexrgb("#5d646c") * 255).astype(np.uint8)
        rgba[..., 3] = (np.clip(dens, 0, 1) * 235).astype(np.uint8)
        Image.fromarray(rgba).save(os.path.join(out, f"wc_{k}.png"))


def ice_fg(sprites, out):
    """星空场景的前景：发光的草 + 冰色的三渲二玫瑰（保留素材里的线条，不再是剪影色块）"""
    grass = tinted(silhouettes(sprites, PW, 560, 6, roses=0), "#e9f8ff", blur=1.0, glow="#7fd0ff")
    rng = np.random.default_rng(7)
    ramp_lo, ramp_hi = hexrgb("#3d86bf"), hexrgb("#f4fcff")
    for k in range(7):
        side = -1 if k % 2 == 0 else 1
        x0 = PW * (0.5 + side * (0.25 + 0.22 * rng.random()))
        sz = int(170 + 120 * rng.random())
        top = 560 * (0.22 + 0.35 * rng.random())
        stem = Image.new("RGBA", grass.size, (0, 0, 0, 0))
        ImageDraw.Draw(stem).line([(x0, 560), (x0 + rng.normal(0, 12), top)], fill=(214, 240, 255, 255), width=4)
        grass = Image.alpha_composite(grass, stem)
        name = ["rose_paleblue_25_1.00.png", "rose_white_55_1.00.png", "rose_blue_25_1.00.png"][k % 3]
        spr = Image.open(os.path.join(sprites, name)).convert("RGBA").resize((sz, sz), Image.LANCZOS)
        spr = spr.rotate(rng.normal(0, 15), resample=Image.BICUBIC)
        a = np.asarray(spr, np.float32) / 255
        lum = np.clip((a[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32) - 0.15) / 0.7, 0, 1)
        rgba = np.zeros((sz, sz, 4), np.uint8)
        rgba[..., :3] = (mix(np.broadcast_to(ramp_lo, (sz, sz, 3)), ramp_hi, lum) * 255).astype(np.uint8)
        rgba[..., 3] = (a[..., 3] * 255).astype(np.uint8)
        glow = Image.fromarray(rgba[..., 3]).filter(ImageFilter.GaussianBlur(12))
        halo = np.zeros((sz, sz, 4), np.uint8)
        halo[..., :3] = (hexrgb("#9fdcff") * 255).astype(np.uint8)
        halo[..., 3] = np.clip(np.asarray(glow, np.float32) * 1.3, 0, 255).astype(np.uint8)
        layer = Image.new("RGBA", grass.size, (0, 0, 0, 0))
        pos = (int(x0 - sz / 2), int(top - sz / 2))
        layer.paste(Image.fromarray(halo), pos)
        grass = Image.alpha_composite(grass, layer)
        layer = Image.new("RGBA", grass.size, (0, 0, 0, 0))
        layer.paste(Image.fromarray(rgba), pos)
        grass = Image.alpha_composite(grass, layer)
    grass.save(os.path.join(out, "fg_ice.png"))


def main():
    sprites, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    plate_sepia(out)
    plate_rain(out)
    plate_paper(out, "paper.jpg", "#f4f1ea", "#b9b2a3", 12)
    plate_paper(out, "white.jpg", "#f6f6f4", "#9a9a9a", 14)
    plate_warm(out)
    plate_sky(out)
    m = silhouettes(sprites, PW, 560, 5)
    tinted(m, "#3e2c1b", blur=2.5).save(os.path.join(out, "fg_sepia.png"))
    tinted(m, "#2f3338", blur=2.5).save(os.path.join(out, "fg_rain.png"))
    ice_fg(sprites, out)
    ink_flowers(sprites, out)
    watercolor(sprites, out)
    print("ok", sorted(os.listdir(out)))


if __name__ == "__main__":
    main()
