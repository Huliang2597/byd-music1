#!/usr/bin/env python3
"""《Blooming Planet》叙事 PV · 全屏插画版：每句歌词是封面插画上的一个镜头。

封面先用 upscale.py 放大 4 倍，这里按镜头裁切、分场景调色（褐 / 灰 / 纯黑白 / 粉米 / 冰蓝 / 线稿 / 水彩），
画面上只做运镜、光效、粒子和文字，最后过 post.py 的合成后期。时间轴、歌词、字幕沿用 effectpv.py。
全片只有片尾才第一次露出全彩的完整封面。

用法:
  keyart.py --prepare <cover_x4.jpg> <fx目录>          # 生成 shot_*.jpg / cover_*.jpg
  keyart.py <fx目录> <音频> <歌词.lrc> <feat60.npz> <fonts目录> <输出.mp4> [--still 秒,...]
"""
import json
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effectpv as E  # noqa: E402
from effectpv import CX, CY, H, W, clamp, ease_io, ease_out, lerp, n  # noqa: E402

SR = 4  # 放大倍数
# 镜头：起止取景框（封面像素坐标 x, y, 宽；高 = 宽 × 9/16），调色
SHOTS = {
    "eyes": ((800, 330, 560), (850, 365, 470), "sepia"),
    "rain": ((700, 300, 800), (560, 560, 800), "gray"),
    "rose": ((741, 817, 380), (786, 857, 290), "ink"),
    "bouquet": ((600, 730, 520), (240, 420, 1100), "warm"),
    "stars": ((0, 0, 700), (70, 30, 540), "icy"),
    "smile": ((1060, 150, 540), (960, 330, 600), "icy"),
    "line": ((520, 300, 1000), (620, 360, 820), "line"),
    "score": ((100, 150, 1400), (200, 200, 1200), "wash"),
}


def hexrgb(s):
    return np.array([int(s[i:i + 2], 16) for i in (5, 3, 1)], np.float32) / 255  # BGR


def ramp(lum, stops):
    return np.stack([np.interp(lum, [p for p, _ in stops], [hexrgb(c)[k] for _, c in stops]) for k in range(3)], -1)


def grade(img, kind):
    lum = img @ np.array([0.114, 0.587, 0.299], np.float32)
    if kind == "sepia":
        out = ramp(lum, [(0, "#1c120a"), (0.4, "#7d5f3e"), (0.78, "#dcc7a0"), (1, "#fbf3e3")])
        return out * 0.9 + img * 0.1
    if kind == "gray":
        g = ramp(lum * 0.78, [(0, "#15181c"), (0.5, "#646b73"), (1, "#d9dfe5")])
        return g * 0.88 + img * 0.12
    if kind == "ink":
        v = np.clip((lum - 0.2) / 0.62, 0, 1)
        v = v * v * (3 - 2 * v)
        return np.repeat(v[..., None], 3, -1)
    if kind == "warm":
        out = ramp(lum, [(0, "#3e1222"), (0.35, "#a8506e"), (0.65, "#eaa0b6"), (1, "#fff5ee")])
        return out * 0.72 + img * 0.28
    if kind == "icy":
        out = ramp(lum, [(0, "#030a18"), (0.35, "#1b4b82"), (0.72, "#94cdf0"), (1, "#f4fcff")])
        return out * 0.9 + img * 0.1
    if kind == "line":
        blur = cv2.GaussianBlur(lum, (0, 0), 3)
        ln = np.clip((blur - lum - 0.025) * 7, 0, 1) + np.clip((0.22 - lum) * 5, 0, 1)
        ln = np.clip(ln, 0, 1) ** 0.8
        return ln[..., None] * hexrgb("#f4f8ff")
    if kind == "wash":
        blur = cv2.GaussianBlur(lum, (0, 0), 4)
        edge = np.clip((blur - lum) * 3, 0, 1)
        v = 0.6 + 0.4 * lum - 0.3 * edge
        tone = np.repeat(v[..., None], 3, -1) * hexrgb("#f1eee6")
        return tone * 0.85 + (img * 0.4 + 0.6) * hexrgb("#f1eee6") * 0.15
    raise ValueError(kind)


def rect(r):
    x, y, w = r
    return x, y, w, w * 9 / 16


