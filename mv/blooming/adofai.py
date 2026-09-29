#!/usr/bin/env python3
"""《Blooming Planet》叙事 × ADOFAI 特效谱风格试片（SVG，1080p60）。

两颗光（我 = 青，君 = 粉）按 ADOFAI 的走法一拍一格前进：一颗踩在格子上当轴心，另一颗绕它转到下一格。
路的形状讲剧情，走过的格子长出三渲二玫瑰（sprites.py 的素材），歌词逐字摆在路旁、踩到才弹出。
剧情见 STORY.md。

用法:
  adofai.py <素材目录> <音频> <歌词.lrc> <feat60.npz> <fonts目录> <输出.mp4> [--start 217 --end 237.5] [--still 秒,...] [--workers 4]
"""
import argparse
import math
import os
import subprocess
import sys
import time
from multiprocessing import Process

import imageio_ffmpeg
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import compose as C  # noqa: E402
import pv2d as P  # noqa: E402
from story import SERIF, TECH  # noqa: E402

W, H, FPS = 1920, 1080, 60
ME, YOU = "#8ff0e6", "#f7b7d2"
L = 1.0  # 格距（世界单位）
UNIT = 118  # 默认缩放：1 世界单位 = 118 px

# 各段起点（拍号）；与 feat60 的节拍网格对应，见 STORY.md
B0 = 705  # 路的第一格
B_S2, B_S3, B_S4, B_S5, B_END = 709, 724, 742, 757, 772
B_MEET = 735.5  # 两人相会（3:46.3）
B_THROUGH = 756.0  # 穿门


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


def f2(x):
    return f"{x:.2f}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_path():
    """按拍生成格子坐标：heading 为走向下一格的方向（度，屏幕坐标 y 向下，0 = 向右）。"""
    headings = []
    headings += [0] * (B_S2 - B0)  # 序章：向右
    rise = [-90, -90, -60, -60, -120, -120, -60, -60, -120, -120, -90, -90, -60, -120, -90]
    headings += rise[:B_S3 - B_S2]  # 未来へ舞い上がれ：向上攀升
    h = -90.0
    for _ in range(16):  # 君となら、輝く：逆时针绕一圈把大花围在左侧，出圈后向右走不会穿过花
        headings.append(h)
        h -= 22.5
    headings += [-45, 0][:B_S4 - B_S3 - 16]
    for k in range(B_S5 - B_S4):  # 新しい世界へ：直通门
        headings.append(12 * math.sin(k * 0.9))
    headings += [0] * 20
    pts = [np.array([0.0, 0.0])]
    for hd in headings:
        a = math.radians(hd)
        pts.append(pts[-1] + L * np.array([math.cos(a), math.sin(a)]))
    return np.array(pts)


