#!/usr/bin/env python3
"""《Blooming Planet》叙事 PV：照参考特效谱的镜头语言重做（SVG → Chromium → 1080p60）。

不是把画面做成 ADOFAI，而是借它的叙事手法：遮幅宽银幕、每句歌词一个单色调场景、毛笔大字、
底部小号手写翻译、贯穿画面的丝带与细圆环、落在重拍上的过曝白闪。「我」和「君」是两朵玫瑰。
试片段落 4:17–4:46（最后一段副歌 + 片尾），剧情见 STORY.md。

用法:
  effectpv.py <fx贴图目录> <音频> <歌词.lrc> <feat60.npz> <fonts目录> <输出.mp4>
              [--start 256.9 --end 286] [--still 秒,...] [--workers 4]
（fx 贴图由 fxtex.py 生成；画面里的花都是 rose.py 的矢量玫瑰）
"""
import argparse
import math
import os
import re
import subprocess
import sys
import time
from multiprocessing import Process

import imageio_ffmpeg
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post as P  # noqa: E402
import rose  # noqa: E402

W, H, FPS = 1920, 1080, 60
CX, CY = W / 2, H / 2
BAR = 118  # 遮幅黑边
ME, YOU = "#8ff0e6", "#f7b7d2"
BRUSH = "'Yuji Syuku', serif"
HAND = "'Long Cang', cursive"
LOGO = "'Cormorant Garamond', 'Noto Serif JP', serif"
SERIF = "'Noto Serif JP', serif"
MUSIC = "'Noto Music'"
CLEF = "\U0001D11E"
FONTS = [("noto-serif-jp", ["500", "700"]), ("yuji-syuku", ["400"]), ("long-cang", ["400"]),
         ("cormorant-garamond", ["500", "500-italic", "600-italic"]), ("noto-music", ["400"])]
PROBES = [(SERIF, 500, "normal"), (SERIF, 700, "normal"), (BRUSH, 400, "normal"), (HAND, 400, "normal"),
          (LOGO, 500, "normal"), (LOGO, 500, "italic"), (LOGO, 600, "italic"), (MUSIC, 400, "normal")]

# 每个场景的调色：歌词墨色 / 描边 / 光晕滤镜 / 翻译字色 / 线条色
STYLE = {
    "sepia": dict(fill="#3a2716", sub="#3a2716", line="#5a4128", filt=None),
    "rain": dict(fill="#f4f6f8", sub="#f0f3f6", line="#e6ebf0", filt="sh"),
    "ink": dict(fill="#0b0b0b", sub="#111111", line="#111111", filt=None),
    "bloom": dict(fill="#7a3044", sub="#6a2a3a", line="#b86e80", filt="glw"),
    "star": dict(fill="rgba(232,247,255,0.18)", stroke="#eaf7ff", sw=2.2, sub="#e6f4ff", line="#bfe6ff", filt="gl"),
    "line": dict(fill="#ffffff", sub="#e8e8e8", line="#ffffff", filt="gl"),
    "score": dict(fill="#24272b", sub="#34383d", line="#4a4f55", filt=None),
    "end": dict(fill="#2d4d55", sub="#2d4d55", line="#b08d57", filt=None),
}


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


def lerp(a, b, t):
    return a + (b - a) * t


def n(x):
    return f"{x:.1f}"


def parse_lrc(path):
    out = []
    for raw in open(path, encoding="utf-8"):
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*?)\s*(?:[（(]翻译[：:](.*)[)）])?\s*$", raw.strip())
        if m and m.group(3):
            out.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip(), (m.group(4) or "").strip()))
    return sorted(out)


def star4(cx, cy, r, w=0.22):
    k = r * w
    return (f"M{n(cx)} {n(cy - r)} L{n(cx + k)} {n(cy - k)} L{n(cx + r)} {n(cy)} L{n(cx + k)} {n(cy + k)} "
            f"L{n(cx)} {n(cy + r)} L{n(cx - k)} {n(cy + k)} L{n(cx - r)} {n(cy)} L{n(cx - k)} {n(cy - k)} Z")


def leaf_paths(x, y, ang, L, Wd):
    """线稿叶子：轮廓 + 主脉 + 侧脉（已按位置/角度/大小变换好的路径列表）"""
    c, s = math.cos(ang), math.sin(ang)

    def p(u, v):
        return f"{n(x + u * c - v * s)} {n(y + u * s + v * c)}"
    out = [f"M{p(0, 0)} C{p(L * .3, -Wd)} {p(L * .75, -Wd * .8)} {p(L, 0)} C{p(L * .75, Wd * .8)} {p(L * .3, Wd)} {p(0, 0)}",
           f"M{p(0, 0)} L{p(L * .95, 0)}"]
    for v in (0.28, 0.48, 0.68):
        out.append(f"M{p(L * v, 0)} L{p(L * (v + .16), -Wd * .6)}")
        out.append(f"M{p(L * v, 0)} L{p(L * (v + .16), Wd * .6)}")
    return out


def bezier(P, s):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = P
    m = 1 - s
    x = m ** 3 * x0 + 3 * m * m * s * x1 + 3 * m * s * s * x2 + s ** 3 * x3
    y = m ** 3 * y0 + 3 * m * m * s * y1 + 3 * m * s * s * y2 + s ** 3 * y3
    dx = 3 * m * m * (x1 - x0) + 6 * m * s * (x2 - x1) + 3 * s * s * (x3 - x2)
    dy = 3 * m * m * (y1 - y0) + 6 * m * s * (y2 - y1) + 3 * s * s * (y3 - y2)
    return x, y, math.atan2(dy, dx)


