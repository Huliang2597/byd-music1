#!/usr/bin/env python3
"""折中方案第 2 步：用 sprites.py 渲出的三渲二素材在 SVG 里做 2.5D 动画，并叠加 compose.py 的歌词 / 转场。

玫瑰按 3D 坐标投影到星球素材上（与 sprites.py 的正交相机一致），
按所在位置的朝向选俯视 / 斜视 / 侧视素材，花轴沿投影后的球面法线旋转。

用法:
  pv2d.py <素材目录> <音频> <歌词.lrc> <features.npz> <fonts目录> <输出.mp4> [--start 217 --end 237.5] [--still 秒,...] [--workers 4]
"""
import argparse
import math
import os
import random
import re
import subprocess
import sys
import time
from multiprocessing import Process

import imageio_ffmpeg
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import compose as C  # noqa: E402
from story import stage_html  # noqa: E402

W, H, FPS = 1920, 1080, 24
T1, T2, T3, T4 = C.T_LINE1, C.T_LINE2, C.T_LINE3, C.T_LINE4
T_MEET, T_THROUGH = C.T_MEET, C.T_THROUGH
C.CUTS.append(T1)  # 贴地 → 升起也切一下

# 与 sprites.py 保持一致
CAM_E = math.radians(20)
CV = np.array([0, -math.cos(CAM_E), math.sin(CAM_E)])  # 指向相机
RV = np.array([1.0, 0, 0])
UV = np.array([0, math.sin(CAM_E), math.cos(CAM_E)])
PLANET_R_PX, HD_R_PX = 1024 / 2.08, 2560 / 2.08
HD_ANGLE = 280
FINE = range(280, 346)
ROSE_UNITS = 2.9  # 玫瑰素材覆盖的局部单位
STAGES = [0.05, 0.4, 0.75, 1.0]
COLORS = ["white", "paleblue", "blue", "mint", "pink", "cream"]
WEIGHTS = [0.30, 0.26, 0.20, 0.12, 0.06, 0.06]
PETAL_FILL = {"white": "#f3f9ff", "paleblue": "#a9d0ff", "blue": "#4f78ec", "mint": "#9ceacf", "pink": "#fac8da", "cream": "#ffe8a8"}
DOOR_BASE_Y = 512 + 0.8 * math.cos(math.radians(12)) / 2.4 * 1024  # door.png 中门底中心的 y


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b - a) * t


def f1(x):
    return f"{x:.1f}"


def rz(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def sph(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])


def unit(v):
    return v / np.linalg.norm(v)


class Rose:
    __slots__ = ("dir", "size", "color", "phase", "spin", "giant")

    def __init__(self, d, size, color, phase, spin, giant=False):
        self.dir, self.size, self.color, self.phase, self.spin, self.giant = unit(d), size, color, phase, spin, giant


