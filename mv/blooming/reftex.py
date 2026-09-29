#!/usr/bin/env python3
"""refpv.py 的素材：照参考特效谱的画面做的雾面底图、发光植物、烟雾花、水彩牡丹、花影（numpy/cv2 程序化生成）。

用法: python3 reftex.py <输出目录>
"""
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fxtex as F  # noqa: E402
import rose  # noqa: E402

PW, PH = F.PW, F.PH


def warp_fbm(w, h, seed, base=3, amt=0.12):
    """域扭曲的分形噪声：比普通 fbm 更像烟雾和水墨"""
    n0 = F.fbm(w, h, seed, base=base)
    wx = F.fbm(w, h, seed + 100, base=2) - 0.5
    wy = F.fbm(w, h, seed + 200, base=2) - 0.5
    x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(n0, x + wx * amt * w, y + wy * amt * h, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def save(a, path):
    F.save_rgb(a, path)


def plate(out, name, stops, fog_col, fog_amt, seed, glow=None, ink=None):
    x, y = F.grid(PW, PH)
    col = F.vgrad(PH, PW, stops)
    fog = warp_fbm(PW, PH, seed)
    col = F.mix(col, F.hexrgb(fog_col), np.clip((fog - 0.45) * 2.0, 0, 1) * fog_amt)
    if ink:  # 左下角的水墨云纹
        c, amt = ink
        wash = warp_fbm(PW, PH, seed + 7, base=4, amt=0.2)
        band = np.clip(1.2 - (x * 0.9 + (1 - y) * 0.9), 0, 1)
        col = F.mix(col, F.hexrgb(c), np.clip((wash - 0.5) * 3, 0, 1) * band * amt)
    if glow:
        gx, gy, r, c, amt = glow
        d = np.sqrt(((x - gx) * 1.78) ** 2 + (y - gy) ** 2)
        col = F.mix(col, F.hexrgb(c), np.exp(-(d / r) ** 2) * amt)
    save(col * F.vignette(PW, PH, 0.35)[..., None], os.path.join(out, name))


def rays_top(out):
    w, h = 2200, 1300
    x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    cx, cy = w * 0.5, -h * 0.35
    ang = np.arctan2(x - cx, y - cy)
    r = np.hypot(x - cx, y - cy) / h
    stripes = F.fbm(4096, 8, 41, octaves=5, base=10)[4]
    k = np.interp(ang, np.linspace(-1.2, 1.2, 4096), stripes)
    a = np.clip((k - 0.42) * 2.4, 0, 1) ** 1.4 * np.exp(-(r - 0.35) * 1.3) * np.clip((1 - y / h) * 1.4, 0, 1)
    a *= np.clip(np.minimum(x, w - x) / (w * 0.2), 0, 1)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (cv2.GaussianBlur(np.clip(a, 0, 1), (0, 0), 5) * 255).astype(np.uint8)
    Image.fromarray(rgba).save(os.path.join(out, "rays_top.png"))


def glow_png(mask, core, halo, out_path, blur=1.2, halo_sigma=22, halo_gain=1.5, shade=None):
    """白色发光剪影：核心 + 大范围光晕"""
    m = cv2.GaussianBlur(mask, (0, 0), blur)
    g = np.clip(cv2.GaussianBlur(mask, (0, 0), halo_sigma) * halo_gain, 0, 1)
    h, w = mask.shape
    rgb = np.zeros((h, w, 3), np.float32)
    a = np.clip(m + g * (1 - m), 0, 1)
    core_c, halo_c = F.hexrgb(core), F.hexrgb(halo)
    t = np.where(a > 0, m / np.maximum(a, 1e-4), 0)[..., None]
    rgb = halo_c * (1 - t) + core_c * t
    if shade is not None:
        rgb = rgb * shade[..., None]
    rgba = np.concatenate([np.clip(rgb, 0, 1), a[..., None]], -1)
    Image.fromarray((rgba * 255).astype(np.uint8)).save(out_path)


def frost_plant(d, x0, y0, height, lean, s, rng):
    """冰霜般的植物：一根弯茎 + 往上斜伸的细长叶片（像火焰/蕨叶）"""
    pts = []
    for k in range(24):
        v = k / 23
        pts.append((x0 + lean * height * v * v + rng.normal(0, 1.5), y0 - height * v))
    for k in range(len(pts) - 1):
        d.line([pts[k], pts[k + 1]], fill=255, width=max(2, int(3.5 * s * (1 - k / 24))))
    for k in range(3, 23):
        v = k / 23
        px, py = pts[k]
        L = height * (0.3 * (1 - v) + 0.06) * (0.7 + 0.6 * rng.random())
        if rng.random() < 0.35:
            continue
        for side in (-1, 1):
            ang = math.radians(90 - side * (28 + 30 * rng.random())) + lean * 0.5
            wdt = L * (0.045 + 0.04 * rng.random())
            ex, ey = px + side * L * math.cos(ang) * 0.9, py - L * math.sin(ang)
            nx, ny = -(ey - py), ex - px
            nl = math.hypot(nx, ny) or 1
            nx, ny = nx / nl * wdt, ny / nl * wdt
            mx, my = (px + ex) / 2, (py + ey) / 2
            d.polygon([(px, py), (mx + nx, my + ny), (ex, ey), (mx - nx, my - ny)], fill=255)
    tx, ty = pts[-1]
    d.polygon([(tx - 6 * s, ty + 10), (tx, ty - 26 * s), (tx + 6 * s, ty + 10)], fill=255)


def foliage(out, name, sides, seed, h=800, count=46):
    s = 2
    im = Image.new("L", (PW * s, h * s), 0)
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(seed)
    for _ in range(count):
        x = rng.random()
        edge = min(x, 1 - x)
        tall = (1 - min(edge * 3.2, 0.8)) if sides else (0.55 + 0.45 * rng.random())
        height = (160 + 560 * tall * (0.6 + 0.4 * rng.random())) * s
        frost_plant(d, x * PW * s, h * s + 20, height, rng.normal(0, 0.25), s, rng)
    m = np.asarray(im.resize((PW, h), Image.LANCZOS), np.float32) / 255
    shade = 0.78 + 0.22 * F.fbm(PW, h, seed + 3, base=8)
    glow_png(m, "#f4fbff", "#9cc6e6", os.path.join(out, name), blur=1.6, halo_sigma=26, halo_gain=1.6, shade=shade)


def smoke_flower(out, size=900):
    """心之花：一簇发光的白色云团（每一团都有上亮下暗的体积感）"""
    x, y = np.meshgrid(np.arange(size, dtype=np.float32), np.arange(size, dtype=np.float32))
    rng = np.random.default_rng(12)
    col = np.zeros((size, size), np.float32)
    alpha = np.zeros((size, size), np.float32)
    puffs = []
    for _ in range(48):
        cx = size / 2 + rng.normal(0, 105)
        cy = size / 2 + rng.normal(0, 85)
        r = 28 + 50 * rng.random() * (1.3 - min(1.0, math.hypot(cx - size / 2, cy - size / 2) / 260))
        puffs.append((cy, cx, r))
    noise = warp_fbm(size, size, 13, base=10, amt=0.05)
    xw = x + (F.fbm(size, size, 15, base=5) - 0.5) * 90  # 扭曲坐标，云团边缘不规则
    yw = y + (F.fbm(size, size, 16, base=5) - 0.5) * 90
    for cy, cx, r in sorted(puffs):  # 从上往下画：下面的云团压在上面的前面
        dd = np.hypot(xw - cx, yw - cy)
        p = np.clip(1 - (dd / r) ** 2, 0, 1)
        a = np.clip((p + (noise - 0.5) * 0.8 * np.sqrt(p)) * 2.2, 0, 1) * 0.9
        shade = np.clip(0.8 + 0.22 * (-(x - cx) * 0.35 - (y - cy) * 0.9) / r + 0.1 * np.sqrt(p), 0.5, 1.05)
        col = col * (1 - a) + shade * a
        alpha = alpha + a * (1 - alpha)
    fine = F.fbm(size, size, 14, base=24, gain=0.6)
    rgba = np.zeros((size, size, 4), np.float32)
    rgba[..., :3] = np.clip(col * (0.9 + 0.1 * fine), 0, 1)[..., None]
    rgba[..., :3] = cv2.GaussianBlur(rgba[..., :3], (0, 0), 2.5)
    rgba[..., 3] = cv2.GaussianBlur(alpha, (0, 0), 2.5)
    Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8)).save(os.path.join(out, "smoke_flower.png"))