def prepare(cover_x4, out):
    big = cv2.imread(cover_x4, cv2.IMREAD_COLOR)
    size = big.shape[1] // SR
    meta = {}
    for name, (a, b, kind) in SHOTS.items():
        ax, ay, aw, ah = rect(a)
        bx, by, bw, bh = rect(b)
        m = 0.03 * max(aw, bw)
        ux, uy = max(0, min(ax, bx) - m), max(0, min(ay, by) - m)
        ux2, uy2 = min(size, max(ax + aw, bx + bw) + m), min(size, max(ay + ah, by + bh) + m)
        d = min(SR, W / min(aw, bw))
        crop = big[int(uy * SR):int(uy2 * SR), int(ux * SR):int(ux2 * SR)]
        crop = cv2.resize(crop, (int((ux2 - ux) * d), int((uy2 - uy) * d)), interpolation=cv2.INTER_AREA)
        img = grade(crop.astype(np.float32) / 255, kind)
        cv2.imwrite(os.path.join(out, f"shot_{name}.jpg"), (np.clip(img, 0, 1) * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 95])
        meta[name] = [ux, uy, ux2 - ux, uy2 - uy]
        print(name, crop.shape, f"{d:.2f}")
    full = cv2.resize(big, (1600, 1600), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(out, "cover_full.jpg"), full, [cv2.IMWRITE_JPEG_QUALITY, 95])
    bg = cv2.resize(full[300:1200, 0:1600], (W, int(W * 900 / 1600)), interpolation=cv2.INTER_AREA)
    bg = cv2.GaussianBlur(bg, (0, 0), 38).astype(np.float32) * 0.55 + np.array([30, 24, 18], np.float32) * 0.45
    cv2.imwrite(os.path.join(out, "cover_blur.jpg"), np.clip(bg, 0, 255).astype(np.uint8)[:H], [cv2.IMWRITE_JPEG_QUALITY, 92])
    with open(os.path.join(out, "shots.json"), "w") as f:
        json.dump(meta, f)