class EffectPV:
    def __init__(self, fx, lrc, features):
        self.fx = os.path.abspath(fx)
        f = np.load(features)
        self.kick = f["kick"]
        self.phase = float(f["beat_phase"]) / FPS
        self.period = float(f["beat_period"]) / FPS
        self.t_in = self.t_out = None
        lines = parse_lrc(lrc)[-4:]  # 最后一段：泣き虫の雨が降る … 永遠の歌
        self.subs = [(t, zh) for t, _, zh in lines]
        L1, L2, L3, L4 = (t for t, _, _ in lines)
        self.B0 = math.floor(self.beat(L1)) - 4
        q = self.q
        self.END = self.at(math.ceil(self.beat(L4)) + 16)
        s_rain, s_bloom, s_score = q(L1, 6), q(L2, 8), q(L4, 8)
        self.scenes = [(-1e9, "sepia"), (s_rain, "rain"), (L2, "ink"), (s_bloom, "bloom"), (L3, "star"),
                       (L4, "line"), (s_score, "score"), (self.END, "end")]
        # (出现时刻, 文字, x, y, 字号, 竖排)
        self.chunks = [(L1, "泣き虫の", 800, 420, 150, False),
                       (s_rain, "雨が", 560, 250, 150, True), (q(L1, 10), "降る", 930, 360, 150, True),
                       (L2, "心の", 430, 300, 132, False), (q(L2, 4), "花で", 1480, 720, 132, False),
                       (s_bloom, "満開の", 500, 320, 132, False), (q(L2, 12), "瞬間", 1410, 770, 170, False),
                       (L3, "遠い星が", 450, 250, 112, True), (q(L3, 8), "微笑む", 1330, 560, 118, False),
                       (L4, "寄り添う", 520, 300, 124, False), (q(L4, 5), "愛", 1440, 770, 190, False),
                       (s_score, "永遠の", 640, 320, 128, False), (q(L4, 12), "歌", 1330, 330, 200, False)]
        # 雨里「君」那朵花开始散落的那一拍
        b = math.ceil(self.beat(s_rain)) + 3
        self.t_leave = self.at(b)
        rng = np.random.default_rng(3)
        self.rain = rng.random((170, 6))
        self.petals = rng.random((28, 6))
        self.dust = rng.random((46, 5))
        self.burst = rng.random((52, 5))
        self.leave_petals = rng.random((16, 5))
        self.vines = [((-60, 990), (300, 720), (430, 640), (770, 575)), ((1980, 110), (1650, 330), (1500, 430), (1150, 515)),
                      ((-40, 150), (180, 170), (380, 260), (560, 360)), ((1960, 960), (1760, 880), (1560, 850), (1380, 760))]
        self.leaves = []
        for vi, P in enumerate(self.vines):
            for k, s in enumerate(np.arange(0.12, 0.97, 0.11)):
                x, y, a = bezier(P, s)
                side = 1 if k % 2 else -1
                L = 58 + 34 * rng.random()
                self.leaves.append((vi, s, leaf_paths(x, y, a + side * (0.75 + 0.3 * rng.random()), L, L * 0.34)))
        self.mandala = self._mandala()

    # ---------- 节拍 ----------
    def beat(self, t):
        return (t - self.phase) / self.period

    def at(self, b):
        return self.phase + b * self.period

    def q(self, t, beats):
        return self.at(round(self.beat(t) + beats))

    def pulse(self, t, k=5.0):
        b = self.beat(t)
        return math.exp(-(b - math.floor(b)) * k)

    def scene(self, t):
        for k in range(len(self.scenes) - 1, -1, -1):
            if t >= self.scenes[k][0]:
                end = self.scenes[k + 1][0] if k + 1 < len(self.scenes) else 1e9
                return self.scenes[k][1], self.scenes[k][0], end
        raise ValueError(t)

    # ---------- 通用元素 ----------
    def img(self, name, x, y, w, h, extra=""):
        return (f'<image href="file://{self.fx}/{name}" x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" '
                f'preserveAspectRatio="none" {extra}/>')

    def plate(self, name, u, drift=0.05):
        s = 1 + drift * ease_io(u / 5)
        return self.img(name, -96, -54, 2112, 1188, f'transform="translate(960 540) scale({s:.4f}) translate(-960 -540)"')

    def fg(self, name, u, y, speed=26):
        return self.img(name, -96 - speed * u, y, 2112, 560)

    def rings(self, t, cx, cy, r, color, op):
        p = self.pulse(t)
        return (f'<g fill="none" stroke="{color}" opacity="{op:.3f}">'
                f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r + 10 * p)}" stroke-width="1.5"/>'
                f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r + 24 + 4 * p)}" stroke-width="0.9" stroke-dasharray="2 12" '
                f'transform="rotate({t * 12:.2f} {n(cx)} {n(cy)})"/>'
                f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r - 16)}" stroke-width="0.6" opacity="0.6"/></g>')

    def ribbons(self, t, color, op, y0, amp, count=2, seed=0.0):
        out = []
        xs = np.linspace(-40, W + 40, 49)
        for k in range(count):
            ph = t * (0.55 + 0.22 * k) + seed + k * 1.7
            yc = y0 + (k - (count - 1) / 2) * 80 + amp * np.sin(xs / W * 2 * math.pi * 0.9 + ph) \
                + 0.35 * amp * np.sin(xs / W * 2 * math.pi * 2.3 - 1.3 * ph)
            th = 8 + 22 * (0.5 + 0.5 * np.sin(xs / W * 2 * math.pi * 1.4 + 0.7 * ph + k))
            top = " L".join(f"{n(x)} {n(y)}" for x, y in zip(xs, yc - th / 2))
            bot = " L".join(f"{n(x)} {n(y)}" for x, y in zip(xs[::-1], (yc + th / 2)[::-1]))
            out.append(f'<path d="M{top} L{bot} Z" fill="{color}" opacity="{op * 0.22:.3f}"/>'
                       f'<path d="M{top}" fill="none" stroke="{color}" stroke-width="1.2" opacity="{op:.3f}"/>'
                       f'<path d="M{bot}" fill="none" stroke="{color}" stroke-width="0.8" opacity="{op * 0.7:.3f}"/>')
        return "".join(out)

    def stem_rose(self, uid, t, bx, hx, hy, R, style, g=1.0, lean=0.0, squash=0.62, opacity=1.0, seed=0, reveal=None, phase=0.0,
                  stem=True):
        """一枝玫瑰：从画面下方长上来的茎 + 两片小叶 + 花头（花头随风轻摆，lean 为弯腰的角度）"""
        stem_col = {"sepia": "#3e2c1b", "gray": "#2f3338", "line": "#ffffff"}[style]
        sway = 7 * math.sin(t * 1.3 + phase)
        hx2 = hx + sway + 260 * math.sin(lean)
        hy2 = hy + 260 * (1 - math.cos(lean))
        by = H + 30
        mx, my = lerp(bx, hx2, 0.5) + 30 * math.sin(lean + 0.3), lerp(by, hy2, 0.5)
        k = ease_out(reveal / 0.6) if reveal is not None else 1.0
        dash = f' pathLength="1" stroke-dasharray="{k:.4f} 2"' if reveal is not None else ""
        out = [f'<g opacity="{opacity:.3f}">']
        if not stem:
            out.append(rose.rose_svg(uid, hx2, hy2, R, style, g, lean * 0.6 + 0.2 * math.sin(t * 0.5 + phase), squash, seed,
                                     reveal=reveal) + '</g>')
            return "".join(out)
        out.append(f'<path d="M{n(bx)} {n(by)} Q{n(mx)} {n(my)} {n(hx2)} {n(hy2)}" fill="none" stroke="{stem_col}" '
                   f'stroke-width="{max(2.0, R / 18):.1f}" stroke-linecap="round"{dash}/>')
        for j, (v, side) in enumerate(((0.45, 1), (0.65, -1))):
            px, py = lerp(lerp(bx, mx, v), lerp(mx, hx2, v), v), lerp(lerp(by, my, v), lerp(my, hy2, v), v)
            body, veins = rose.leaf(px, py, -math.pi / 2 + side * 0.9 + lean, R * 0.75 * k, R * 0.27 * k, 1.0)
            fill = "#050507" if style == "line" else stem_col
            out.append(f'<path d="{body}" fill="{fill}" stroke="{stem_col}" stroke-width="1.4"/>')
        out.append(rose.rose_svg(uid, hx2, hy2, R, style, g, lean * 0.6 + 0.2 * math.sin(t * 0.5 + phase), squash, seed,
                                 leaves=False, reveal=reveal))
        out.append('</g>')
        return "".join(out)

    # ---------- 场景 ----------
    def sc_sepia(self, t, u):
        out = [self.plate("sepia.jpg", u), self.ribbons(t, "#5a4128", 0.32, 540, 90),
               self.rings(t, CX, CY - 40, 300, "#5a4128", 0.32),
               self.stem_rose("s1", t, 1400, 1330, 650, 86, "sepia", lean=0.10, seed=21),
               self.stem_rose("s2", t, 1560, 1545, 615, 94, "sepia", lean=-0.12, seed=22, phase=1.3)]
        for p in self.petals:  # 枯叶般落下的花瓣
            x = (p[0] * 2200 - 140 - 60 * t) % 2200 - 140
            y = (p[1] * 1300 + (60 + 50 * p[2]) * t) % 1300 - 110
            a = t * (40 + 80 * p[3]) + p[4] * 360
            out.append(f'<ellipse cx="0" cy="0" rx="{n(7 + 6 * p[5])}" ry="{n(3 + 2 * p[5])}" fill="#3e2c1b" opacity="0.55" '
                       f'transform="translate({n(x + 30 * math.sin(t + p[4] * 6))} {n(y)}) rotate({a:.1f})"/>')
        out.append(self.fg("fg_sepia.png", u, H - 430))
        return "".join(out)

    def sc_rain(self, t, u):
        out = [self.plate("rain.jpg", u),
               self.img("rays.png", -260, -240, 1600, 1400,
                        f'opacity="{0.55 + 0.15 * math.sin(t * 2.1):.3f}" transform="rotate({2.5 * math.sin(t * 0.7):.2f} 90 -100)"'),
               self.ribbons(t, "#e6ebf0", 0.28, 560, 80, seed=2.0), self.rings(t, CX, CY - 40, 300, "#e6ebf0", 0.35)]
        # 「君」那朵：从这一拍起花瓣被雨打散、顺着光束飘上天，花头慢慢谢掉；「我」那朵在雨里低下头
        ul = t - self.t_leave
        wilt = ease_io(ul / 2.2) if ul > 0 else 0.0
        out.append(self.stem_rose("r1", t, 1400, 1330, 650, 86, "gray", lean=0.10 + 0.25 * ease_io(u / 2.5), seed=21))
        out.append(self.stem_rose("r2", t, 1560, 1545, 615, 94, "gray", g=1 - 0.7 * wilt, lean=-0.12, seed=22, phase=1.3,
                                  opacity=1 - 0.75 * wilt))
        for p in self.leave_petals:
            d = p[0] * 1.3
            if ul > d:
                pr = (ul - d) / 2.4
                px = 1545 - (160 + 260 * p[1]) * pr + 30 * math.sin(ul * 3 + p[2] * 6)
                py = 615 - (650 + 250 * p[2]) * ease_out(pr) + 20 * pr
                out.append(f'<path d="M0 -9 C7 -8 9 4 0 9 C-9 4 -7 -8 0 -9 Z" fill="#f3d9e1" stroke="#9aa0a6" stroke-width="0.8" '
                           f'opacity="{0.95 * clamp(1 - pr):.3f}" transform="translate({n(px)} {n(py)}) rotate({n(ul * 200 * (p[3] - .5) + p[4] * 360)}) '
                           f'scale({0.9 + 0.8 * p[4]:.2f} {0.9 + 0.4 * math.sin(ul * 5 + p[1] * 9):.2f})"/>')
        for width, sel in ((1.1, self.rain[:, 5] < 0.7), (2.0, self.rain[:, 5] >= 0.7)):
            d = []
            for r in self.rain[sel]:
                speed, length = 1900 + 900 * r[1], 50 + 80 * r[2]
                y = (r[3] * 1400 + speed * t) % 1400 - 160
                x = r[0] * (W + 400) - 200 - 0.21 * y
                d.append(f"M{n(x)} {n(y)} l{n(0.21 * length)} {n(-length)}")
            out.append(f'<path d="{"".join(d)}" stroke="#eef2f6" stroke-width="{width}" opacity="{0.35 if width < 2 else 0.5}"/>')
        out.append(self.fg("fg_rain.png", u, H - 430))
        return "".join(out)

    def flower(self, t, u, colored):
        if os.path.exists(os.path.join(self.fx, "bouquet_ink.png")):
            # 主体用封面花束：墨色从中心晕开 → 满开时换成粉米暖调
            w, h = 1148, 784
            s = 1 + 0.05 * ease_io(u / 3) + 0.012 * self.pulse(t)
            tr = f'transform="translate({CX} {CY}) scale({s:.4f}) translate({-CX} {-CY})"'
            if colored:
                return (f'<circle cx="{CX}" cy="{CY}" r="520" fill="url(#hWarm)"/>' +
                        self.img("bouquet_warm.png", CX - w / 2, CY - h / 2, w, h, tr))
            r = 80 + 900 * ease_out(u / 1.6)
            return (f'<mask id="spread"><circle cx="{CX}" cy="{CY}" r="{n(r)}" fill="url(#hInk)"/></mask>'
                    f'<g mask="url(#spread)">{self.img("bouquet_ink.png", CX - w / 2, CY - h / 2, w, h, tr)}</g>')
        g = 1.0 if colored else 0.1 + 0.9 * ease_out(u / 1.9)
        R = 300 * (1 + 0.015 * self.pulse(t))
        body = rose.rose_svg("heart", CX, CY, R, "bloom" if colored else "ink", g, t * 0.07, 1.0, 11)
        return (f'<circle cx="{CX}" cy="{CY}" r="440" fill="url(#hWarm)"/>' if colored else "") + body

    def sc_ink(self, t, u):
        p = ease_out((u - 0.05) / 0.9) * 0.93
        enso = "".join(f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="none" stroke="#0b0b0b" stroke-width="{w}" pathLength="1" '
                       f'stroke-dasharray="{p * k:.4f} 2" stroke-linecap="round" opacity="{o}" transform="rotate(-100 {CX} {CY})"/>'
                       for r, w, k, o in ((392, 16, 1.0, 0.92), (400, 6, 0.97, 0.7), (384, 3, 0.9, 0.8), (408, 2, 0.8, 0.5)))
        dots = "".join(f'<circle cx="{n(CX + 420 * math.cos(a))}" cy="{n(CY + 420 * math.sin(a))}" r="{r}" fill="#0b0b0b"/>'
                       for a, r in ((0.35, 5), (0.42, 3), (0.5, 2), (2.9, 4), (3.0, 2))) if p > 0.8 else ""
        return "".join([self.plate("white.jpg", u), self.ribbons(t, "#111111", 0.4, 560, 110, seed=4.0),
                        f'<g transform="translate({CX} {CY - 24}) scale(0.88) translate({-CX} {-CY})">{enso}{dots}'
                        f'{self.flower(t, u, False)}</g>'])

    def _mandala(self):
        c = 'fill="#f8d9dd" fill-opacity="0.5" stroke="#b86e80" stroke-width="1.5"'
        r1 = "".join(f'<ellipse cx="0" cy="-150" rx="22" ry="58" transform="rotate({a})" {c}/>' for a in range(0, 360, 30))
        r2 = "".join(f'<path d="M0 -205 Q28 -262 0 -318 Q-28 -262 0 -205 Z" transform="rotate({a})" {c}/>' for a in range(0, 360, 15))
        r3 = "".join(f'<circle cx="0" cy="-352" r="5" transform="rotate({a})" fill="#b86e80"/>' for a in range(0, 360, 10))
        ticks = "".join(f"M0 -384 L0 -400 " for _ in range(1))
        r4 = (f'<circle r="392" fill="none" stroke="#b86e80" stroke-width="1.2"/>' +
              "".join(f'<path d="{ticks}" transform="rotate({a})" stroke="#b86e80" stroke-width="1.2"/>' for a in range(0, 360, 5)))
        r5 = "".join(f'<path d="M0 -410 C95 -445 75 -525 0 -565 C-75 -525 -95 -445 0 -410 Z" transform="rotate({a})" '
                     f'fill="none" stroke="#c98795" stroke-width="1.4"/>' for a in range(0, 360, 45))
        return [(r1, 10), (r2, -6), (r3, 4), (r4, -3), (r5, 2)]

    def sc_bloom(self, t, u):
        s = 0.55 + 0.45 * ease_out(u / 0.7)
        out = [self.plate("warm.jpg", u), self.ribbons(t, "#b86e80", 0.3, 560, 90, seed=1.0)]
        ray_op = 0.8 * math.exp(-u / 0.9)
        if ray_op > 0.01:
            out.append(f'<g opacity="{ray_op:.3f}" transform="rotate({t * 20:.1f} {CX} {CY})">' +
                       "".join(f'<path d="M{CX} {CY} L{n(CX + 1400 * math.cos(math.radians(a - 2)))} {n(CY + 1400 * math.sin(math.radians(a - 2)))} '
                               f'L{n(CX + 1400 * math.cos(math.radians(a + 2)))} {n(CY + 1400 * math.sin(math.radians(a + 2)))} Z" fill="#fffaf5"/>'
                               for a in range(0, 360, 20)) + '</g>')
        out.append(f'<g transform="translate({CX} {CY}) scale({s:.4f})" opacity="0.85">' +
                   "".join(f'<g transform="rotate({t * sp:.2f})">{ring}</g>' for ring, sp in self.mandala) + '</g>')
        out.append(self.flower(t, u, True))
        for p in self.burst:  # 满开时炸开的花瓣
            a = p[0] * 2 * math.pi
            r = (500 + 500 * p[1]) * 0.8 * (1 - math.exp(-u / 0.8))
            op = clamp(1 - (u - 1.2) / 1.0) * 0.9
            col = ("#f7b7d2", "#ffffff", "#ffe8a8", "#fac8da")[int(p[2] * 4)]
            out.append(f'<ellipse cx="0" cy="0" rx="{n(9 + 7 * p[3])}" ry="{n(4 + 2 * p[3])}" fill="{col}" opacity="{op:.3f}" '
                       f'transform="translate({n(CX + r * math.cos(a))} {n(CY + r * math.sin(a) + 40 * u * u)}) rotate({n(u * 300 * (p[4] - .5) + a * 57)})"/>')
        return "".join(out)

    def sc_star(self, t, u, t_smile):
        sx, sy = 1330, 280
        p = self.pulse(t, 3)
        sm = math.exp(-max(0.0, t - t_smile) / 0.8) if t >= t_smile else 0.0
        flare = 1 + 0.12 * p + 0.5 * sm
        out = [self.plate("sky.jpg", u, 0.03), self.ribbons(t, "#bfe6ff", 0.2, 470, 70, seed=3.0),
               f'<circle cx="{sx}" cy="{sy}" r="{n(150 * (1 + 0.25 * sm))}" fill="url(#hStar)"/>',
               f'<g transform="translate({sx} {sy}) scale({flare:.3f})" fill="#f6fbff">'
               f'<path d="M-210 0 L0 -2.6 L210 0 L0 2.6 Z"/><path d="M0 -150 L2.4 0 L0 150 L-2.4 0 Z"/>'
               f'<path d="M-60 -60 L1.5 -1.5 L60 60 L-1.5 1.5 Z" opacity="0.6"/><path d="M60 -60 L1.5 1.5 L-60 60 L-1.5 -1.5 Z" opacity="0.6"/>'
               f'</g><circle cx="{sx}" cy="{sy}" r="{n(7 + 2 * p)}" fill="#fff4f8"/><circle cx="{sx}" cy="{sy}" r="16" fill="{YOU}" opacity="0.35"/>',
               self.rings(t, sx, sy, 118, "#dff3ff", 0.35)]
        if sm > 0:
            out.append(f'<circle cx="{sx}" cy="{sy}" r="{n(40 + 520 * (1 - sm))}" fill="none" stroke="#ffffff" stroke-width="2" opacity="{0.6 * sm:.3f}"/>')
        for d in self.dust:  # 从发光的草丛里升起的光点
            x = d[0] * W
            y = H - 180 - ((d[1] * 700 + 40 * (0.5 + d[2]) * t) % 700)
            a = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * (3 + 4 * d[3]) + d[4] * 9))
            out.append(f'<circle cx="{n(x + 14 * math.sin(t + d[4] * 7))}" cy="{n(y)}" r="{n(1.2 + 2 * d[2])}" fill="#e9f8ff" opacity="{a:.3f}"/>')
        out.append(self.fg("fg_ice.png", u, H - 440, 18))
        return "".join(out)

    def sc_line(self, t, u):
        out = [f'<rect width="{W}" height="{H}" fill="#050507"/>', self.ribbons(t, "#ffffff", 0.3, 560, 120, seed=5.0),
               '<g fill="none" stroke="#ffffff" stroke-width="1.6" stroke-linecap="round" filter="url(#gls)">']
        for P in self.vines:
            v = ease_out(u / 1.4)
            out.append(f'<path d="M{P[0][0]} {P[0][1]} C{P[1][0]} {P[1][1]} {P[2][0]} {P[2][1]} {P[3][0]} {P[3][1]}" '
                       f'pathLength="1" stroke-dasharray="{v:.4f} 2" stroke-width="2"/>')
        for _, s, paths in self.leaves:
            k = ease_out((u - s * 1.4) / 0.45)
            if k > 0:
                out.extend(f'<path d="{d}" pathLength="1" stroke-dasharray="{k:.4f} 2"/>' for d in paths)
        out.append('</g>')
        # 寄り添う：两朵线稿玫瑰一笔笔画出来，靠在一起
        out.append(self.stem_rose("l1", t, 0, 860, 575, 175, "line", lean=0.10, squash=0.85, seed=31, reveal=u / 1.8, stem=False))
        out.append(self.stem_rose("l2", t, 0, 1085, 525, 150, "line", lean=-0.10, squash=0.85, seed=32, reveal=(u - 0.35) / 1.8,
                                  phase=1.1, stem=False))
        return "".join(out)

    def staff_y(self, x, t, i, calm=0.0):
        amp = 1 - 0.8 * calm
        return (lerp(610, 560, calm) + (i - 2) * 17 +
                amp * (55 * math.sin(2 * math.pi * x / 1700 - 0.9 * t) + 16 * math.sin(2 * math.pi * x / 600 + 1.4 * t)))

    def staff(self, t, calm, color, op):
        xs = np.linspace(-40, W + 40, 60)
        return "".join(f'<path d="M{" L".join(f"{n(x)} {n(self.staff_y(x, t, i, calm))}" for x in xs)}" fill="none" '
                       f'stroke="{color}" stroke-width="1.6" opacity="{op:.3f}"/>' for i in range(5))

    NOTES = [-2, 0, 2, 1, 3, 2, 4, 3, 5, 4, 2, 0]

    def notes(self, t, s0, calm=0.0, op=1.0):
        out = []
        b = self.beat(t) - self.beat(s0)
        for k, p in enumerate(self.NOTES):
            if b < k:
                break
            a = ease_out((b - k) / 0.5)
            x = 330 + k * 118
            y = self.staff_y(x, t, 2, calm) - p * 8.5
            sc = 1.6 - 0.6 * a
            flag = f'<path d="M{n(x + 10)} {n(y - 62)} q10 16 18 30" fill="none" stroke="#24272b" stroke-width="2.2"/>' if k % 3 == 1 else ""
            out.append(f'<g opacity="{a * op:.3f}" transform="translate({n(x)} {n(y)}) scale({sc:.3f}) translate({n(-x)} {n(-y)})">'
                       f'<ellipse cx="{n(x)}" cy="{n(y)}" rx="11" ry="8" transform="rotate(-22 {n(x)} {n(y)})" fill="#24272b"/>'
                       f'<line x1="{n(x + 10)}" y1="{n(y)}" x2="{n(x + 10)}" y2="{n(y - 62)}" stroke="#24272b" stroke-width="2"/>{flag}</g>')
        return "".join(out), b

    def sc_score(self, t, u, s0):
        wc = [("wc_0.png", -150, 560, 660), ("wc_1.png", 1400, -110, 600), ("wc_2.png", 1530, 640, 500), ("wc_3.png", 60, -40, 420)]
        out = [self.plate("paper.jpg", u)]
        for k, (name, x, y, s) in enumerate(wc):
            a = ease_out((u - 0.1 * k) / 0.9)
            g = s * (0.94 + 0.06 * a)
            out.append(self.img(name, x + (s - g) / 2 + 8 * u, y + (s - g) / 2, g, g, f'opacity="{0.95 * a:.3f}"'))
        out.append(self.staff(t, 0.0, "#4a4f55", 0.85))
        cy = self.staff_y(180, t, 3)
        out.append(f'<text x="175" y="{n(cy + 34)}" font-family="{MUSIC}" font-size="118" fill="#2b2f33" text-anchor="middle">{CLEF}</text>')
        notes, _ = self.notes(t, s0)
        out.append(notes)
        return "".join(out)

    def emblem(self, cx, cy, u):
        """封面上的六芒星徽章：外环描出 → 星转入"""
        ring = ease_out(u / 0.9)
        st = ease_out((u - 0.25) / 1.0)
        out = [f'<g transform="translate({cx} {cy})">',
               f'<circle r="126" fill="none" stroke="#b08d57" stroke-width="2.2" pathLength="1" stroke-dasharray="{ring:.4f} 2" transform="rotate(-90)"/>',
               f'<circle r="112" fill="none" stroke="#b08d57" stroke-width="1" pathLength="1" stroke-dasharray="{ring:.4f} 2" transform="rotate(90)"/>']
        if ring > 0.5:
            out.append(f'<g opacity="{clamp((ring - 0.5) * 2):.3f}">' +
                       "".join(f'<line x1="0" y1="-112" x2="0" y2="-{104 if a % 30 else 96}" stroke="#b08d57" stroke-width="1.2" transform="rotate({a})"/>'
                               for a in range(0, 360, 10)) +
                       "".join(f'<circle cx="0" cy="-138" r="3" fill="#b08d57" transform="rotate({a + 15})"/>' for a in range(0, 360, 30)) + '</g>')
        if st > 0:
            out.append(f'<g transform="rotate({-70 * (1 - st):.2f}) scale({0.4 + 0.6 * st:.3f})" opacity="{st:.3f}">')
            for a in range(0, 360, 60):
                out.append(f'<g transform="rotate({a})"><path d="M0 0 L-17 -34 L0 -104 Z" fill="#e6f1ef" stroke="#b08d57" stroke-width="1.4"/>'
                           f'<path d="M0 0 L17 -34 L0 -104 Z" fill="#6fa4a0" stroke="#b08d57" stroke-width="1.4"/></g>')
                out.append(f'<g transform="rotate({a + 30})"><path d="M0 -20 L-8 -38 L0 -58 L8 -38 Z" fill="#d9c08f" stroke="#b08d57" stroke-width="1"/></g>')
            out.append('<circle r="12" fill="#fdfaf2" stroke="#b08d57" stroke-width="1.6"/>')
            out.append(f'<circle r="5.5" fill="#8fd3bd" stroke="#b08d57" stroke-width="1"/></g>')
        out.append('</g>')
        return "".join(out)

    def sc_end(self, t, u, s0_score):
        calm = ease_io(u / 1.6)
        out = [self.plate("paper.jpg", u + 3)]
        for k, (name, x, y, s) in enumerate([("wc_0.png", -150, 560, 660), ("wc_1.png", 1400, -110, 600)]):
            out.append(self.img(name, x + 8 * (u + 3), y, s, s, f'opacity="{0.95 - 0.45 * calm:.3f}"'))
        out.append(self.staff(t, calm, "#b08d57", 0.85 - 0.4 * calm))
        notes, _ = self.notes(t, s0_score, calm, 1 - calm)
        out.append(notes)
        out.append(self.emblem(CX, 400, u - 0.2))
        title = "Blooming Planet"
        tot = 820
        lx = CX - 400
        rise = 16 * (1 - ease_out((u - 1.2) / 1.2))
        spans = "".join(f'<tspan fill-opacity="{ease_out((u - 1.2 - 0.05 * j) / 0.6):.3f}">{c}</tspan>' for j, c in enumerate(title))
        out.append(f'<text x="{CX}" y="{n(655 + rise)}" text-anchor="middle" font-family="{LOGO}" font-style="italic" '
                   f'font-weight="600" font-size="118" fill="#2d4d55" letter-spacing="2">{spans}</text>')
        fl = ease_out((u - 1.9) / 1.0)
        if fl > 0:
            out.append(f'<path d="M{n(lx + 60)} 690 C{n(lx + 180)} 735 {n(lx + 330)} 672 {n(lx + 420)} 700 S{n(lx + 610)} 736 '
                       f'{n(lx + 700)} 700 S{n(lx + 800)} 668 {n(lx + 790)} 690 S{n(lx + 740)} 712 {n(lx + 752)} 694" fill="none" '
                       f'stroke="#b08d57" stroke-width="2" pathLength="1" stroke-dasharray="{fl:.4f} 2" stroke-linecap="round"/>')
        if fl > 0.9:
            k = ease_out((u - 2.8) / 0.4) * (1 + 0.15 * self.pulse(t, 3))
            out.append(f'<path d="{star4(lx + 820, 672, 16 * k)}" fill="#b08d57"/>')
        orn = ease_out((u - 2.2) / 0.8)
        if orn > 0:
            leaves = []
            for side in (-1, 1):
                bx = CX + side * (tot / 2 + 70)
                for ang, L in ((-0.5, 46), (0.45, 38), (0.0, 30)):
                    a = (math.pi if side < 0 else 0) + side * ang
                    leaves.extend(leaf_paths(bx, 625, a, L * orn, L * 0.34))
            out.append('<g fill="none" stroke="#b08d57" stroke-width="1.4">' + "".join(f'<path d="{d}"/>' for d in leaves) + '</g>')
        cr = ease_out((u - 2.6) / 0.8)
        cr2 = ease_out((u - 3.2) / 0.8)
        out.append(f'<text x="{CX}" y="748" text-anchor="middle" font-family="{SERIF}" font-weight="500" font-size="30" letter-spacing="14" '
                   f'fill="#5b6b6e" opacity="{cr:.3f}">花開く惑星</text>')
        out.append(f'<g text-anchor="middle" font-family="{LOGO}" fill="#4a5a5e" opacity="{cr2:.3f}">'
                   f'<text x="{CX}" y="828" font-size="30" font-weight="500">Music — Xyris / 花隈千冬</text>'
                   f'<text x="{CX}" y="866" font-size="24" font-style="italic" font-weight="500">from ARTIFACTS:ASCENSIØN</text>'
                   f'<text x="{CX}" y="904" font-size="19" letter-spacing="6" opacity="0.75">FAN-MADE NARRATIVE PV</text></g>')
        for p in self.petals[:14]:  # 缓缓飘落的灰色花瓣
            x = (p[0] * 2200 - 40 * t) % 2200 - 140
            y = (p[1] * 1300 + (40 + 30 * p[2]) * t) % 1300 - 110
            out.append(f'<ellipse cx="0" cy="0" rx="{n(8 + 6 * p[5])}" ry="{n(3.5 + 2 * p[5])}" fill="#7d858c" opacity="0.35" '
                       f'transform="translate({n(x + 30 * math.sin(t + p[4] * 6))} {n(y)}) rotate({t * (40 + 80 * p[3]) + p[4] * 360:.1f})"/>')
        return "".join(out)

    # ---------- 文字 ----------
    def lyrics(self, t, name, s0, s1):
        st = STYLE[name]
        out = []
        for t0, text, x, y, size, vert in self.chunks:
            if not (s0 <= t0 < s1) or t < t0 - 0.01:
                continue
            filt = f' filter="url(#{st["filt"]})"' if st["filt"] else ""
            stroke = f' stroke="{st["stroke"]}" stroke-width="{st["sw"]}"' if "stroke" in st else ""
            for j, ch in enumerate(text):
                tj = t0 + j * 0.11
                a = ease_out((t - tj) / 0.28)
                if a <= 0:
                    continue
                if vert:
                    cx, cy = x, y + j * size * 1.04
                else:
                    cx, cy = x + (j - (len(text) - 1) / 2) * size * 1.02, y
                s = 1.3 - 0.3 * a
                dy = 22 * (1 - a)
                echo = clamp((t - tj) / 0.5)
                tr = f'translate({n(cx)} {n(cy + dy)}) scale({s:.3f}) translate({n(-cx)} {n(-cy)})'
                if echo < 1:
                    es = 1 + 0.6 * echo
                    out.append(f'<text x="{n(cx)}" y="{n(cy + size * 0.36)}" text-anchor="middle" font-family="{BRUSH}" '
                               f'font-size="{size}" fill="none" stroke="{st["line"]}" stroke-width="1.5" opacity="{0.5 * (1 - echo):.3f}" '
                               f'transform="translate({n(cx)} {n(cy)}) scale({es:.3f}) translate({n(-cx)} {n(-cy)})">{ch}</text>')
                out.append(f'<text x="{n(cx)}" y="{n(cy + size * 0.36)}" text-anchor="middle" font-family="{BRUSH}" font-size="{size}" '
                           f'fill="{st["fill"]}"{stroke}{filt} opacity="{a:.3f}" transform="{tr}">{ch}</text>')
        return "".join(out)

    def subtitle(self, t, name):
        if name == "end":
            return ""
        cur = None
        for k, (t0, zh) in enumerate(self.subs):
            if t >= t0 - 0.1:
                cur = (t0, zh)
        if not cur:
            return ""
        a = ease_out((t - cur[0] + 0.1) / 0.3)
        st = STYLE[name]
        return (f'<text x="{CX}" y="{H - BAR - 30}" text-anchor="middle" font-family="{HAND}" font-size="40" letter-spacing="3" '
                f'fill="{st["sub"]}" opacity="{0.9 * a:.3f}" filter="url(#sub)">{cur[1]}</text>')

    def flash(self, t):
        op = 0.0
        for k, (s, name) in enumerate(self.scenes[1:]):
            dt = t - s
            strength, tau = {"bloom": (1.0, 0.35), "end": (1.0, 0.45)}.get(name, (0.85, 0.16))
            if 0 <= dt < 2.0:
                op = max(op, strength * math.exp(-dt / tau))
            elif name == "bloom" and -0.2 < dt < 0:
                op = max(op, 0.5 * (1 + dt / 0.2))
        return op

    DEFS = ('<defs>'
            '<filter id="gl" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="7" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            '<filter id="gls" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="3" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            '<filter id="glw" x="-40%" y="-40%" width="180%" height="180%"><feMorphology operator="dilate" radius="3" in="SourceAlpha" result="d"/>'
            '<feGaussianBlur in="d" stdDeviation="6" result="b"/><feFlood flood-color="#fff6f0"/><feComposite in2="b" operator="in" result="g"/>'
            '<feMerge><feMergeNode in="g"/><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            '<filter id="sh" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="0" stdDeviation="8" flood-color="#15181c" flood-opacity="0.7"/></filter>'
            '<filter id="sub" x="-10%" y="-60%" width="120%" height="220%"><feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#000" flood-opacity="0.25"/></filter>'
            f'<radialGradient id="hMe"><stop offset="0" stop-color="{ME}" stop-opacity="0.7"/><stop offset="1" stop-color="{ME}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="hYou"><stop offset="0" stop-color="{YOU}" stop-opacity="0.7"/><stop offset="1" stop-color="{YOU}" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="hStar"><stop offset="0" stop-color="#ffffff" stop-opacity="0.9"/><stop offset="0.25" stop-color="#dff2ff" stop-opacity="0.35"/>'
            '<stop offset="1" stop-color="#bfe6ff" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="hWarm"><stop offset="0" stop-color="#fffaf4" stop-opacity="0.95"/><stop offset="1" stop-color="#ffe9e4" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="hInk"><stop offset="0.8" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
            '</defs>')

    def svg(self, i):
        t = i / FPS
        name, s0, s1 = self.scene(t)
        u = t - s0
        if name == "sepia":
            inner = self.sc_sepia(t, t - self.chunks[0][0] + 1.0)
        elif name == "star":
            inner = self.sc_star(t, u, self.chunks[8][0])
        elif name == "score":
            inner = self.sc_score(t, u, s0)
        elif name == "end":
            inner = self.sc_end(t, u, self.scenes[6][0])
        else:
            inner = getattr(self, "sc_" + name)(t, u)
        z = 1 + 0.012 * float(self.kick[min(i, len(self.kick) - 1)])
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', self.DEFS,
               f'<g transform="translate({CX} {CY}) scale({z:.4f}) translate({-CX} {-CY})">{inner}</g>',
               self.lyrics(t, name, s0, s1), self.subtitle(t, name)]
        fl = self.flash(t)
        if self.t_in is not None and t < self.t_in + 0.5:
            fl = max(fl, 1 - (t - self.t_in) / 0.5)
        if fl > 0.004:
            out.append(f'<rect width="{W}" height="{H}" fill="#ffffff" opacity="{min(fl, 1):.3f}"/>')
        if self.t_out is not None and t > self.t_out - 1.0:
            out.append(f'<rect width="{W}" height="{H}" fill="#000" opacity="{clamp((t - self.t_out + 1.0) / 0.9):.3f}"/>')
        out.append(f'<rect width="{W}" height="{BAR}" fill="#000"/><rect y="{H - BAR}" width="{W}" height="{BAR}" fill="#000"/></svg>')
        return "".join(out)

    def warm(self):
        return "".join(sorted({c for _, s, *_ in self.chunks for c in s} | {c for _, zh in self.subs for c in zh})) + \
            "BloomingPlanetMusic—Xyris/花隈千冬fromARTIFACTS:ASCENSIØNFAN-MADENARRATIVEPV花開く惑星" + CLEF


