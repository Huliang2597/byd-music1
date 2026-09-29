#!/usr/bin/env python3
"""叙事风格（BOF BGA 式）动画：逐帧生成 SVG → 无头 Chromium 渲染 → 1080p60 视频。

镜头按拍子编排（BPM≈185，第 88 拍 = 0:28.75 主段进入）。
用法:
  story.py <音频> <features.npz> <cover.png> <fonts目录> <输出.mp4> [--start 秒] [--end 秒] [--still 秒,...] [--workers N]
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
from playwright.sync_api import sync_playwright

W, H = 1920, 1080
FPS = 60
SERIF = "'Noto Serif JP', serif"
SANS = "'Zen Kaku Gothic New', sans-serif"
TECH = "'Orbitron', sans-serif"

TEAL = "#2fd6c3"
AQUA = "#8ff0e6"
ICE = "#e9fffb"
BLUE = "#6fb4f0"
GOLD = "#ecc880"
NAVY = "#050f1c"

DROP = 88  # 主段进入的拍号

# 封面（500×500）里的局部区域 (x, y, w, h)
CROP_EYES = (262, 118, 176, 99)
CROP_FACE = (220, 40, 250, 141)
CROP_FLOWERS = (150, 170, 230, 129)
CROP_ASTRO = (10, 50, 230, 129)
CROP_BOUQUET = (170, 250, 220, 124)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp(x)
    return x ** 3


def ease_io(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b - a) * t


def f1(x):
    return f"{x:.1f}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def rnd(k, salt=0):
    """确定性伪随机 0..1。"""
    x = math.sin(k * 12.9898 + salt * 78.233) * 43758.5453
    return x - math.floor(x)


class Story:
    def __init__(self, audio_path, features_path, cover_path):
        d = np.load(features_path)
        self.n = int(d["n_frames"])
        self.kick = d["kick"]
        self.kicks = d["kicks"]
        self.bass = d["bass"]
        self.loud = d["loud"]
        self.spec = d["spectrum"]
        self.period = float(d["beat_period"])
        self.phase = float(d["beat_phase"])
        self.cover = os.path.basename(cover_path)
        self.dir = os.path.dirname(os.path.abspath(cover_path))
        import soundfile as sf
        self.duration = sf.info(audio_path).duration

    def beat_of(self, i):
        return (i - self.phase) / self.period

    def frame_of_beat(self, b):
        return self.phase + b * self.period

    # ------------------------------------------------------------ building blocks

    def crop(self, region, x, y, w, h, extra=""):
        """把封面的一块区域 (rx, ry, rw, rh) 铺进 (x, y, w, h)。"""
        rx, ry, rw, rh = region
        return (f'<svg x="{f1(x)}" y="{f1(y)}" width="{f1(w)}" height="{f1(h)}" viewBox="{rx:.2f} {ry:.2f} {rw:.2f} {rh:.2f}" '
                f'preserveAspectRatio="xMidYMid slice" {extra}><image href="{self.cover}" width="500" height="500"/></svg>')

    @staticmethod
    def pan(region, dx, dy, zoom):
        rx, ry, rw, rh = region
        nw, nh = rw / zoom, rh / zoom
        return (rx + (rw - nw) / 2 + dx, ry + (rh - nh) / 2 + dy, nw, nh)

    @staticmethod
    def letterbox(h):
        if h <= 0.5:
            return ""
        return (f'<rect width="{W}" height="{f1(h)}" fill="#000"/>'
                f'<rect y="{f1(H - h)}" width="{W}" height="{f1(h)}" fill="#000"/>')

    @staticmethod
    def typewriter(text, progress):
        n = int(len(text) * clamp(progress) + 1e-6)
        return text[:n]

    def glint(self, x, y, size, opacity, rot=0):
        s = size / 10
        return (f'<g transform="translate({f1(x)} {f1(y)}) rotate({f1(rot)}) scale({s:.3f})" opacity="{opacity:.3f}">'
                f'<circle r="9" fill="url(#softdot)"/>'
                '<path d="M0 -10 Q1.2 -1.2 10 0 Q1.2 1.2 0 10 Q-1.2 1.2 -10 0 Q-1.2 -1.2 0 -10Z" fill="#fff"/></g>')

    def hero(self, x, y, size, energy):
        """主角：一粒会发光的光。"""
        return (f'<g transform="translate({f1(x)} {f1(y)})">'
                f'<circle r="{f1(size * (3.2 + 1.5 * energy))}" fill="url(#herohalo)" opacity="{0.55 + 0.45 * energy:.3f}"/>'
                f'<rect x="{f1(-size)}" y="{f1(-size)}" width="{f1(2 * size)}" height="{f1(2 * size)}" transform="rotate(45)" fill="#fff"/>'
                f'<rect x="{f1(-size * 1.8)}" y="{f1(-size * 1.8)}" width="{f1(3.6 * size)}" height="{f1(3.6 * size)}" transform="rotate(45)" '
                f'fill="none" stroke="{AQUA}" stroke-width="1.5" opacity="0.7"/></g>')

    def dust(self, i, n, speed, color, opacity, salt=0, up=False):
        parts = []
        t = i / FPS
        for k in range(n):
            x = rnd(k, salt + 1) * W
            yy = (rnd(k, salt + 2) * (H + 40) + (-1 if up else 1) * t * speed * (0.4 + rnd(k, salt + 3))) % (H + 40) - 20
            r = 0.8 + 2.2 * rnd(k, salt + 4)
            a = opacity * (0.3 + 0.7 * rnd(k, salt + 5)) * (0.6 + 0.4 * math.sin(t * 2 + k))
            parts.append(f'<circle cx="{f1(x)}" cy="{f1(yy)}" r="{r:.2f}" fill="{color}" opacity="{a:.3f}"/>')
        return "".join(parts)

    def defs(self):
        return (
            '<defs>'
            '<radialGradient id="softdot"><stop offset="0" stop-color="#fff" stop-opacity="0.9"/>'
            f'<stop offset="0.4" stop-color="{AQUA}" stop-opacity="0.35"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="herohalo"><stop offset="0" stop-color="#fff" stop-opacity="0.95"/>'
            f'<stop offset="0.25" stop-color="{AQUA}" stop-opacity="0.55"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="vignette" cx="0.5" cy="0.5" r="0.75"><stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0.85"/></radialGradient>'
            f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#03101d"/><stop offset="1" stop-color="#0b3440"/></linearGradient>'
            '<linearGradient id="shade" x1="0" x2="1"><stop offset="0.35" stop-color="#021018" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#021018" stop-opacity="0.75"/></linearGradient>'
            '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.3" fill="#000" opacity="0.35"/></pattern>'
            '<pattern id="stripes" width="46" height="46" patternUnits="userSpaceOnUse" patternTransform="rotate(-24)">'
            f'<rect width="18" height="46" fill="{TEAL}" opacity="0.18"/></pattern>'
            '<filter id="memory" x="0" y="0" width="1" height="1"><feColorMatrix type="saturate" values="0.2"/>'
            '<feComponentTransfer><feFuncR type="linear" slope="0.55"/><feFuncG type="linear" slope="0.85" intercept="0.03"/>'
            '<feFuncB type="linear" slope="1.0" intercept="0.08"/></feComponentTransfer><feGaussianBlur stdDeviation="1.2"/></filter>'
            '<filter id="teal" x="0" y="0" width="1" height="1"><feColorMatrix type="matrix" '
            'values="0.5 0.2 0.08 0 -0.02  0.12 0.78 0.2 0 0  0.08 0.25 0.8 0 0.03  0 0 0 1 0"/></filter>'
            '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            '<filter id="bigglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            '</defs>'
        )

    # ------------------------------------------------------------ frame

    def svg(self, i):
        b = self.beat_of(i)
        kick = float(self.kick[i]) if i < self.n else 0.0
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', self.defs()]
        if b < 71.8:
            out.append(self.s1_memory(i, b))
        elif b < 79.5:
            out.append(self.s2_layer_zero(i, b))
        elif b < DROP:
            out.append(self.s3_gate(i, b))
        elif b < 92:
            out.append(self.s4_title(i, b, kick))
        elif b < 100:
            out.append(self.s5_shaft(i, b, kick))
        elif b < 104:
            out.append(self.s6_montage(i, b, kick))
        else:
            out.append(self.s7_climb(i, b, kick))
        out.append(self.hud(i, b, kick))
        # 主段进入的白闪
        if DROP <= b < DROP + 1.2:
            out.append(f'<rect width="{W}" height="{H}" fill="#fff" opacity="{(1 - (b - DROP) / 1.2) ** 2:.3f}"/>')
        out.append('</svg>')
        return "".join(out)

    # ---- S1 22.0–23.5s：记忆里的眼睛
    def s1_memory(self, i, b):
        p = clamp((b - 67.0) / 4.8)
        region = self.pan(CROP_EYES, lerp(-14, 10, p), lerp(4, -2, p), lerp(1.0, 1.12, p))
        flicker = 0.85 + 0.15 * math.sin(i * 1.7) * (1 if rnd(i // 3, 9) > 0.7 else 0)
        glint_a = clamp((b - 69.2) / 0.6) * (1 - clamp((b - 71.0) / 0.8))
        cap = clamp((b - 67.6) / 1.2)
        return (
            f'<rect width="{W}" height="{H}" fill="{NAVY}"/>'
            f'<g filter="url(#memory)" opacity="{0.9 * flicker:.3f}">{self.crop(region, 0, 150, W, 780)}</g>'
            f'<rect y="150" width="{W}" height="780" fill="url(#scan)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#vignette)"/>'
            + self.glint(1120, 520, 44 + 10 * math.sin(b * 3), glint_a, b * 20)
            + self.letterbox(150)
            + f'<g opacity="{cap:.3f}" font-family="{SERIF}" text-anchor="middle">'
            f'<text x="960" y="1010" font-size="40" font-weight="500" fill="{ICE}" letter-spacing="8">{esc(self.typewriter("記憶の底で、光が瞬いた", cap * 1.4))}</text>'
            f'<text x="960" y="1052" font-family="{TECH}" font-size="15" fill="{AQUA}" letter-spacing="6" opacity="0.8">'
            'IN THE DEPTHS OF MEMORY, A LIGHT FLICKERED</text></g>'
            + f'<text x="80" y="100" font-family="{TECH}" font-size="16" fill="{AQUA}" letter-spacing="5" opacity="{0.6 * cap:.3f}">ARCHIVE ◆ REC</text>'
        )

    # ---- S2 23.5–26.0s：第零层
    def s2_layer_zero(self, i, b):
        n, frac = math.floor(b), b - math.floor(b)
        beatpulse = (1 - ease_out(frac * 2)) if n >= 72 else 0
        line = ease_io((b - 72.0) / 3.0)
        jp = self.typewriter("ここは、第零層。", (b - 72.5) / 3.5)
        en = clamp((b - 76.4) / 1.0)
        return (
            f'<rect width="{W}" height="{H}" fill="#000"/>'
            + self.dust(i, 60, 18, AQUA, 0.35, salt=3)
            + self.hero(960, 470, 5 + 2 * beatpulse, 0.2 + 0.6 * beatpulse)
            + f'<line x1="{f1(960 - 520 * line)}" y1="560" x2="{f1(960 + 520 * line)}" y2="560" stroke="{AQUA}" stroke-width="1.2" opacity="0.7"/>'
            + f'<text x="960" y="640" font-family="{SERIF}" font-size="62" font-weight="700" fill="#fff" text-anchor="middle" letter-spacing="14">{esc(jp)}</text>'
            + f'<text x="960" y="700" font-family="{TECH}" font-size="20" fill="{AQUA}" text-anchor="middle" letter-spacing="10" opacity="{en:.3f}">'
            'LAYER 00 — THE SILENT STRATUM</text>'
            + self.letterbox(150)
        )

    # ---- S3 26.0–28.75s：星盘之门，蓄力
    def s3_gate(self, i, b):
        p = (b - 79.5) / (DROP - 79.5)
        cam = 1 + 0.55 * ease_in((b - 85.5) / 2.5)
        rot = 40 * p * p * 8
        parts = [f'<rect width="{W}" height="{H}" fill="url(#sky)"/>', self.dust(i, 70, 60 + 300 * p, AQUA, 0.5, salt=5, up=True)]
        parts.append(f'<g transform="translate(960 540) scale({cam:.4f})">')
        lit_count = int(clamp(b - 79.5, 0, 8.5))
        for k in range(8):
            r = 110 + k * 46
            lit = k < lit_count
            since = b - (80 + k) if lit else -1
            flash = (1 - ease_out(since / 0.8)) if 0 <= since < 0.8 else 0
            direction = 1 if k % 2 == 0 else -1
            ang = direction * rot * (1 + k * 0.15)
            dash = "3 9" if k % 3 == 0 else ("40 14" if k % 3 == 1 else "1 5")
            op = 0.18 + (0.55 if lit else 0) + 0.3 * flash
            col = GOLD if k == 7 else (ICE if flash > 0.3 else TEAL)
            parts.append(f'<circle r="{r}" fill="none" stroke="{col}" stroke-width="{2 + 3 * flash:.2f}" stroke-dasharray="{dash}" '
                         f'opacity="{op:.3f}" transform="rotate({f1(ang)})"/>')
        # 八角星与中心的光
        star = []
        for k in range(16):
            ang = math.radians(k * 22.5 + rot * 0.5)
            r = 470 if k % 2 == 0 else 150
            star.append(f"{r * math.cos(ang):.1f},{r * math.sin(ang):.1f}")
        parts.append(f'<polygon points="{" ".join(star)}" fill="none" stroke="{GOLD}" stroke-width="1.2" opacity="{0.25 + 0.4 * p:.3f}"/>')
        parts.append(self.hero(0, 0, 7 + 5 * p, 0.3 + 0.7 * p))
        parts.append('</g>')
        # 每拍闪切的字
        words = {80: ("目を開け", "OPEN YOUR EYES"), 82: ("声を聴け", "HEAR THE CALL"), 84: ("層を越え", "CROSS THE STRATA")}
        n, frac = math.floor(b), b - math.floor(b)
        key = n - (n % 2)
        if key in words and b < 86:
            jp, en = words[key]
            a = 1 - ease_in(((b - key) - 1.4) / 0.6)
            x = 420 if (key // 2) % 2 == 0 else 1500
            parts.append(f'<g opacity="{a:.3f}" text-anchor="middle">'
                         f'<text x="{x}" y="560" font-family="{SERIF}" font-size="92" font-weight="900" fill="#fff" '
                         f'writing-mode="vertical-rl" letter-spacing="10" filter="url(#glow)">{esc(jp)}</text>'
                         f'<text x="{x}" y="920" font-family="{TECH}" font-size="16" fill="{AQUA}" letter-spacing="6">{en}</text></g>')
        if b >= 86:
            half = int((b - 86) * 2)
            jp, en = [("昇れ", "ASCEND"), ("ASCEND", ""), ("昇れ", "ASCEND"), ("躍れ", "LEAP")][min(half, 3)]
            size = 220 + 40 * (1 - ease_out((b - 86) * 2 - half))
            font = SERIF if not jp.isascii() else TECH
            parts.append(f'<text x="960" y="{f1(540 + size * 0.35)}" font-family="{font}" font-size="{f1(size)}" font-weight="900" fill="#fff" '
                         f'text-anchor="middle" letter-spacing="12" opacity="0.92" filter="url(#bigglow)">{esc(jp)}</text>')
        white = ease_in((b - 86.5) / 1.5) * 0.9
        parts.append(f'<rect width="{W}" height="{H}" fill="#fff" opacity="{white:.3f}"/>')
        box = 150 * (1 - ease_io((b - 87.3) / 0.7))
        parts.append(self.letterbox(box))
        return "".join(parts)

    # ---- S4 28.75–30.1s：标题砸入
    def s4_title(self, i, b, kick):
        p = b - DROP
        shake = 14 * kick
        sx, sy = shake * math.sin(i * 1.3), shake * math.cos(i * 1.9)
        reveal = ease_out(p / 0.5)
        punch = 1 + 0.06 * kick
        slide = lerp(260, 0, ease_out(p / 0.7))
        panel = [(1010 + slide, 0), (1920, 0), (1920, 1080), (720 + slide, 1080)]
        pts = " ".join(f"{f1(x)},{f1(y)}" for x, y in panel)
        region = self.pan((40, 0, 460, 500), lerp(10, -10, p / 4), 0, lerp(1.0, 1.08, p / 4))
        clip_w = 1920 * reveal
        return (
            f'<rect width="{W}" height="{H}" fill="#04121e"/>'
            f'<rect width="{W}" height="{H}" fill="url(#stripes)" transform="translate({f1(-(p * 60) % 46)} 0)"/>'
            f'<g transform="translate({f1(sx)} {f1(sy)})">'
            f'<clipPath id="panel"><polygon points="{pts}"/></clipPath>'
            f'<g clip-path="url(#panel)" filter="url(#teal)">{self.crop(region, 700 + slide, 0, 1220, 1080)}</g>'
            f'<polygon points="{pts}" fill="none" stroke="{ICE}" stroke-width="6"/>'
            f'<line x1="{f1(990 + slide)}" y1="-10" x2="{f1(700 + slide)}" y2="1090" stroke="{GOLD}" stroke-width="3"/>'
            f'<clipPath id="wipe"><polygon points="0,0 {f1(clip_w + 200)},0 {f1(clip_w)},1080 0,1080"/></clipPath>'
            f'<g clip-path="url(#wipe)"><g transform="translate(120 600) scale({punch:.4f})">'
            f'<text x="6" y="4" font-family="{SERIF}" font-size="190" font-weight="900" fill="{TEAL}" opacity="0.55" letter-spacing="6">叡の躍層</text>'
            f'<text x="-4" y="-3" font-family="{SERIF}" font-size="190" font-weight="900" fill="{GOLD}" opacity="0.35" letter-spacing="6">叡の躍層</text>'
            f'<text font-family="{SERIF}" font-size="190" font-weight="900" fill="#fff" letter-spacing="6">叡の躍層</text></g></g>'
            f'<g opacity="{ease_out((p - 0.4) / 0.6):.3f}" transform="translate({f1(lerp(-40, 0, ease_out((p - 0.4) / 0.6)))} 0)">'
            f'<rect x="126" y="660" width="460" height="4" fill="{TEAL}"/>'
            f'<text x="126" y="730" font-family="{TECH}" font-size="48" font-weight="700" fill="#fff" letter-spacing="10">LINK"0</text>'
            f'<text x="126" y="780" font-family="{TECH}" font-size="18" fill="{AQUA}" letter-spacing="7">ARTIFACTS:ASCENSIØN — TRACK 06</text></g>'
            '</g>'
            + self.dust(i, 40, 220, "#fff", 0.6, salt=7, up=True)
        )

    # ---- S5 30.1–32.6s：竖井，一层层穿过
    def s5_shaft(self, i, b, kick):
        cx, cy = 960, 520
        parts = [f'<rect width="{W}" height="{H}" fill="url(#sky)"/>']
        # 放射状速度线
        for k in range(48):
            ang = rnd(k, 11) * 2 * math.pi
            ph = (b * 0.9 + rnd(k, 12)) % 1
            r1 = 120 + 1100 * ph ** 2
            r2 = r1 + 60 + 220 * ph
            c, s = math.cos(ang), math.sin(ang)
            parts.append(f'<line x1="{f1(cx + r1 * c)}" y1="{f1(cy + r1 * s)}" x2="{f1(cx + r2 * c)}" y2="{f1(cy + r2 * s)}" '
                         f'stroke="{ICE}" stroke-width="{1 + 2 * ph:.2f}" opacity="{0.15 + 0.5 * ph:.3f}"/>')
        # 层：每拍一层迎面穿过
        for n in range(12, -2, -1):
            layer = math.floor(b) + n
            dz = layer - b
            if dz <= -0.15:
                continue
            scale = 1 / (0.12 + 0.34 * max(dz, 0.0))
            size = 300 * scale
            a = clamp(1.4 - dz * 0.12) * clamp((dz + 0.15) / 0.5)
            rot = layer * 9
            major = layer % 4 == 0
            col = GOLD if major else TEAL
            sw = (2.5 if major else 1.4) * min(scale, 5)
            parts.append(f'<g transform="translate({cx} {cy}) rotate({f1(rot)})" opacity="{a:.3f}">'
                         f'<rect x="{f1(-size / 2)}" y="{f1(-size / 2)}" width="{f1(size)}" height="{f1(size)}" fill="none" stroke="{col}" stroke-width="{sw:.2f}"/>')
            if major and size > 200:
                label = f"LAYER {((layer - 92) // 4) + 1:02d}" if layer >= 92 else "LAYER 00"
                parts.append(f'<text x="{f1(-size / 2 + 12)}" y="{f1(-size / 2 - 12)}" font-family="{TECH}" font-size="{f1(min(22 * scale / 2, 60))}" '
                             f'fill="{GOLD}" letter-spacing="4">{label}</text>')
            parts.append('</g>')
        parts.append(self.hero(cx, cy, 9 + 5 * kick, 0.6 + 0.4 * kick))
        # 两侧字幕
        la = ease_out((b - 93) / 0.8) * (1 - ease_in((b - 99.2) / 0.8))
        parts.append(f'<g opacity="{la:.3f}">'
                     f'<text x="200" y="300" font-family="{SERIF}" font-size="64" font-weight="700" fill="#fff" writing-mode="vertical-rl" '
                     f'letter-spacing="14" filter="url(#glow)">まだ、上へ</text>'
                     f'<text x="1720" y="860" font-family="{TECH}" font-size="22" fill="{AQUA}" text-anchor="end" letter-spacing="10">HIGHER, STILL HIGHER</text></g>')
        return "".join(parts)

    # ---- S6 32.6–33.9s：曲绘快切
    def s6_montage(self, i, b, kick):
        cuts = [(CROP_FLOWERS, "咲け", "BLOOM"), (CROP_ASTRO, "巡れ", "TURN"), (CROP_EYES, "視よ", "SEE"), (CROP_FACE, "跳べ", "LEAP")]
        k = min(3, int(b - 100))
        region, jp, en = cuts[k]
        p = b - 100 - k
        slide = lerp(160, 0, ease_out(p / 0.25)) * (1 if k % 2 == 0 else -1)
        region = self.pan(region, lerp(-6, 6, p), 0, lerp(1.0, 1.1, p))
        panel = [(140 + slide, 90), (1920, 90), (1780 + slide, 990), (0, 990)]
        pts = " ".join(f"{f1(x)},{f1(y)}" for x, y in panel)
        flash = (1 - ease_out(p / 0.3)) * 0.7
        return (
            f'<rect width="{W}" height="{H}" fill="#03101b"/>'
            f'<clipPath id="cut"><polygon points="{pts}"/></clipPath>'
            f'<g clip-path="url(#cut)" filter="url(#teal)">{self.crop(region, slide, 90, W, 900)}</g>'
            f'<rect x="0" y="90" width="{W}" height="900" fill="url(#scan)" opacity="0.5" clip-path="url(#cut)"/>'
            f'<rect x="0" y="90" width="{W}" height="900" fill="url(#shade)" clip-path="url(#cut)"/>'
            f'<polygon points="{pts}" fill="none" stroke="{ICE}" stroke-width="5"/>'
            f'<text x="{f1(1500 - slide * 0.5)}" y="700" font-family="{SERIF}" font-size="260" font-weight="900" fill="#fff" '
            f'text-anchor="middle" filter="url(#bigglow)" opacity="0.95">{jp}</text>'
            f'<text x="{f1(1500 - slide * 0.5)}" y="780" font-family="{TECH}" font-size="30" font-weight="700" fill="#fff" text-anchor="middle" letter-spacing="18">{en}</text>'
            f'<text x="80" y="1040" font-family="{TECH}" font-size="18" fill="{GOLD}" letter-spacing="6">FRAGMENT {k + 1:02d} / 04</text>'
            f'<rect width="{W}" height="{H}" fill="#fff" opacity="{flash:.3f}"/>'
        )

    # ---- S7 33.9–37.0s：俯瞰星盘，向上攀升
    def s7_climb(self, i, b, kick):
        p = b - 104
        parts = [f'<rect width="{W}" height="{H}" fill="url(#sky)"/>', self.dust(i, 90, 420, ICE, 0.55, salt=13)]
        # 一层层星盘平台从上方落下（我们在上升）
        for n in range(-1, 7):
            layer = math.floor(p / 1.0) + n
            y = 1300 - (layer - p) * 190
            depth = clamp((y - 100) / 1100)
            rx = 260 + 620 * depth
            ry = rx * 0.22
            a = clamp(depth * 1.6) * clamp((1300 - y) / 200 + 0.2)
            spin = layer * 17 + p * 12
            major = layer % 2 == 0
            parts.append(f'<g transform="translate(960 {f1(y)})" opacity="{a:.3f}">'
                         f'<ellipse rx="{f1(rx)}" ry="{f1(ry)}" fill="{TEAL}" fill-opacity="0.05" stroke="{GOLD if major else TEAL}" stroke-width="{1.5 + 2 * depth:.2f}"/>'
                         f'<ellipse rx="{f1(rx * 0.82)}" ry="{f1(ry * 0.82)}" fill="none" stroke="{ICE}" stroke-width="1" stroke-dasharray="3 10" '
                         f'transform="rotate(0)" stroke-dashoffset="{f1(spin * 8)}"/>')
            for k in range(12):
                ang = math.radians(k * 30 + spin)
                x1, y1 = rx * 0.82 * math.cos(ang), ry * 0.82 * math.sin(ang)
                x2, y2 = rx * math.cos(ang), ry * math.sin(ang)
                parts.append(f'<line x1="{f1(x1)}" y1="{f1(y1)}" x2="{f1(x2)}" y2="{f1(y2)}" stroke="{TEAL}" stroke-width="1.5"/>')
            parts.append('</g>')
        # 主角与光尾
        hy = 470 + 12 * math.sin(p * math.pi)
        parts.append(f'<rect x="954" y="{f1(hy)}" width="12" height="520" fill="url(#softdot)" opacity="0.55"/>')
        parts.append(self.hero(960, hy, 10 + 5 * kick, 0.7 + 0.3 * kick))
        cap = (b - 104.4) / 3.0
        parts.append(f'<text x="960" y="930" font-family="{SERIF}" font-size="54" font-weight="700" fill="#fff" text-anchor="middle" '
                     f'letter-spacing="12" filter="url(#glow)">{esc(self.typewriter("叡智の階を、駆け上がれ", cap))}</text>')
        parts.append(f'<text x="960" y="980" font-family="{TECH}" font-size="18" fill="{AQUA}" text-anchor="middle" letter-spacing="9" '
                     f'opacity="{clamp((b - 107.5) / 1):.3f}">RUN UP THE STAIRS OF WISDOM</text>')
        return "".join(parts)

    # ---- 常驻 HUD（主段之后出现）
    def hud(self, i, b, kick):
        if b < DROP:
            return ""
        a = ease_out((b - DROP - 0.5) / 1.0)
        if b < 92:
            layer = 0
        elif b < 100:
            layer = 1 + int((b - 92) // 2)
        elif b < 104:
            layer = 4
        else:
            layer = 5 + int((b - 104) // 3)
        n, frac = math.floor(b), b - math.floor(b)
        pips = []
        for k in range(4):
            on = (n % 4) == k
            pips.append(f'<rect x="{1640 + k * 34}" y="62" width="20" height="20" transform="rotate(45 {1650 + k * 34} 72)" '
                        f'fill="{GOLD if on else "none"}" stroke="{GOLD}" stroke-width="1.5" opacity="{1 if on else 0.5}"/>')
        t = i / FPS
        return (f'<g opacity="{a:.3f}">'
                f'<text x="80" y="84" font-family="{TECH}" font-size="26" font-weight="700" fill="#fff" letter-spacing="6">LAYER {layer:02d}</text>'
                f'<rect x="80" y="98" width="{f1(180 * (1 - frac))}" height="3" fill="{TEAL}"/>'
                + "".join(pips) +
                f'<text x="1840" y="1030" font-family="{TECH}" font-size="16" fill="{AQUA}" text-anchor="end" letter-spacing="5" opacity="0.8">'
                f'{int(t // 60):02d}:{t % 60:05.2f} ◆ 185 BPM</text></g>')


def stage_html(fonts_dir):
    css = []
    for pkg, weights in [("noto-serif-jp", (500, 700, 900)), ("orbitron", (400, 700, 900)), ("zen-kaku-gothic-new", (500, 900))]:
        base = [d for d in os.listdir(fonts_dir) if d.startswith(f"fontsource-{pkg}-") and os.path.isdir(os.path.join(fonts_dir, d))][0]
        for w in weights:
            css.append(f'<link rel="stylesheet" href="file://{os.path.join(fonts_dir, base, "package", f"{w}.css")}">')
    warm = ("記憶の底で、光が瞬いたここは第零層。目を開け声を聴け層を越え昇れ躍れ叡の躍層まだ上へ咲け巡れ視よ跳べ智階駆がる"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:—◆\"Ø., abcdefghijklmnopqrstuvwxyz")
    probes = "".join(f'<span style="font-family:{fam};font-weight:{w}">{warm}</span>'
                     for fam, ws in [(SERIF, (500, 700, 900)), (TECH, (400, 700, 900)), (SANS, (500, 900))] for w in ws)
    return ('<!doctype html><html><head><meta charset="utf-8">' + "".join(css) +
            '<style>html,body{margin:0;background:#000;overflow:hidden}#warm{position:absolute;top:-9999px}</style></head>'
            f'<body><div id="s"></div><div id="warm">{probes}</div></body></html>')


class Renderer:
    def __init__(self, story, fonts_dir):
        self.story = story
        path = os.path.join(story.dir, ".story_stage.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(stage_html(fonts_dir))
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--font-render-hinting=none", "--force-color-profile=srgb",
                                                     "--allow-file-access-from-files"])
        self.page = self.browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        self.page.goto("file://" + path)
        self.page.evaluate("document.fonts.ready.then(() => true)")
        self.page.wait_for_timeout(300)

    def frame(self, i):
        self.page.evaluate("s => { document.getElementById('s').innerHTML = s; }", self.story.svg(i))
        return self.page.screenshot(type="jpeg", quality=100)

    def close(self):
        self.browser.close()
        self.pw.stop()


def worker(args, a, b, seg_path):
    story = Story(args.audio, args.features, args.cover)
    r = Renderer(story, args.fonts)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", seg_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    start = time.time()
    for i in range(a, b):
        proc.stdin.write(r.frame(i))
        done = i - a + 1
        if done % 150 == 0 or i == b - 1:
            print(f"[{os.path.basename(seg_path)}] {done}/{b - a} 帧，{done / (time.time() - start):.1f} 帧/秒", flush=True)
    r.close()
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg 失败")


def main():
    ap = argparse.ArgumentParser()
    for name in ("audio", "features", "cover", "fonts", "output"):
        ap.add_argument(name)
    ap.add_argument("--start", type=float, default=22.0)
    ap.add_argument("--end", type=float, default=37.0)
    ap.add_argument("--still", default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    args.fonts = os.path.abspath(args.fonts)

    if args.still:
        r = Renderer(Story(args.audio, args.features, args.cover), args.fonts)
        for s in args.still.split(","):
            i = round(float(s) * FPS)
            path = f"{os.path.splitext(args.output)[0]}_{float(s):06.2f}.jpg"
            with open(path, "wb") as f:
                f.write(r.frame(i))
            print(path)
        r.close()
        return

    a, b = round(args.start * FPS), round(args.end * FPS)
    work = os.path.splitext(args.output)[0] + "_segments"
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
        f.writelines(f"file '{os.path.abspath(s)}'\n" for s in segs)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    dur = (b - a) / FPS
    subprocess.run([ff, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing,
                    "-ss", f"{a / FPS:.4f}", "-t", f"{dur:.4f}", "-i", args.audio,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-af", f"afade=t=in:d=0.3,afade=t=out:st={dur - 0.5:.3f}:d=0.5",
                    "-movflags", "+faststart", "-shortest", args.output], check=True)
    print("输出:", args.output)


if __name__ == "__main__":
    main()