class Adofai:
    def __init__(self, sprites, lrc, features):
        self.pv = P.PV2D(sprites, features)
        d = np.load(features)
        self.kick = d["kick"]
        per = float(d["beat_period"]) / FPS
        if 60 / per < 120:
            per /= 2
        self.per = per
        self.phase = float(d["beat_phase"]) / FPS
        self.lines = C.parse_lrc(lrc)
        self.path = build_path()
        # 绕圈的圆心（大花的位置）
        loop = self.path[B_S3 - B0:B_S3 - B0 + 16]
        self.loop_center = loop.mean(axis=0)
        self.door_pos = self.path[B_S5 - B0] + np.array([0.6, 0.0])
        rng = np.random.default_rng(3)
        self.tile_rose = [(rng.choice(P.COLORS, p=P.WEIGHTS), rng.uniform(0, 360), rng.choice([-1, 1]), rng.uniform(0.32, 0.5))
                          for _ in range(len(self.path))]
        self.bg_petals = rng.random((70, 5))
        # 歌词：每句的字分配到从该句起始拍开始的格子上
        self.words = []
        for s, e, text in self.lines:
            b = self.beat(s)
            if B0 <= b < B_END + 4 and text != "花開く惑星":
                start = int(round(b))
                for j, ch in enumerate(text):
                    self.words.append((start + j, ch, start, self.beat(min(e, s + 4.6))))

    def beat(self, t):
        return (t - self.phase) / self.per

    def time_of(self, b):
        return self.phase + b * self.per

    def kick_at(self, t):
        i = int(round(t * FPS))
        return float(self.kick[min(max(i, 0), len(self.kick) - 1)])

    # ------------------------------------------------------------ ADOFAI 走法

    def orbs(self, b):
        """返回 (我的位置, 君的位置, 轴心格号)。"""
        n = int(math.floor(b))
        frac = b - n
        k = clamp(n - B0, 0, len(self.path) - 2)
        k = int(k)
        pivot = self.path[k]
        prev = self.path[k - 1] if k > 0 else pivot - (self.path[k + 1] - pivot)
        nxt = self.path[k + 1]
        a0 = math.atan2(*(prev - pivot)[::-1])
        a1 = math.atan2(*(nxt - pivot)[::-1])
        delta = (a1 - a0) % (2 * math.pi)
        if delta < 1e-6:
            delta = 2 * math.pi
        if n < B0:
            frac = 0.0
        a = a0 + delta * frac
        moving = pivot + L * np.array([math.cos(a), math.sin(a)])
        if (n - B0) % 2 == 0:
            return pivot, moving, k
        return moving, pivot, k

    # ------------------------------------------------------------ camera

    def camera(self, t, b):
        me, you, k = self.orbs(b)
        focus = (me + you) / 2
        kick = self.kick_at(t)
        if b < B_S2:
            zoom, rot = lerp(1.9, 1.35, ease_io((b - B0) / 4)), 0
        elif b < B_S3:
            zoom, rot = 1.15, lerp(0, -12, ease_io((b - B_S2) / 15))
            focus = focus + np.array([0, -1.2])
        elif b < B_S4:
            p = (b - B_S3) / (B_S4 - B_S3)
            zoom = lerp(1.1, 0.72, ease_io(p * 1.6))
            rot = lerp(-12, 20, ease_io(p))
            focus = focus * (1 - ease_io(p * 1.5)) + self.loop_center * ease_io(p * 1.5)
        else:
            p = (b - B_S4) / (B_THROUGH - B_S4)
            zoom = lerp(1.0, 2.6, clamp(p) ** 3)
            rot = lerp(20, 0, ease_io(p * 2))
            focus = focus * (1 - clamp(p) ** 2) + self.door_pos * clamp(p) ** 2 + np.array([0, -0.9]) * clamp(p) ** 2
        return focus, zoom * (1 + 0.035 * kick), rot

    # ------------------------------------------------------------ drawing

    def background(self, t, b):
        if b < B_S2:
            top, bot = "#02070f", "#07202c"
        elif b < B_S3:
            top, bot = "#041829", "#0d4050"
        elif b < B_S4:
            top, bot = "#1a1030", "#0d3a4a"
        else:
            top, bot = "#07142a", "#12506a"
        out = ['<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
               f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/></linearGradient>'
               f'<radialGradient id="orbMe"><stop offset="0" stop-color="#fff"/><stop offset="0.35" stop-color="{ME}"/>'
               f'<stop offset="1" stop-color="{ME}" stop-opacity="0"/></radialGradient>'
               f'<radialGradient id="orbYou"><stop offset="0" stop-color="#fff"/><stop offset="0.35" stop-color="{YOU}"/>'
               f'<stop offset="1" stop-color="{YOU}" stop-opacity="0"/></radialGradient>'
               '<radialGradient id="soft"><stop offset="0" stop-color="#fff" stop-opacity="0.9"/>'
               '<stop offset="1" stop-color="#bff7f0" stop-opacity="0"/></radialGradient>'
               '<radialGradient id="vig" cx="0.5" cy="0.5" r="0.72"><stop offset="0.62" stop-color="#000" stop-opacity="0"/>'
               '<stop offset="1" stop-color="#01060c" stop-opacity="0.7"/></radialGradient>'
               '<filter id="blur6"><feGaussianBlur stdDeviation="6"/></filter></defs>',
               f'<rect width="{W}" height="{H}" fill="url(#bg)"/>']
        for x, y, r, ph in self.pv.stars:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#e6fffc" opacity="{0.3 + 0.3 * math.sin(t * 1.7 + ph):.2f}"/>')
        # 背景花瓣：攀升段向下流（我们在往上）
        speed = 260 if B_S2 <= b < B_S3 else 70
        for k, (a, bb, c, s, col) in enumerate(self.bg_petals):
            x = (a * W + 40 * math.sin(t + k)) % W
            y = (bb * H + t * speed * (0.5 + c)) % (H + 40) - 20
            color = P.PETAL_FILL[P.COLORS[int(col * len(P.COLORS)) % len(P.COLORS)]]
            out.append(f'<ellipse rx="{6 + 8 * s:.1f}" ry="{3 + 4 * s:.1f}" fill="{color}" opacity="0.35" '
                       f'transform="translate({x:.0f} {y:.0f}) rotate({(t * 50 + k * 37) % 360:.0f})"/>')
        return "".join(out)

    def world(self, t, b):
        focus, zoom, rot = self.camera(t, b)
        s = UNIT * zoom
        out = [f'<g transform="translate(960 540) rotate({f2(rot)}) scale({s:.3f}) translate({f2(-focus[0])} {f2(-focus[1])})">']
        me, you, k = self.orbs(b)
        cur = k
        # 圈中央的大花：相会时绽放
        if B_S3 - 2 <= b < B_S5:
            bloom = 0.05 + ease_out((b - (B_MEET - 1.5)) / 3.0)
            glow = math.exp(-max(b - B_MEET, 0) * 0.6) if b > B_MEET else 0
            c = self.loop_center
            out.append(f'<circle cx="{f2(c[0])}" cy="{f2(c[1])}" r="{f2(1.4 + 2.2 * glow)}" fill="url(#soft)" opacity="{0.25 + 0.6 * glow:.2f}"/>')
            out.append(self.pv.rose_img("pink", 90, bloom, c[0], c[1], 3.6, (t * 8) % 360))
        # 门
        if b >= B_S4 - 4:
            dp = self.door_pos
            dw = 4.2
            out.append(f'<circle cx="{f2(dp[0] + 0.4)}" cy="{f2(dp[1] - 1.2)}" r="{f2(1.2 + 3 * clamp((b - B_S4) / 14) ** 2)}" fill="url(#soft)" '
                       f'opacity="{0.4 + 0.6 * clamp((b - B_S4) / 14):.2f}"/>')
            out.append(f'<image href="{self.pv.href("door.png")}" x="{f2(dp[0] - dw / 2 + 0.4)}" y="{f2(dp[1] - P.DOOR_BASE_Y / 1024 * dw + 0.35)}" '
                       f'width="{f2(dw)}" height="{f2(dw)}"/>')
        # 路：已走过的暗一些，前方的亮
        lo, hi = max(0, cur - 40), min(len(self.path) - 1, cur + 14)
        pts_done = self.path[lo:cur + 1]
        pts_next = self.path[cur:hi + 1]
        if len(pts_done) > 1:
            out.append(self.polyline(pts_done, "#1d6f78", 0.66, 0.9) + self.polyline(pts_done, "#6fd6c9", 0.5, 0.55))
        if len(pts_next) > 1:
            out.append(self.polyline(pts_next, "#0b2d38", 0.7, 0.9) + self.polyline(pts_next, "#e9fffb", 0.52, 0.95))
        for i in range(lo, hi + 1):
            p = self.path[i]
            ahead = i > cur
            out.append(f'<circle cx="{f2(p[0])}" cy="{f2(p[1])}" r="0.09" fill="{"#1d6f78" if ahead else "#e9fffb"}" opacity="0.8"/>')
        # 走过的格子长出玫瑰（交替在路两侧）
        for i in range(lo, cur + 1):
            if i + B0 < B_S2 - 1:
                continue
            color, spin, side, size = self.tile_rose[i]
            nxt = self.path[min(i + 1, len(self.path) - 1)] - self.path[max(i - 1, 0)]
            nrm = np.array([-nxt[1], nxt[0]]) / (np.linalg.norm(nxt) + 1e-9)
            pos = self.path[i] + nrm * side * 0.62
            grow = ease_out((b - (i + B0)) / 2.5)
            out.append(self.pv.rose_img(color, 90, 0.05 + grow, pos[0], pos[1], 2.9 * size * (0.5 + 0.5 * grow), spin))
        # 落拍脉冲
        n = math.floor(b)
        if n >= B0:
            q = b - n
            p = self.path[min(n - B0, len(self.path) - 1)]
            out.append(f'<circle cx="{f2(p[0])}" cy="{f2(p[1])}" r="{f2(0.35 + 0.9 * ease_out(q))}" fill="none" stroke="#ffffff" '
                       f'stroke-width="{f2(0.08 * (1 - q))}" opacity="{1 - q:.2f}"/>')
        # 歌词：前方格子上的字，踩到才弹出
        for tile, ch, start, end in self.words:
            if tile - B0 >= len(self.path) or b > end + 1 or b < start - 1:
                continue
            p = self.path[tile - B0]
            nxt = self.path[min(tile - B0 + 1, len(self.path) - 1)] - self.path[max(tile - B0 - 1, 0)]
            nrm = np.array([nxt[1], -nxt[0]]) / (np.linalg.norm(nxt) + 1e-9)
            pos = p + nrm * 1.7
            if np.linalg.norm(pos - self.loop_center) < np.linalg.norm(p - self.loop_center):
                pos = p - nrm * 1.7  # 绕圈段：字放在圈外侧
            pop = ease_out((b - tile) / 0.35)
            if b < tile:
                a, sc = 0.25, 0.8
            else:
                a, sc = 1.0 * (1 - clamp((b - end) / 1.0)), 1.0 + 0.5 * (1 - pop)
            out.append(f'<g transform="translate({f2(pos[0])} {f2(pos[1])}) rotate({f2(-rot)}) scale({sc:.3f})" opacity="{a:.2f}">'
                       f'<text y="0.32" font-family="{SERIF}" font-weight="900" font-size="0.8" text-anchor="middle" fill="#ffffff" '
                       f'stroke="#1d6f78" stroke-width="0.09" paint-order="stroke">{esc(ch)}</text></g>')
        # 两颗光与光尾
        for j in range(12, 0, -1):
            pm, py, _ = self.orbs(b - j * 0.045)
            a = (1 - j / 13) * 0.5
            out.append(f'<circle cx="{f2(pm[0])}" cy="{f2(pm[1])}" r="{f2(0.16 * (1 - j / 14))}" fill="{ME}" opacity="{a:.2f}"/>')
            out.append(f'<circle cx="{f2(py[0])}" cy="{f2(py[1])}" r="{f2(0.16 * (1 - j / 14))}" fill="{YOU}" opacity="{a:.2f}"/>')
        meet = math.exp(-abs(b - B_MEET) * 1.5)
        for pos, grad in ((you, "orbYou"), (me, "orbMe")):
            out.append(f'<circle cx="{f2(pos[0])}" cy="{f2(pos[1])}" r="{f2(0.62 + 0.4 * meet)}" fill="url(#{grad})"/>')
            out.append(f'<circle cx="{f2(pos[0])}" cy="{f2(pos[1])}" r="0.2" fill="#ffffff"/>')
        out.append('</g>')
        return "".join(out)

    @staticmethod
    def polyline(pts, color, width, opacity):
        d = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)
        return (f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
                f'stroke-linejoin="round" opacity="{opacity}"/>')

    def finale(self, t, b):
        """花開く惑星：星球盛开，路变成环绕星球的光环，两颗光在环上继续走。"""
        p = (b - B_S5) / (B_END - B_S5)
        theta = lerp(318, 345, p)
        rpx, cx, cy = lerp(300, 330, ease_out(p)), 960, 560

        def bloom(r):
            return ease_out((b - B_S5 - 1 - (r.phase % 1) * 4) / 3) if r.giant else 1.0

        rx, ry = rpx * 1.75, rpx * 0.5
        back, front = [], []
        n_tiles = 28
        for i in range(n_tiles):
            a = 2 * math.pi * i / n_tiles
            x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
            el = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#e9fffb" opacity="0.9"/>'
            (front if math.sin(a) > 0 else back).append(el)
        ring = (f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.1f}" ry="{ry:.1f}" fill="none" stroke="#bff7f0" stroke-width="16" opacity="0.35"/>')
        out = [ring] + back + [self.pv.planet_img(theta, cx, cy, rpx), self.pv.draw_roses(theta, cx, cy, rpx, bloom, t, 2)]
        # 前半圈的环盖在星球前面
        out.append(f'<path d="M {cx - rx:.1f} {cy} A {rx:.1f} {ry:.1f} 0 0 0 {cx + rx:.1f} {cy}" fill="none" stroke="#e9fffb" stroke-width="16" opacity="0.55"/>')
        out += front
        # 两颗光沿环走（仍是一拍一步、互相绕转）
        step = 2 * math.pi / n_tiles
        n = math.floor(b)
        q = b - n
        base = (n - B_S5) * step
        pivot_a = base
        piv = (cx + rx * math.cos(pivot_a), cy + ry * math.sin(pivot_a))
        ang0 = math.atan2(ry * math.sin(pivot_a - step) - ry * math.sin(pivot_a), rx * math.cos(pivot_a - step) - rx * math.cos(pivot_a))
        ang1 = math.atan2(ry * math.sin(pivot_a + step) - ry * math.sin(pivot_a), rx * math.cos(pivot_a + step) - rx * math.cos(pivot_a))
        delta = (ang1 - ang0) % (2 * math.pi) or 2 * math.pi
        a = ang0 + delta * q
        dist = math.hypot(rx * (math.cos(pivot_a + step) - math.cos(pivot_a)), ry * (math.sin(pivot_a + step) - math.sin(pivot_a)))
        mov = (piv[0] + dist * math.cos(a), piv[1] + dist * math.sin(a))
        me, you = (piv, mov) if (n - B_S5) % 2 == 0 else (mov, piv)
        for pos, col in ((you, "orbYou"), (me, "orbMe")):
            out.append(f'<circle cx="{pos[0]:.1f}" cy="{pos[1]:.1f}" r="44" fill="url(#{col})"/><circle cx="{pos[0]:.1f}" cy="{pos[1]:.1f}" r="12" fill="#fff"/>')
        return "".join(out)

    def hud(self, t, b):
        out = ['<rect width="1920" height="1080" fill="url(#vig)"/>']
        # 章节卡（开头）
        if b < B_S2 + 0.5:
            a = ease_out((b - B0 + 0.3) / 1.2) * (1 - clamp((b - B_S2 + 0.3) / 0.8))
            out.append(f'<g opacity="{a:.2f}" text-anchor="middle">'
                       f'<text x="960" y="250" font-family="{TECH}" font-size="26" fill="{ME}" letter-spacing="14">CHAPTER IV</text>'
                       f'<text x="960" y="318" font-family="{SERIF}" font-size="56" font-weight="700" fill="#fff" letter-spacing="10">ふたりの足跡が、花になる</text>'
                       f'<line x1="700" y1="345" x2="1220" y2="345" stroke="#bff7f0" stroke-width="1.5" opacity="0.7"/></g>')
        # 下方整句字幕
        cur = [(s, e, x) for s, e, x in self.lines if s - 0.05 <= t < min(e, s + 4.6)]
        if cur and cur[-1][2] != "花開く惑星":
            s, e, text = cur[-1]
            a = ease_out((t - s) / 0.3) * (1 - clamp((t - (min(e, s + 4.6) - 0.3)) / 0.3))
            out.append(f'<text x="960" y="1010" font-family="{SERIF}" font-size="34" font-weight="500" fill="#ffffff" text-anchor="middle" '
                       f'letter-spacing="10" opacity="{a * 0.9:.2f}" stroke="#0b3a44" stroke-width="5" paint-order="stroke">{esc(text)}</text>')
        # 标题
        if b >= B_S5:
            s = self.time_of(B_S5) - 0.1
            a = ease_out((t - s - 0.5) / 0.6)
            out.append(f'<g opacity="{a:.2f}" text-anchor="middle">'
                       f'<text x="960" y="170" font-family="{SERIF}" font-size="96" font-weight="900" fill="#fff" stroke="#1d6f78" stroke-width="7" '
                       f'paint-order="stroke" letter-spacing="10">花開く惑星</text>'
                       f'<text x="960" y="222" font-family="{TECH}" font-size="26" font-weight="700" fill="#fff" letter-spacing="14" '
                       f'stroke="#1d6f78" stroke-width="4" paint-order="stroke">BLOOMING PLANET</text>'
                       f'<text x="960" y="1010" font-family="{SERIF}" font-size="26" fill="#fff" letter-spacing="8" stroke="#0b3a44" stroke-width="4" '
                       f'paint-order="stroke">Xyris / 花隈千冬</text></g>')
        # 白闪：每段开头、相会、穿门
        white = 0.0
        for bb, dur, peak in ((B_S2, 0.8, 0.7), (B_S3, 0.8, 0.7), (B_MEET, 1.6, 0.55), (B_S4, 0.8, 0.6)):
            if bb <= b < bb + dur:
                white = max(white, peak * (1 - (b - bb) / dur))
        if B_THROUGH - 1.6 <= b < B_S5 + 2.4:
            white = max(white, clamp((b - (B_THROUGH - 1.6)) / 1.6) if b < B_S5 else 1 - ease_out((b - B_S5) / 2.4))
        if white > 0:
            out.append(f'<rect width="1920" height="1080" fill="#f4fffd" opacity="{white:.3f}"/>')
        return "".join(out)

    def svg(self, i):
        t = i / FPS
        b = self.beat(t)
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', self.background(t, b)]
        out.append(self.finale(t, b) if b >= B_S5 else self.world(t, b))
        out.append(self.hud(t, b))
        out.append('</svg>')
        return "".join(out)


def warm_text(lines):
    return "".join(sorted({c for _, _, s in lines for c in s})) + "花隈千冬ふたりの足跡が、花になるCHAPTERIV"


def worker(args, a, b, seg):
    ad = Adofai(args.sprites, args.lrc, args.features)
    r = P.Renderer(ad, args.fonts, os.path.dirname(os.path.abspath(args.output)), warm_text(ad.lines))
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
    for name in ("sprites", "audio", "lrc", "features", "fonts", "output"):
        ap.add_argument(name)
    ap.add_argument("--start", type=float, default=217.0)
    ap.add_argument("--end", type=float, default=237.5)
    ap.add_argument("--still", default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    args.fonts = os.path.abspath(args.fonts)
    if args.still:
        ad = Adofai(args.sprites, args.lrc, args.features)
        r = P.Renderer(ad, args.fonts, os.path.dirname(os.path.abspath(args.output)), warm_text(ad.lines))
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