class Renderer:
    def __init__(self, frame, fonts_dir, workdir, post=True):
        self.frame_src = frame
        self.post = post
        css = []
        for pkg, files in FONTS:
            base = [d for d in os.listdir(fonts_dir) if d.startswith(f"fontsource-{pkg}-") and os.path.isdir(os.path.join(fonts_dir, d))][0]
            css += [f'<link rel="stylesheet" href="file://{os.path.join(fonts_dir, base, "package", f"{x}.css")}">' for x in files]
        warm = frame.warm()
        probes = "".join(f'<span style="font-family:{fam};font-weight:{w};font-style:{s}">{warm}</span>' for fam, w, s in PROBES)
        path = os.path.join(workdir, ".effectpv_stage.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write('<!doctype html><html><head><meta charset="utf-8">' + "".join(css) +
                    '<style>html,body{margin:0;background:#000;overflow:hidden}#warm{position:absolute;top:-9999px}</style></head>'
                    f'<body><div id="s"></div><div id="warm">{probes}</div></body></html>')
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--font-render-hinting=none", "--force-color-profile=srgb",
                                                     "--allow-file-access-from-files"])
        self.page = self.browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        self.page.goto("file://" + path)
        self.page.evaluate("document.fonts.ready.then(() => true)")
        self.page.wait_for_timeout(500)

    def frame(self, i):
        self.page.evaluate("""s => new Promise(res => {
            const el = document.getElementById('s'); el.innerHTML = s;
            const urls = [...new Set([...el.querySelectorAll('image')].map(n => n.getAttribute('href')))];
            Promise.all(urls.map(u => new Promise(r => { const im = new Image(); im.onload = im.onerror = r; im.src = u; })))
              .then(() => requestAnimationFrame(() => requestAnimationFrame(() => res(true))));
        })""", self.frame_src.svg(i))
        shot = self.page.screenshot(type="jpeg", quality=100)
        if self.post:
            shot = P.process(shot, self.frame_src.scene(i / FPS)[0], i)
        return shot

    def close(self):
        self.browser.close()
        self.pw.stop()