class PV2D:
    def __init__(self, sprites, features):
        self.sp = os.path.abspath(sprites)
        d = np.load(features)
        self.kick = d["kick"]
        rnd = random.Random(7)
        self.p0 = sph(18, -8)
        door_dir = sph(12, 150)
        roses = []
        golden = math.pi * (3 - math.sqrt(5))
        for k in range(150):
            y = 1 - 2 * (k + 0.5) / 150
            r = math.sqrt(1 - y * y)
            roses.append((np.array([r * math.cos(golden * k), r * math.sin(golden * k), y]), rnd.uniform(0.2, 0.36), False))
        for _ in range(55):
            roses.append((self.p0 + np.array([rnd.gauss(0, 0.15) for _ in range(3)]), rnd.uniform(0.14, 0.26), False))
        for lat, lon in [(32, 200), (-18, 232), (8, 258), (48, 238), (-42, 205), (18, 172), (-2, 215), (60, 150), (-60, 280),
                         (25, 300), (-30, 320), (5, 335)]:
            roses.append((sph(lat, lon), rnd.uniform(0.95, 1.3), True))
        self.roses = [Rose(dd, s, rnd.choices(COLORS, WEIGHTS)[0], rnd.uniform(0, 6.28), rnd.uniform(0, 360), g)
                      for dd, s, g in roses if np.linalg.norm(unit(dd) - door_dir) > 0.3]
        # 地平线上的一簇花（贴地镜头、门前镜头用）
        self.limb = []
        for k in range(46):
            a = rnd.uniform(-1, 1)
            self.limb.append((a, rnd.uniform(0.0, 0.35), rnd.uniform(0.05, 0.14), rnd.choices(COLORS, WEIGHTS)[0], rnd.uniform(0, 6.28)))
        self.limb.sort(key=lambda x: x[1])
        self.stars = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.6, 2.0), rnd.uniform(0, 6.28)) for _ in range(170)]
        self.petals = [(rnd.random(), rnd.random(), rnd.random(), rnd.uniform(7, 16), rnd.choices(COLORS, WEIGHTS)[0]) for _ in range(160)]

    # ------------------------------------------------------------ helpers

    def kick_at(self, t):
        i = int(round(t * FPS))
        return float(self.kick[min(max(i, 0), len(self.kick) - 1)])

    def href(self, name):
        return f"file://{self.sp}/{name}"

    def planet_img(self, theta, cx, cy, rpx, hd=False):
        if hd:
            name, base = "planet_hd.png", HD_R_PX
        else:
            deg = int(round(theta)) % 360
            if deg not in FINE:
                deg = int(round(deg / 5)) * 5 % 360
            name, base = f"planet_{deg:03d}.png", PLANET_R_PX
        size = (2560 if hd else 1024) * rpx / base
        return f'<image href="{self.href(name)}" x="{f1(cx - size / 2)}" y="{f1(cy - size / 2)}" width="{f1(size)}" height="{f1(size)}"/>'

    def rose_img(self, color, elev, bloom, x, y, width, angle, opacity=1.0):
        b = clamp(bloom, 0, 1.0)
        lo = max(i for i, s in enumerate(STAGES) if s <= max(b, STAGES[0]))
        hi = min(lo + 1, len(STAGES) - 1)
        frac = 0.0 if hi == lo else clamp((b - STAGES[lo]) / (STAGES[hi] - STAGES[lo]))
        tr = f'transform="translate({f1(x)} {f1(y)}) rotate({f1(angle)})"'
        half = width / 2
        out = [f'<g {tr} opacity="{opacity:.3f}">',
               f'<image href="{self.href(f"rose_{color}_{elev}_{STAGES[lo]:.2f}.png")}" x="{f1(-half)}" y="{f1(-half)}" width="{f1(width)}" height="{f1(width)}"/>']
        if frac > 0.02:
            out.append(f'<image href="{self.href(f"rose_{color}_{elev}_{STAGES[hi]:.2f}.png")}" x="{f1(-half)}" y="{f1(-half)}" '
                       f'width="{f1(width)}" height="{f1(width)}" opacity="{frac:.3f}"/>')
        out.append('</g>')
        return "".join(out)

    def draw_roses(self, theta, cx, cy, rpx, bloom_fn, t, sway=0.0, giants_only=False):
        rot = rz(theta)
        items = []
        for r in self.roses:
            if giants_only and not r.giant:
                continue
            q = rot @ r.dir
            d = float(q @ CV)
            if d < 0.03:
                continue
            x = cx + rpx * float(q @ RV)
            y = cy - rpx * float(q @ UV)
            width = ROSE_UNITS * (r.size / 4) * rpx
            if x < -width or x > W + width or y < -width or y > H + width:
                continue
            elev = 90 if d > 0.8 else (55 if d > 0.45 else 25)
            angle = r.spin if elev == 90 else math.degrees(math.atan2(float(q @ RV), float(q @ UV)))
            angle += sway * math.sin(t * 2.2 + r.phase)
            items.append((d, self.rose_img(r.color, elev, bloom_fn(r), x, y, width, angle)))
        items.sort(key=lambda it: it[0])
        return "".join(s for _, s in items)

    def draw_limb_roses(self, cx, top_y, span, scale, bloom, t, skip=None):
        """地平线（y=top_y）附近的一排侧视玫瑰；d 越大越靠前、越低、越大。"""
        out = []
        for a, d, size, color, ph in self.limb:
            x = cx + a * span
            if skip and skip[0] < x < skip[1]:
                continue
            y = top_y + 25 + d * 380 * scale
            width = size * 2600 * scale * (0.6 + 1.8 * d)
            out.append(self.rose_img(color, 25, bloom, x, y, width, 3 * math.sin(t * 2 + ph)))
        return "".join(out)

    def petal(self, x, y, s, rot, color, opacity):
        return (f'<ellipse rx="{f1(s)}" ry="{f1(s * 0.55)}" fill="{PETAL_FILL[color]}" stroke="#16404a" stroke-width="1" '
                f'opacity="{opacity:.2f}" transform="translate({f1(x)} {f1(y)}) rotate({f1(rot)})"/>')

    def sky(self, t, bright=0.0):
        top = "#04101c" if bright < 0.5 else "#0a2436"
        parts = ['<defs><linearGradient id="skyg" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="#0f3a48"/></linearGradient>'
                 '<radialGradient id="portal"><stop offset="0" stop-color="#fff"/><stop offset="0.5" stop-color="#e6fffb" stop-opacity="0.8"/>'
                 '<stop offset="1" stop-color="#9ff5ea" stop-opacity="0"/></radialGradient>'
                 '<radialGradient id="orbg"><stop offset="0" stop-color="#fff"/><stop offset="0.25" stop-color="#e8fffb" stop-opacity="0.9"/>'
                 '<stop offset="1" stop-color="#8ff0e6" stop-opacity="0"/></radialGradient>'
                 '<radialGradient id="orbp"><stop offset="0" stop-color="#fff"/><stop offset="0.25" stop-color="#ffe6f1" stop-opacity="0.9"/>'
                 '<stop offset="1" stop-color="#f7b7d2" stop-opacity="0"/></radialGradient></defs>',
                 f'<rect width="{W}" height="{H}" fill="url(#skyg)"/>']
        for x, y, r, ph in self.stars:
            parts.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{r:.1f}" fill="#e6fffc" opacity="{0.35 + 0.35 * math.sin(t * 1.7 + ph):.2f}"/>')
        return "".join(parts)

    # ------------------------------------------------------------ shots

    def world(self, t):
        kick = self.kick_at(t)
        shake = 4 * kick
        out = [self.sky(t), f'<g transform="translate({f1(shake * math.sin(t * 91))} {f1(shake * math.cos(t * 77))})">']
        if t < T1:
            out.append(self.shot_ground(t))
        elif t < T2:
            out.append(self.shot_rise(t))
        elif t < T3:
            out.append(self.shot_orbit(t))
        elif t < T4:
            out.append(self.shot_door(t))
        else:
            out.append(self.shot_wide(t))
        out.append('</g>')
        return "".join(out)

    def shot_ground(self, t):
        p = (t - 217.0) / (T1 - 217.0)
        rpx = 5200
        top = 700
        cx = 960 + lerp(40, -40, p)
        out = [self.planet_img(HD_ANGLE, cx, top + rpx, rpx, hd=True),
               self.draw_limb_roses(cx, top, 1500, 1.0, 0.06 + 0.04 * math.sin(t * 3), t)]
        for k, (a, b, c, s, col) in enumerate(self.petals[:70]):
            x = (a * W + t * 30 * (0.5 + c)) % W
            y = 80 + b * 560 + 18 * math.sin(t * 1.3 + k)
            out.append(self.petal(x, y, s * 0.8, t * 60 * (0.5 + c) + k * 20, col, 0.75))
        return "".join(out)

    def rise_frame(self, t):
        k = ease_io((t - T1) / (T2 - T1))
        rpx = math.exp(lerp(math.log(6200), math.log(410), k))
        q0 = rz(HD_ANGLE) @ unit(self.p0)
        s1 = np.array([960 + 410 * float(q0 @ RV), 560 - 410 * float(q0 @ UV)])
        s = np.array([960, 540]) * (1 - k) + s1 * k
        cx = s[0] - rpx * float(q0 @ RV)
        cy = s[1] + rpx * float(q0 @ UV)
        return rpx, cx, cy

    def shot_rise(self, t):
        rpx, cx, cy = self.rise_frame(t)
        wave = (t - T1) * 0.55
        p0 = unit(self.p0)

        def bloom(r):
            ang = math.acos(clamp(float(r.dir @ p0), -1, 1))
            return 0.06 + ease_out((wave - ang) / 0.25)

        out = [self.planet_img(HD_ANGLE, cx, cy, rpx, hd=rpx > 600), self.draw_roses(HD_ANGLE, cx, cy, rpx, bloom, t, 3)]
        # 花瓣从花田中心向外、向镜头冲出
        for k, (a, b, c, s, col) in enumerate(self.petals):
            q = clamp((t - T1 - c * 0.8) / 3.0)
            if q <= 0:
                continue
            ang = a * 6.28 + q * 2
            rad = (60 + 1300 * q ** 1.4) * (0.4 + b)
            x, y = 960 + rad * math.cos(ang), 540 + rad * math.sin(ang)
            out.append(self.petal(x, y, s * (0.6 + 2.2 * q), t * 90 + k * 30, col, 0.9 * (1 - q ** 3)))
        return "".join(out)

    def orb(self, k, tt):
        p = clamp((tt - T2) / (T_MEET - T2))
        ang = math.radians(lerp(-160, 270, p) + (0 if k == 0 else 180) * (1 - ease_out(p)))
        rx, ry = lerp(760, 60, ease_out(p) ** 0.8), lerp(230, 20, ease_out(p) ** 0.8)
        cx, cy = 960, lerp(560, 300, ease_out(p))
        x, y = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
        behind = math.sin(ang) < 0 and abs(x - 960) < 430 and p < 0.9
        if tt > T_MEET:
            q = tt - T_MEET
            x += 50 * math.cos(q * 6 + k * math.pi) * min(q, 1)
            y += -q * 90 + 20 * math.sin(q * 6 + k * math.pi)
            behind = False
        return x, y, behind

    def shot_orbit(self, t):
        p = (t - T2) / (T3 - T2)
        theta = lerp(280, 320, ease_io(p))
        rpx, cx, cy = lerp(410, 440, p), 960, 560
        back, front = [], []
        for k in range(2):
            grad = "orbg" if k == 0 else "orbp"
            for j in range(16, -1, -1):
                x, y, behind = self.orb(k, t - j * 0.035)
                r = (26 if j == 0 else 14 * (1 - j / 17)) * (1.4 if j == 0 else 1)
                el = f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{f1(r * 2.4)}" fill="url(#{grad})" opacity="{1 - j / 18:.2f}"/>'
                (back if behind else front).append(el)
        glow = 0.0
        if t > T_MEET:
            glow = ease_out((t - T_MEET) / 0.35) * math.exp(-(t - T_MEET) * 1.3)
        out = back + [self.planet_img(theta, cx, cy, rpx), self.draw_roses(theta, cx, cy, rpx, lambda r: 1.0, t, 3)]
        if glow > 0.01:
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{f1(rpx)}" fill="#e9fffb" opacity="{0.35 * glow:.3f}"/>')
        for k, (a, b, c, s, col) in enumerate(self.petals[:90]):
            ang = a * 6.28 + t * (0.25 + 0.2 * b)
            r = rpx * (1.3 + 0.8 * c)
            x, y = cx + r * math.cos(ang), cy + r * 0.32 * math.sin(ang) + (b - 0.5) * 300
            if math.sin(ang) > 0 or abs(x - cx) > rpx:
                out.append(self.petal(x, y, s * 0.8, t * 80 + k * 17, col, 0.85))
        return "".join(out + front)

    def shot_door(self, t):
        p = (t - T3) / (T_THROUGH - T3)
        k = clamp(p) ** 3.6
        rpx, top = 5200, 800
        door_h = 470
        door_w = 1024 * door_h / (1.65 / 2.4 * 1024)
        portal_y = top - door_h * 0.45
        zoom = lerp(1.0, 16.0, k)
        out = [f'<g transform="translate(960 {f1(portal_y)}) scale({zoom:.4f}) translate(-960 {f1(-portal_y)})">',
               self.planet_img(HD_ANGLE, 960, top + rpx, rpx, hd=True),
               self.draw_limb_roses(960, top, 1400, 0.85, 1.0, t, skip=(700, 1220))]
        dx, dy = 960 - door_w / 2, top - DOOR_BASE_Y * door_w / 1024
        out.append(f'<image href="{self.href("door.png")}" x="{f1(dx)}" y="{f1(dy)}" width="{f1(door_w)}" height="{f1(door_w)}"/>')
        glow = lerp(0.25, 1.0, clamp(p) ** 1.5)
        out.append(f'<ellipse cx="960" cy="{f1(portal_y)}" rx="{f1(door_w * 0.3)}" ry="{f1(door_h * 0.5)}" fill="url(#portal)" opacity="{glow:.3f}"/>')
        for j, (a, b, c, s, col) in enumerate(self.petals[:80]):
            q = (t * 0.35 + a) % 1
            x = 960 + (b - 0.5) * 1800 * (0.4 + q)
            y = portal_y + (c - 0.5) * 500 - q * 200
            out.append(self.petal(x, y, s * (0.5 + 1.2 * q), t * 70 + j * 23, col, 0.8 * math.sin(q * math.pi)))
        out.append('</g>')
        return "".join(out)

    def shot_wide(self, t):
        p = (t - T4) / 4.7
        theta = lerp(320, 345, p)
        rpx, cx, cy = lerp(345, 305, ease_out(p)), 960, 600
        delays = {}

        def bloom(r):
            if not r.giant:
                return 1.0
            d = delays.setdefault(id(r), 0.15 + (r.phase % 1) * 0.9)
            return ease_out((t - T4 - d) / 1.5)

        ring_back, ring_front = [], []
        tilt = math.radians(22)
        for k, (a, b, c, s, col) in enumerate(self.petals):
            ang = b * 6.28 + t * 0.35
            r = 1.5 + 0.45 * c
            x3, y3, z3 = r * math.cos(ang), r * math.sin(ang), (a - 0.5) * 0.09
            v = np.array([x3, y3 * math.cos(tilt) - z3 * math.sin(tilt), y3 * math.sin(tilt) + z3 * math.cos(tilt)])
            d = float(v @ CV)
            x, y = cx + rpx * float(v @ RV), cy - rpx * float(v @ UV)
            el = self.petal(x, y, s * 0.9, t * 70 + k * 13, col, 0.9)
            (ring_front if d > 0 else ring_back).append(el)
        return "".join(ring_back + [self.planet_img(theta, cx, cy, rpx), self.draw_roses(theta, cx, cy, rpx, bloom, t, 2)] + ring_front)


class Frame:
    """world 层 + compose.Overlay 的叠加层。"""

    def __init__(self, pv, overlay):
        self.pv, self.ov = pv, overlay

    def svg(self, i):
        s = self.ov.svg(i)
        return re.sub(r'<image href="file://[^"]*/\d{6}\.png" width="1920" height="1080"/>', lambda _: self.pv.world(i / FPS), s, count=1)


class Renderer:
    def __init__(self, frame, fonts_dir, workdir, warm):
        self.frame_src = frame
        path = os.path.join(workdir, ".pv2d_stage.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(stage_html(fonts_dir, warm))
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--font-render-hinting=none", "--force-color-profile=srgb",
                                                     "--allow-file-access-from-files"])
        self.page = self.browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        self.page.goto("file://" + path)
        self.page.evaluate("document.fonts.ready.then(() => true)")
        self.page.wait_for_timeout(300)

    def frame(self, i):
        self.page.evaluate("""s => new Promise(res => {
            const el = document.getElementById('s'); el.innerHTML = s;
            const urls = [...new Set([...el.querySelectorAll('image')].map(n => n.getAttribute('href')))];
            Promise.all(urls.map(u => new Promise(r => { const im = new Image(); im.onload = im.onerror = r; im.src = u; })))
              .then(() => requestAnimationFrame(() => requestAnimationFrame(() => res(true))));
        })""", self.frame_src.svg(i))
        return self.page.screenshot(type="jpeg", quality=100)

    def close(self):
        self.browser.close()
        self.pw.stop()