def peonies(out):
    """永远之歌左下角的水彩牡丹：先用矢量玫瑰摆一丛，再做水彩化（晕染、边缘积色、颗粒）"""
    from playwright.sync_api import sync_playwright
    w, h = 1200, 1000
    parts = []
    for i, (cx, cy, R, sq, rot) in enumerate([(420, 420, 190, 0.72, 0.3), (720, 600, 150, 0.8, 1.2), (260, 700, 135, 0.66, 2.0),
                                               (620, 300, 95, 0.7, 0.8)]):
        parts.append(f'<path d="M{cx} {cy} Q{cx + 30} {cy + 250} {cx - 20} {h + 20}" stroke="#666" stroke-width="5" fill="none"/>')
        parts.append(rose.rose_svg(f"p{i}", cx, cy, R, "gray", 1.0, rot, sq, 40 + i, leaves=(i < 2)))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{"".join(parts)}</svg>'
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": w, "height": h})
        page.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
        png = page.screenshot(omit_background=True)
        b.close()
    im = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    lum = im[..., :3] @ np.array([0.114, 0.587, 0.299], np.float32)
    mask = im[..., 3]
    dmask = cv2.GaussianBlur(mask, (0, 0), 3)
    edge_n = warp_fbm(w, h, 51, base=6, amt=0.03)
    mask_s = np.clip((dmask + (edge_n - 0.5) * 0.5 - 0.3) / 0.4, 0, 1)
    dens = np.clip((1 - lum) * 1.7, 0, 1) * mask
    wash = cv2.GaussianBlur(dens, (0, 0), 2.5)
    edge = np.clip((wash - cv2.GaussianBlur(wash, (0, 0), 9)) * 2.2, 0, 1)
    gran = F.fbm(w, h, 52, octaves=5, base=40, gain=0.6)
    d = np.clip(0.16 * mask_s + wash * 0.8 + edge * 0.9, 0, 1) * (0.7 + 0.6 * gran)
    rgba = np.zeros((h, w, 4), np.float32)
    rgba[..., :3] = F.hexrgb("#3b4046")
    rgba[..., 3] = np.clip(d * mask_s, 0, 1) * 0.92
    Image.fromarray((rgba * 255).astype(np.uint8)).save(os.path.join(out, "peonies.png"))