def build(args):
    pv = EffectPV(args.fx, args.lrc, args.features)
    pv.t_in, pv.t_out = args.start, args.end
    return pv


def worker(args, a, b, seg):
    pv = build(args)
    r = Renderer(pv, args.fonts, os.path.dirname(os.path.abspath(args.output)), not args.no_post)
    proc = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
                             "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", seg], stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(a, b):
        proc.stdin.write(r.frame(i))
        if (i - a) % 120 == 0:
            print(f"[{os.path.basename(seg)}] {i - a + 1}/{b - a}，{(i - a + 1) / (time.time() - t0):.1f} 帧/秒", flush=True)
    r.close()
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg 失败")


def main():
    ap = argparse.ArgumentParser()
    for name in ("fx", "audio", "lrc", "features", "fonts", "output"):
        ap.add_argument(name)
    ap.add_argument("--start", type=float, default=256.9)
    ap.add_argument("--end", type=float, default=286.0)
    ap.add_argument("--still", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-post", action="store_true", help="不加合成后期（对比用）")
    args = ap.parse_args()
    args.fonts = os.path.abspath(args.fonts)
    if args.still:
        pv = build(args)
        pv.t_in = None
        r = Renderer(pv, args.fonts, os.path.dirname(os.path.abspath(args.output)), not args.no_post)
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
                    "-c:a", "aac", "-b:a", "320k", "-af", f"afade=t=in:d=0.3,afade=t=out:st={dur - 0.8:.3f}:d=0.8",
                    "-movflags", "+faststart", "-shortest", args.output], check=True)
    print("输出:", args.output)


if __name__ == "__main__":
    main()