def build(args):
    pv = PV2D(args.sprites, args.features)
    ov = C.Overlay("/nonexistent", args.lrc, args.features, FPS)
    warm = "".join(sorted({c for _, _, s in ov.lines for c in s})) + "花隈千冬✿"
    return Frame(pv, ov), warm


def worker(args, a, b, seg):
    frame, warm = build(args)
    r = Renderer(frame, args.fonts, os.path.dirname(os.path.abspath(args.output)), warm)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen([ff, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p",
                             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", seg], stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(a, b):
        proc.stdin.write(r.frame(i))
        if (i - a) % 60 == 0:
            print(f"[{os.path.basename(seg)}] {i - a + 1}/{b - a}，{(i - a + 1) / (time.time() - t0):.1f} 帧/秒", flush=True)
    r.close()
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg 失败")


def main():
    ap = argparse.ArgumentParser()
    for name in ("sprites", "audio", "lrc", "features", "fonts", "output"):
        ap.add_argument(name)
    ap.add_argument("--start", type=float, default=217.0)
    ap.add_argument("--end", type=float, default=237.5)
    ap.add_argument("--still", default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    args.fonts = os.path.abspath(args.fonts)
    if args.still:
        frame, warm = build(args)
        r = Renderer(frame, args.fonts, os.path.dirname(os.path.abspath(args.output)), warm)
        for s in args.still.split(","):
            path = f"{os.path.splitext(args.output)[0]}_{float(s):07.2f}.jpg"
            with open(path, "wb") as f:
                f.write(r.frame(round(float(s) * FPS)))
            print(path)
        r.close()
        return
    a, b = round(args.start * FPS), round(args.end * FPS)
    work = os.path.splitext(os.path.abspath(args.output))[0] + "_segments"
    os.makedirs(work, exist_ok=True)
    k = args.workers
    bounds = [a + (b - a) * j // k for j in range(k + 1)]
    segs = [os.path.join(work, f"seg{j:02d}.mp4") for j in range(k)]
    procs = [Process(target=worker, args=(args, bounds[j], bounds[j + 1], segs[j])) for j in range(k)]
    t0 = time.time()
    for p in procs:
        p.start()
    for p in procs:
        p.join()
        if p.exitcode != 0:
            sys.exit("渲染失败")
    print(f"渲染用时 {time.time() - t0:.0f} 秒")
    listing = os.path.join(work, "list.txt")
    with open(listing, "w") as f:
        f.writelines(f"file '{s}'\n" for s in segs)
    dur = (b - a) / FPS
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing,
                    "-ss", f"{a / FPS:.4f}", "-t", f"{dur:.4f}", "-i", args.audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "320k", "-af", f"afade=t=in:d=0.3,afade=t=out:st={dur - 0.6:.3f}:d=0.6",
                    "-movflags", "+faststart", "-shortest", args.output], check=True)
    print("输出:", args.output)


if __name__ == "__main__":
    main()