def sine_io(x):
    x = clamp(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


class KeyArtPV(E.EffectPV):
    def __init__(self, fx, lrc, features):
        super().__init__(fx, lrc, features)
        with open(os.path.join(self.fx, "shots.json")) as f:
            self.meta = json.load(f)
        self.bok = np.random.default_rng(8).random((26, 6))
        E.STYLE["sepia"] = dict(fill="#2a1a0c", sub="#fff4e2", line="#3a2716", filt="glw")
        E.STYLE["ink"] = dict(fill="#ffffff", stroke="#0b0b0b", sw=2.6, sub="#ffffff", line="#ffffff", filt="sh")
        E.STYLE["bloom"] = dict(fill="#fff6f2", stroke="#7a3044", sw=1.6, sub="#fff6f2", line="#ffffff", filt="sh")
        E.STYLE["score"] = dict(fill="#2a2d31", sub="#2a2d31", line="#4a4f55", filt="glw")
        E.STYLE["star"] = dict(fill="#f4fbff", stroke="#16395e", sw=1.2, sub="#eef7ff", line="#bfe6ff", filt="sh")
        E.STYLE["line"] = dict(fill="#ffffff", sub="#e8e8e8", line="#ffffff", filt="sh")
        # 全屏插画上重新摆字：避开脸和眼睛
        moved = {"寄り添う": (250, 250, 124, True)}
        self.chunks = [(t0, s) + moved.get(s, (x, y, size, vert)) for t0, s, x, y, size, vert in self.chunks]

    # ---------- 镜头 ----------
    def cam(self, name, p, t):
        a, b, _ = SHOTS[name]
        x, y, w = (lerp(a[k], b[k], p) for k in range(3))
        return x, y, w

    def shot(self, name, t, p, extra=""):
        x, y, w = self.cam(name, p, t)
        k = W / w
        ux, uy, uw, uh = self.meta[name]
        dx = 2.2 * math.sin(t * 1.7) + 1.4 * math.sin(t * 2.9 + 1)  # 手持的微晃
        dy = 1.8 * math.sin(t * 1.3 + 2) + 1.2 * math.sin(t * 3.1)
        return self.img(f"shot_{name}.jpg", (ux - x) * k + dx, (uy - y) * k + dy, uw * k, uh * k, extra)

    def to_screen(self, name, p, cx, cy):
        x, y, w = self.cam(name, p, 0)
        k = W / w
        return (cx - x) * k, (cy - y) * k, k

    def overlay(self, name, op, blend):
        return self.img(name, -96, -54, 2112, 1188, f'opacity="{op:.3f}" style="mix-blend-mode:{blend}"')

    def bokeh(self, t, color, op, count=18):
        out = [f'<g style="mix-blend-mode:screen">']
        for b in self.bok[:count]:
            r = 18 + 70 * b[2] ** 2
            x = (b[0] * (W + 300) + (12 + 20 * b[3]) * t) % (W + 300) - 150
            y = (b[1] * (H + 200) - (8 + 14 * b[4]) * t) % (H + 200) - 100
            a = op * (0.25 + 0.75 * (0.5 + 0.5 * math.sin(t * (0.8 + b[5]) + b[5] * 9)))
            out.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}" fill="{color}" fill-opacity="{a * 0.18:.3f}" '
                       f'stroke="{color}" stroke-opacity="{a * 0.25:.3f}" stroke-width="1.5"/>')
        return "".join(out) + '</g>'

    def span(self, name):
        for k, (s, nm) in enumerate(self.scenes):
            if nm == name:
                s0 = s if s > -1e8 else (self.t_in if self.t_in is not None else 256.9)
                return s0, self.scenes[k + 1][0]
        raise KeyError(name)

    def prog(self, name, t, s0=None, s1=None):
        a, b = self.span(name)
        return (t - (s0 or a)) / ((s1 or b) - (s0 or a))

    # ---------- 场景 ----------
    def sc_sepia(self, t, u):
        p = sine_io(self.prog("sepia", t))
        out = [self.shot("eyes", t, p), self.overlay("sepia.jpg", 0.45, "multiply")]
        # 泪：在她左眼下缘聚起来，然后滑落
        tt = t - self.chunks[0][0] - 0.3
        if tt > 0:
            sx, sy, k = self.to_screen("eyes", p, 938, 545)
            grow = ease_out(tt / 0.6)
            fall = ease_io((tt - 0.7) / 1.4) * 38 * k
            r = 5.5 * k * (0.4 + 0.6 * grow)
            y = sy + fall
            out.append(f'<path d="M{n(sx)} {n(sy - r * 0.5)} L{n(sx)} {n(y)}" stroke="#fff8ec" stroke-width="{n(r * 0.35)}" '
                       f'opacity="{0.35 * clamp(fall / 30):.3f}" stroke-linecap="round"/>')
            out.append(f'<g transform="translate({n(sx)} {n(y)})" opacity="0.92"><path d="M0 {n(-r * 1.9)} C{n(r * 0.6)} {n(-r * 0.8)} {n(r)} 0 0 {n(r)} '
                       f'C{n(-r)} 0 {n(-r * 0.6)} {n(-r * 0.8)} 0 {n(-r * 1.9)} Z" fill="#f6ead6" fill-opacity="0.55" stroke="#fffaf0" stroke-width="1.4"/>'
                       f'<ellipse cx="{n(-r * 0.3)}" cy="{n(-r * 0.2)}" rx="{n(r * 0.18)}" ry="{n(r * 0.35)}" fill="#ffffff"/></g>')
        out.append(self.bokeh(t, "#ffe9c4", 0.8, 12))
        return "".join(out)

    def sc_rain(self, t, u):
        p = sine_io(self.prog("rain", t))
        out = [self.shot("rain", t, p), self.overlay("rain.jpg", 0.3, "screen"),
               self.img("rays.png", -260, -240, 1600, 1400,
                        f'opacity="{0.5 + 0.15 * math.sin(t * 2.1):.3f}" style="mix-blend-mode:screen" '
                        f'transform="rotate({2.5 * math.sin(t * 0.7):.2f} 90 -100)"')]
        for width, sel in ((1.1, self.rain[:, 5] < 0.7), (2.2, self.rain[:, 5] >= 0.7)):
            d = []
            for r in self.rain[sel]:
                speed, length = 1900 + 900 * r[1], 60 + 90 * r[2]
                y = (r[3] * 1400 + speed * t) % 1400 - 160
                x = r[0] * (W + 400) - 200 - 0.21 * y
                d.append(f"M{n(x)} {n(y)} l{n(0.21 * length)} {n(-length)}")
            out.append(f'<path d="{"".join(d)}" stroke="#eef2f6" stroke-width="{width}" opacity="{0.3 if width < 2 else 0.45}"/>')
        ul = t - self.t_leave
        for pp in self.leave_petals:  # 花瓣被雨打落，顺着光往上飘
            d = pp[0] * 1.3
            if ul > d:
                pr = (ul - d) / 2.4
                px = 1300 - (300 + 400 * pp[1]) * pr + 30 * math.sin(ul * 3 + pp[2] * 6)
                py = 880 - (700 + 250 * pp[2]) * ease_out(pr)
                out.append(f'<path d="M0 -11 C8 -10 11 5 0 11 C-11 5 -8 -10 0 -11 Z" fill="#eef1f4" stroke="#9aa0a6" stroke-width="0.8" '
                           f'opacity="{0.9 * clamp(1 - pr):.3f}" transform="translate({n(px)} {n(py)}) rotate({n(ul * 200 * (pp[3] - .5) + pp[4] * 360)}) '
                           f'scale({0.9 + 0.8 * pp[4]:.2f} {0.9 + 0.4 * math.sin(ul * 5 + pp[1] * 9):.2f})"/>')
        return "".join(out)

    def sc_ink(self, t, u):
        p = sine_io(self.prog("ink", t))
        r = 60 + 1300 * ease_out(u / 1.3)
        e = ease_out((u - 0.05) / 0.9) * 0.93
        enso = "".join(f'<circle cx="{CX}" cy="{CY}" r="{rr}" fill="none" stroke="#f4f4f4" stroke-width="{w}" pathLength="1" '
                       f'stroke-dasharray="{e * kk:.4f} 2" stroke-linecap="round" opacity="{o}" transform="rotate(-100 {CX} {CY})"/>'
                       for rr, w, kk, o in ((392, 10, 1.0, 0.75), (400, 4, 0.97, 0.5), (384, 2, 0.9, 0.6)))
        return (f'<rect width="{W}" height="{H}" fill="#f2f2f0"/>'
                f'<mask id="spread"><circle cx="{CX}" cy="{CY}" r="{n(r)}" fill="url(#hInk)"/></mask>'
                f'<g mask="url(#spread)">{self.shot("rose", t, p)}</g>' + self.overlay("white.jpg", 0.5, "multiply") + enso)

    def sc_bloom(self, t, u):
        p = ease_out(u / 2.2)
        s = 0.55 + 0.45 * ease_out(u / 0.7)
        out = [self.shot("bouquet", t, p)]
        ray_op = 0.7 * math.exp(-u / 0.9)
        if ray_op > 0.01:
            out.append(f'<g opacity="{ray_op:.3f}" style="mix-blend-mode:screen" transform="rotate({t * 20:.1f} {CX} {CY})">' +
                       "".join(f'<path d="M{CX} {CY} L{n(CX + 1400 * math.cos(math.radians(a - 2)))} {n(CY + 1400 * math.sin(math.radians(a - 2)))} '
                               f'L{n(CX + 1400 * math.cos(math.radians(a + 2)))} {n(CY + 1400 * math.sin(math.radians(a + 2)))} Z" fill="#fff4ee"/>'
                               for a in range(0, 360, 20)) + '</g>')
        out.append(f'<g transform="translate({CX} {CY}) scale({s:.4f})" opacity="{0.55 * (1 - 0.6 * ease_io(u / 2.5)):.3f}" '
                   f'style="mix-blend-mode:screen">' +
                   "".join(f'<g transform="rotate({t * sp:.2f})">{ring}</g>' for ring, sp in self.mandala) + '</g>')
        for q in self.burst:
            a = q[0] * 2 * math.pi
            r = (500 + 500 * q[1]) * 0.8 * (1 - math.exp(-u / 0.8))
            op = clamp(1 - (u - 1.2) / 1.0) * 0.9
            col = ("#f7b7d2", "#ffffff", "#ffe8a8", "#fac8da")[int(q[2] * 4)]
            out.append(f'<ellipse cx="0" cy="0" rx="{n(9 + 7 * q[3])}" ry="{n(4 + 2 * q[3])}" fill="{col}" opacity="{op:.3f}" '
                       f'transform="translate({n(CX + r * math.cos(a))} {n(CY + r * math.sin(a) + 40 * u * u)}) rotate({n(u * 300 * (q[4] - .5) + a * 57)})"/>')
        out.append(self.bokeh(t, "#ffe3ea", 0.9, 16))
        return "".join(out)

    def sc_star(self, t, u, t_smile):
        s0, s1 = self.span("star")
        if t < t_smile:
            p = sine_io((t - s0) / (t_smile - s0))
            out = [self.shot("stars", t, p), self.overlay("sky.jpg", 0.55, "screen")]
            sx, sy, _ = self.to_screen("stars", p, 436, 178)
        else:
            p = sine_io((t - t_smile) / (s1 - t_smile))
            out = [self.shot("smile", t, p), self.overlay("sky.jpg", 0.35, "screen")]
            sx, sy = 1380, 250
        pl = self.pulse(t, 3)
        sm = math.exp(-max(0.0, t - t_smile) / 0.8) if t >= t_smile else 0.0
        flare = 1 + 0.12 * pl + 0.5 * sm
        out += [f'<circle cx="{n(sx)}" cy="{n(sy)}" r="{n(150 * (1 + 0.25 * sm))}" fill="url(#hStar)" style="mix-blend-mode:screen"/>',
                f'<g transform="translate({n(sx)} {n(sy)}) scale({flare:.3f})" fill="#f6fbff">'
                f'<path d="M-230 0 L0 -2.6 L230 0 L0 2.6 Z"/><path d="M0 -160 L2.4 0 L0 160 L-2.4 0 Z"/>'
                f'<path d="M-60 -60 L1.5 -1.5 L60 60 L-1.5 1.5 Z" opacity="0.6"/><path d="M60 -60 L1.5 1.5 L-60 60 L-1.5 -1.5 Z" opacity="0.6"/>'
                f'</g><circle cx="{n(sx)}" cy="{n(sy)}" r="{n(7 + 2 * pl)}" fill="#fff4f8"/>']
        if sm > 0:
            out.append(f'<circle cx="{n(sx)}" cy="{n(sy)}" r="{n(40 + 560 * (1 - sm))}" fill="none" stroke="#ffffff" stroke-width="2" opacity="{0.6 * sm:.3f}"/>')
        for d in self.dust:
            x = d[0] * W
            y = H - 120 - ((d[1] * 800 + 40 * (0.5 + d[2]) * t) % 800)
            a = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * (3 + 4 * d[3]) + d[4] * 9))
            out.append(f'<circle cx="{n(x + 14 * math.sin(t + d[4] * 7))}" cy="{n(y)}" r="{n(1.2 + 2 * d[2])}" fill="#e9f8ff" opacity="{a:.3f}"/>')
        out.append(self.bokeh(t, "#cfeeff", 0.8, 14))
        return "".join(out)

    def sc_line(self, t, u):
        p = sine_io(self.prog("line", t))
        rv = ease_io(u / 1.6)
        art = self.shot("line", t, p, 'style="mix-blend-mode:screen"')
        return (f'<rect width="{W}" height="{H}" fill="#040406"/>'
                f'<mask id="sweep"><linearGradient id="sweepG" gradientUnits="userSpaceOnUse" x1="{n(-400 + 2700 * rv)}" x2="{n(2700 * rv)}">'
                f'<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
                f'<rect width="{W}" height="{H}" fill="url(#sweepG)"/></mask>'
                f'<g mask="url(#sweep)">{art}</g>' +
                self.ribbons(t, "#ffffff", 0.25, 560, 120, seed=5.0) + self.bokeh(t, "#ffffff", 0.6, 12))

    def sc_score(self, t, u, s0):
        p = sine_io(self.prog("score", t))
        out = [self.shot("score", t, p), self.overlay("paper.jpg", 0.9, "multiply"), self.staff(t, 0.0, "#3f444a", 0.9)]
        cy = self.staff_y(180, t, 3)
        out.append(f'<text x="175" y="{n(cy + 34)}" font-family="{E.MUSIC}" font-size="118" fill="#2b2f33" text-anchor="middle">{E.CLEF}</text>')
        notes, _ = self.notes(t, s0)
        out.append(notes)
        return "".join(out)

    def sc_end(self, t, u, s0_score):
        """片尾：第一次露出全彩的完整封面——花开的星球"""
        a = ease_out(u / 1.2)
        s = 700 * (0.94 + 0.06 * a) * (1 + 0.02 * ease_io(u / 8))
        cx, cy = 640, 540
        out = [self.img("cover_blur.jpg", -40 - 10 * u, -20, W + 80, H + 40, f'opacity="{a:.3f}"'),
               f'<rect width="{W}" height="{H}" fill="#0b0f12" opacity="{0.25 * a:.3f}"/>',
               f'<rect x="{n(cx - s / 2 + 14)}" y="{n(cy - s / 2 + 18)}" width="{n(s)}" height="{n(s)}" fill="#000" opacity="{0.35 * a:.3f}" filter="url(#blurS)"/>',
               self.img("cover_full.jpg", cx - s / 2, cy - s / 2, s, s, f'opacity="{a:.3f}"'),
               f'<rect x="{n(cx - s / 2)}" y="{n(cy - s / 2)}" width="{n(s)}" height="{n(s)}" fill="none" stroke="#e9dcc0" stroke-width="1.5" opacity="{0.8 * a:.3f}"/>']
        tx = 1390
        title = "Blooming Planet"
        spans = "".join(f'<tspan fill-opacity="{ease_out((u - 0.9 - 0.05 * j) / 0.6):.3f}">{c}</tspan>' for j, c in enumerate(title))
        rise = 14 * (1 - ease_out((u - 0.9) / 1.2))
        out.append(f'<text x="{tx}" y="{n(500 + rise)}" text-anchor="middle" font-family="{E.LOGO}" font-style="italic" '
                   f'font-weight="600" font-size="96" fill="#f6efe2" letter-spacing="2" filter="url(#sh)">{spans}</text>')
        fl = ease_out((u - 1.6) / 1.0)
        if fl > 0:
            lx = tx - 330
            out.append(f'<path d="M{n(lx + 30)} 540 C{n(lx + 150)} 580 {n(lx + 280)} 522 {n(lx + 360)} 548 S{n(lx + 530)} 580 '
                       f'{n(lx + 610)} 548 S{n(lx + 690)} 520 {n(lx + 682)} 540 S{n(lx + 640)} 560 {n(lx + 650)} 545" fill="none" '
                       f'stroke="#d9bd86" stroke-width="2" pathLength="1" stroke-dasharray="{fl:.4f} 2" stroke-linecap="round"/>')
            if fl > 0.9:
                k = ease_out((u - 2.5) / 0.4) * (1 + 0.15 * self.pulse(t, 3))
                out.append(f'<path d="{E.star4(lx + 700, 522, 15 * k)}" fill="#e9cf98"/>')
        cr = ease_out((u - 2.2) / 0.8)
        cr2 = ease_out((u - 2.8) / 0.8)
        out.append(f'<text x="{tx}" y="610" text-anchor="middle" font-family="{E.SERIF}" font-weight="500" font-size="30" letter-spacing="14" '
                   f'fill="#efe6d4" opacity="{cr:.3f}" filter="url(#sh)">花開く惑星</text>')
        out.append(f'<g text-anchor="middle" font-family="{E.LOGO}" fill="#e6dccb" opacity="{cr2:.3f}" filter="url(#sh)">'
                   f'<text x="{tx}" y="720" font-size="30" font-weight="500">Music — Xyris / 花隈千冬</text>'
                   f'<text x="{tx}" y="758" font-size="24" font-style="italic" font-weight="500">from ARTIFACTS:ASCENSIØN</text>'
                   f'<text x="{tx}" y="800" font-size="19" letter-spacing="6" opacity="0.75">FAN-MADE NARRATIVE PV</text></g>')
        out.append(self.bokeh(t, "#fff0d8", 0.7, 16))
        return "".join(out)

    DEFS = E.EffectPV.DEFS.replace('</defs>', (
        '<filter id="blurS" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="18"/></filter>'
        '<linearGradient id="band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity="0.45"/></linearGradient></defs>'))

    def subtitle(self, t, name):
        """浅色画面上给字幕垫一条从下往上淡出的暗带"""
        sub = super().subtitle(t, name)
        if not sub or name in ("score", "end"):
            return sub
        return f'<rect y="{H - E.BAR - 150}" width="{W}" height="150" fill="url(#band)"/>' + sub


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--prepare":
        prepare(sys.argv[2], sys.argv[3])
        return
    E.EffectPV = KeyArtPV  # 复用 effectpv 的渲染/分段/合成流程
    E.main()


if __name__ == "__main__":
    main()