def teal_silhouettes(out):
    """片尾的花影：郁金香/玫瑰/草的深色剪影，虚化"""
    s = 2
    w, h = PW, 620
    im = Image.new("L", (w * s, h * s), 0)
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(61)
    for _ in range(300):
        x0 = rng.random() * w * s
        F.blade(d, x0, h * s + 4, (40 + 160 * rng.random() ** 2) * s, rng.normal(0, 0.3), (4 + 5 * rng.random()) * s, 255)
    xs = np.sort(rng.random(7)) * 0.9 + 0.05
    for k in range(7):
        x0 = (xs[k] + rng.normal(0, 0.02)) * w * s
        top = h * s * (0.32 + 0.38 * rng.random())
        d.line([(x0, h * s), (x0 + rng.normal(0, 15), top)], fill=255, width=6 * s)
        r = (60 + 90 * rng.random()) * s
        if k % 2:  # 郁金香
            d.polygon([(x0 - r * 0.6, top), (x0 - r * 0.7, top - r * 0.9), (x0 - r * 0.25, top - r * 0.55), (x0, top - r * 1.1),
                       (x0 + r * 0.25, top - r * 0.55), (x0 + r * 0.7, top - r * 0.9), (x0 + r * 0.6, top), (x0, top + r * 0.35)], fill=255)
        else:
            d.ellipse([x0 - r * 0.8, top - r * 0.6, x0 + r * 0.8, top + r * 0.5], fill=255)
            d.ellipse([x0 - r * 0.5, top - r * 0.95, x0 + r * 0.5, top - r * 0.2], fill=255)
        for side in (-1, 1):
            ly = top + (h * s - top) * (0.35 + 0.3 * rng.random())
            d.polygon([(x0, ly), (x0 + side * r * 1.4, ly - r * 1.0), (x0 + side * r * 0.4, ly - r * 0.2)], fill=255)
    m = np.asarray(im.resize((w, h), Image.LANCZOS), np.float32) / 255
    m = cv2.GaussianBlur(m, (0, 0), 11)
    rgba = np.zeros((h, w, 4), np.float32)
    rgba[..., :3] = F.hexrgb("#16201f")
    rgba[..., 3] = m * 0.85
    Image.fromarray((rgba * 255).astype(np.uint8)).save(os.path.join(out, "fg_teal.png"))


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    plate(out, "warm.jpg", [(0, "#c9a488"), (0.5, "#e9ceb3"), (1, "#a8826a")], "#fff1e0", 0.45, 101,
          glow=(0.7, 0.2, 0.55, "#fff8ee", 0.85), ink=("#6f4a38", 0.45))
    plate(out, "gray.jpg", [(0, "#62666b"), (0.55, "#43474b"), (1, "#26292c")], "#8a8f94", 0.5, 102,
          glow=(0.5, 0.0, 0.5, "#9da2a7", 0.6))
    plate(out, "mauve.jpg", [(0, "#8a7472"), (0.5, "#9c8584"), (1, "#7a6664")], "#c7b3b0", 0.35, 103,
          glow=(0.5, 0.5, 0.45, "#e9d8d4", 0.5))
    plate(out, "ice.jpg", [(0, "#6d8ba3"), (0.55, "#98b2c4"), (1, "#cfdfe9")], "#e4eef4", 0.4, 104)
    plate(out, "navy.jpg", [(0, "#1a2233"), (0.6, "#2b3850"), (1, "#3c4a60")], "#56657c", 0.35, 105,
          glow=(0.5, 0.15, 0.35, "#4a5d7c", 0.6))
    plate(out, "paperw.jpg", [(0, "#f1f1f1"), (1, "#e6e6e6")], "#ffffff", 0.35, 106, glow=(0.62, 0.3, 0.6, "#fafafa", 0.6))
    plate(out, "teal.jpg", [(0, "#a8bcbc"), (0.45, "#8aa2a2"), (0.8, "#4d5f60"), (1, "#1c2426")], "#c3d3d2", 0.45, 107)
    rays_top(out)
    foliage(out, "foliage_ice.png", False, 71, count=24)
    foliage(out, "foliage_side.png", True, 72, h=900, count=26)
    smoke_flower(out)
    peonies(out)
    teal_silhouettes(out)
    print("ok", sorted(os.listdir(out)))


if __name__ == "__main__":
    main()
