#!/usr/bin/env python3
"""逐帧生成 SVG → 无头 Chromium 渲染 → ffmpeg 编码为 1080p60 视频。

用法:
  render.py <音频> <features.npz> <cover.png> <输出.mp4> [--workers N] [--frames A:B] [--still 帧号,...]
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
import soundfile as sf

W, H = 1920, 1080
CX, CY = 960, 470
FPS = 60

TITLE = "叡の躍層"
ARTIST = "Link\"0"
ALBUM = "ARTIFACTS:ASCENSIØN"
FONT = "WenQuanYi Zen Hei"

# 配色取自封面：深海军蓝、青绿、湖蓝、白、星盘金
NAVY = (5, 18, 32)
DEEP = (8, 42, 56)
TEAL = (47, 214, 195)
AQUA = (120, 232, 226)
BLUE = (86, 170, 238)
GOLD = (236, 200, 128)
WHITE = (255, 255, 255)


def rgb(c):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def f1(x):
    return f"{x:.1f}"


def ease_out(x):
    return 1 - (1 - x) ** 3


class Scene:
    def __init__(self, audio_path, features_path, cover_path):
        d = np.load(features_path)
        self.n = int(d["n_frames"])
        self.spec = d["spectrum"]
        self.kick = d["kick"]
        self.kicks = d["kicks"]
        self.bass = d["bass"]
        self.loud = d["loud"]
        self.intensity = d["intensity"]
        self.period = float(d["beat_period"])
        self.phase = float(d["beat_phase"])
        self.cover_dir = os.path.dirname(os.path.abspath(cover_path))
        self.cover_name = os.path.basename(cover_path)
        audio, self.sr = sf.read(audio_path, dtype="float32", always_2d=True)
        self.mono = audio.mean(axis=1)
        self.duration = len(self.mono) / self.sr
        # 粒子上升的累计位移：强度越高越快
        self.travel = np.cumsum(0.35 + 1.9 * self.intensity ** 1.5) / FPS
        # 平滑后的强度，用于颜色与整体亮度
        k = np.ones(90) / 90
        self.glow = np.convolve(np.pad(self.intensity, 45, mode="edge"), k, mode="same")[45:-45]
        rng = np.random.default_rng(20231029)
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.6, 2.2), rng.uniform(0, 6.28), rng.uniform(0.4, 1.6))
                      for _ in range(170)]
        self.sparkles = [(rng.uniform(80, W - 80), rng.uniform(60, H - 220), rng.uniform(9, 22), rng.uniform(0, 6.28), rng.uniform(0.3, 1))
                         for _ in range(16)]
        self.particles = [(rng.uniform(0, W), rng.uniform(0, 1), rng.uniform(0.5, 1.6), rng.uniform(2, 7), rng.uniform(0, 6.28),
                           rng.integers(0, 3)) for _ in range(150)]

    # ------------------------------------------------------------------ helpers

    def beat(self, i):
        """返回 (拍号, 拍内进度 0..1)。"""
        b = (i - self.phase) / self.period
        return math.floor(b), b - math.floor(b)

    def stepped_angle(self, i, per_beat, drift):
        """每拍转动 per_beat 度（缓出），再加缓慢漂移。"""
        n, frac = self.beat(i)
        return n * per_beat + ease_out(min(1.0, frac * 2.2)) * per_beat + drift * i / FPS

    # ------------------------------------------------------------------ frame

    def svg(self, i):
        t = i / FPS
        it = float(self.intensity[i])
        glow = float(self.glow[i])
        kick = float(self.kick[i])
        bass = float(self.bass[i])
        fade_in = min(1.0, t / 2.5)
        fade_out = min(1.0, max(0.0, (self.duration - t) / 3.0))
        master = fade_in * fade_out
        draw_in = ease_out(min(1.0, t / 5.0))  # 前奏里星盘逐渐画出
        accent = mix(TEAL, AQUA, glow)

        # 强段落鼓点带轻微镜头震动
        shake = kick * it * 7
        sx = shake * math.sin(i * 12.9898) if it > 0.6 else 0
        sy = shake * math.cos(i * 78.233) if it > 0.6 else 0
        zoom = 1 + 0.012 * kick * it

        out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
        out.append(self.defs(i, glow, bass))
        out.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
        out.append(f'<rect width="{W}" height="{H}" fill="url(#halo)" opacity="{0.35 + 0.55 * bass * (0.4 + 0.6 * it):.3f}"/>')
        out.append(f'<g transform="translate({f1(sx)} {f1(sy)}) translate({CX} {CY}) scale({zoom:.4f}) translate({-CX} {-CY})">')
        out.append(self.stars_layer(i, t, kick))
        out.append(self.floor(i, t, it))
        out.append(self.waveform(i, it, accent))
        out.append(self.particles_layer(i, t, it, accent))
        out.append(self.shockwaves(i))
        out.append(self.astrolabe(i, t, it, kick, draw_in, accent))
        out.append(self.spectrum_ring(i, accent))
        out.append(self.cover(i, kick))
        out.append('</g>')
        out.append(self.hud(i, t, accent))
        if it > 0.55 and kick > 0.5:
            out.append(f'<rect width="{W}" height="{H}" fill="#e8fffb" opacity="{0.10 * (kick - 0.5) * 2 * it:.3f}"/>')
        if master < 1:
            out.append(f'<rect width="{W}" height="{H}" fill="#000" opacity="{1 - master:.3f}"/>')
        out.append('</svg>')
        return "".join(out)

    def defs(self, i, glow, bass):
        top = mix(NAVY, (6, 30, 46), glow)
        bottom = mix(DEEP, (10, 70, 78), glow)
        return (
            '<defs>'
            f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{rgb(top)}"/>'
            f'<stop offset="1" stop-color="{rgb(bottom)}"/></linearGradient>'
            f'<radialGradient id="halo" cx="{CX}" cy="{CY}" r="760" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{rgb(mix(TEAL, AQUA, bass))}" stop-opacity="0.55"/>'
            f'<stop offset="0.35" stop-color="{rgb(BLUE)}" stop-opacity="0.18"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="dot"><stop offset="0" stop-color="#fff"/><stop offset="0.35" stop-color="#bff7f0" stop-opacity="0.7"/>'
            '<stop offset="1" stop-color="#6fe3d8" stop-opacity="0"/></radialGradient>'
            f'<clipPath id="coverclip"><circle cx="{CX}" cy="{CY}" r="190"/></clipPath>'
            f'<path id="orbit" d="M {CX - 404} {CY} a 404 404 0 1 1 808 0 a 404 404 0 1 1 -808 0"/>'
            '<linearGradient id="fadeL" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            '<linearGradient id="prog" x1="0" x2="1"><stop offset="0" stop-color="#2fd6c3"/><stop offset="1" stop-color="#8fd0ff"/></linearGradient>'
            '</defs>'
        )

    def stars_layer(self, i, t, kick):
        parts = ['<g>']
        for x, y, r, ph, sp in self.stars:
            a = 0.25 + 0.45 * (0.5 + 0.5 * math.sin(t * sp * 2 + ph)) + 0.3 * kick
            parts.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{r:.2f}" fill="#dffcff" opacity="{min(1, a):.2f}"/>')
        # 封面里的四角星
        for x, y, s, ph, sp in self.sparkles:
            tw = 0.5 + 0.5 * math.sin(t * sp * 2.4 + ph)
            size = s * (0.6 + 0.5 * tw + 0.4 * kick)
            rot = (t * 20 * sp + ph * 57) % 360
            parts.append(f'<g transform="translate({f1(x)} {f1(y)}) rotate({f1(rot)}) scale({size / 10:.3f})" opacity="{0.35 + 0.6 * tw:.2f}">'
                         '<path d="M0 -10 Q1.4 -1.4 10 0 Q1.4 1.4 0 10 Q-1.4 1.4 -10 0 Q-1.4 -1.4 0 -10Z" fill="#e9fffb"/></g>')
        parts.append('</g>')
        return "".join(parts)

    def floor(self, i, t, it):
        """透视网格地面：随拍子向前滚动。"""
        horizon = 760
        n, frac = self.beat(i)
        parts = [f'<g opacity="{0.10 + 0.28 * it:.3f}" stroke="#5fe0d4" fill="none">']
        for k in range(12):
            z = (k + frac) / 12
            y = horizon + (H - horizon) * z ** 2.2
            parts.append(f'<line x1="0" y1="{f1(y)}" x2="{W}" y2="{f1(y)}" stroke-width="{0.6 + 1.6 * z:.2f}" opacity="{z:.2f}"/>')
        for k in range(-14, 15):
            x2 = CX + k * 190
            parts.append(f'<line x1="{CX + k * 14}" y1="{horizon}" x2="{x2}" y2="{H}" stroke-width="1"/>')
        parts.append('</g>')
        return "".join(parts)

    def waveform(self, i, it, accent):
        """穿过画面中心的示波器波形（被中央圆盘遮住中间一段）。"""
        c = int(i * self.sr / FPS)
        n = 2048
        seg = self.mono[max(0, c - n // 2):c + n // 2]
        if len(seg) < n:
            seg = np.pad(seg, (0, n - len(seg)))
        pts = 240
        idx = np.linspace(0, n - 1, pts).astype(int)
        ys = CY + np.clip(seg[idx] * (55 + 95 * it), -210, 210)
        xs = np.linspace(0, W, pts)
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
        col = rgb(accent)
        return (f'<g fill="none" stroke-linejoin="round">'
                f'<path d="{d}" stroke="{col}" stroke-width="9" opacity="{0.10 + 0.12 * it:.3f}"/>'
                f'<path d="{d}" stroke="#e8fffb" stroke-width="2" opacity="{0.45 + 0.4 * it:.3f}"/></g>')

    def particles_layer(self, i, t, it, accent):
        travel = float(self.travel[i])
        parts = ['<g>']
        span = H + 80
        for x0, y0, speed, size, ph, kind in self.particles:
            y = H + 40 - ((y0 * span + travel * 120 * speed) % span)
            x = x0 + 26 * math.sin(t * 0.8 * speed + ph)
            life = 1 - abs((H + 40 - y) / span - 0.5) * 2  # 中段最亮
            a = (0.25 + 0.55 * it) * (0.35 + 0.65 * life)
            if kind == 0:
                parts.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{size * 2.2:.1f}" fill="url(#dot)" opacity="{a:.2f}"/>')
            elif kind == 1:
                s = size * 0.9
                rot = (t * 60 * speed + ph * 57) % 360
                parts.append(f'<rect x="{f1(-s)}" y="{f1(-s)}" width="{f1(2 * s)}" height="{f1(2 * s)}" fill="none" stroke="{rgb(accent)}" '
                             f'stroke-width="1.4" opacity="{a:.2f}" transform="translate({f1(x)} {f1(y)}) rotate({f1(rot)})"/>')
            else:
                # 花瓣
                rot = (t * 40 * speed + ph * 57) % 360
                s = size * 1.3
                parts.append(f'<ellipse rx="{f1(s)}" ry="{f1(s * 0.45)}" fill="#bfeefa" opacity="{a * 0.8:.2f}" '
                             f'transform="translate({f1(x)} {f1(y)}) rotate({f1(rot)})"/>')
        parts.append('</g>')
        return "".join(parts)

    def shockwaves(self, i):
        parts = ['<g fill="none">']
        recent = self.kicks[(self.kicks <= i) & (self.kicks > i - 50)]
        for k in recent:
            p = (i - k) / 50
            r = 200 + 620 * ease_out(p)
            a = (1 - p) ** 2 * (0.3 + 0.7 * float(self.intensity[k]))
            parts.append(f'<circle cx="{CX}" cy="{CY}" r="{f1(r)}" stroke="#bff7f0" stroke-width="{f1(1 + 5 * (1 - p))}" opacity="{a:.3f}"/>')
        parts.append('</g>')
        return "".join(parts)

    def astrolabe(self, i, t, it, kick, draw_in, accent):
        parts = []
        a1 = self.stepped_angle(i, 3.0, 2.0)
        a2 = -self.stepped_angle(i, 1.5, 3.5)
        a3 = self.stepped_angle(i, 0.75, -1.2)
        col = rgb(accent)
        gold = rgb(GOLD)
        # 金色八角星（封面星盘）
        star_r = 330 + 18 * kick
        pts = []
        for k in range(16):
            ang = math.radians(k * 22.5 + a3)
            r = star_r if k % 2 == 0 else star_r * (0.34 if k % 4 == 1 else 0.3)
            if k % 4 == 2:
                r = star_r * 0.62
            pts.append(f"{CX + r * math.cos(ang):.1f},{CY + r * math.sin(ang):.1f}")
        parts.append(f'<polygon points="{" ".join(pts)}" fill="{gold}" fill-opacity="{0.05 + 0.07 * it:.3f}" stroke="{gold}" '
                     f'stroke-opacity="{(0.35 + 0.4 * it) * draw_in:.3f}" stroke-width="1.5"/>')
        # 刻度环
        ticks = []
        n_ticks = int(120 * draw_in)
        for k in range(n_ticks):
            ang = math.radians(k * 3 + a1)
            long_tick = k % 10 == 0
            r1 = 352
            r2 = 372 if long_tick else 362
            c, s = math.cos(ang), math.sin(ang)
            ticks.append(f'M{CX + r1 * c:.1f} {CY + r1 * s:.1f}L{CX + r2 * c:.1f} {CY + r2 * s:.1f}')
        parts.append(f'<path d="{"".join(ticks)}" stroke="{col}" stroke-width="2" opacity="{0.55 + 0.35 * it:.2f}"/>')
        circ = 2 * math.pi * 380
        parts.append(f'<circle cx="{CX}" cy="{CY}" r="380" fill="none" stroke="{col}" stroke-width="1.5" opacity="0.7" '
                     f'stroke-dasharray="{circ * draw_in:.1f} {circ:.1f}" transform="rotate({f1(a2 - 90)} {CX} {CY})"/>')
        # 虚线环
        parts.append(f'<circle cx="{CX}" cy="{CY}" r="428" fill="none" stroke="#dffcff" stroke-width="3" opacity="{(0.25 + 0.35 * it) * draw_in:.2f}" '
                     f'stroke-dasharray="4 18" transform="rotate({f1(a2 * 1.7)} {CX} {CY})"/>')
        # 三段弧
        for k in range(3):
            start = a1 * 1.3 + k * 120
            parts.append(self.arc(CX, CY, 446, start, start + 70 + 30 * it, "#8fd0ff", 4, (0.3 + 0.5 * it) * draw_in))
        # 沿轨道的文字
        text = f"{ALBUM}  ✦  {TITLE}  ✦  {ARTIST}  ✦  "
        parts.append(f'<g transform="rotate({f1(-a1 * 0.5)} {CX} {CY})" opacity="{(0.35 + 0.3 * it) * draw_in:.2f}">'
                     f'<text font-family="{FONT}" font-size="15" letter-spacing="3" fill="#dffcff">'
                     f'<textPath xlink:href="#orbit" textLength="{2 * math.pi * 404 - 20:.0f}" lengthAdjust="spacing">{esc(text * 3)}</textPath></text></g>')
        # 拍点指示：四个方位的小菱形，在拍上亮起
        _, frac = self.beat(i)
        pulse = 1 - ease_out(min(1, frac * 1.5))
        for k in range(4):
            ang = math.radians(k * 90 - 90)
            x, y = CX + 404 * math.cos(ang), CY + 404 * math.sin(ang)
            s = 7 + 6 * pulse
            parts.append(f'<rect x="{f1(-s)}" y="{f1(-s)}" width="{f1(2 * s)}" height="{f1(2 * s)}" fill="{gold}" '
                         f'opacity="{(0.4 + 0.6 * pulse) * draw_in:.2f}" transform="translate({f1(x)} {f1(y)}) rotate(45)"/>')
        return "".join(parts)

    @staticmethod
    def arc(cx, cy, r, a0, a1, color, width, opacity):
        x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
        x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
        large = 1 if (a1 - a0) % 360 > 180 else 0
        return (f'<path d="M{x0:.1f} {y0:.1f}A{r} {r} 0 {large} 1 {x1:.1f} {y1:.1f}" fill="none" stroke="{color}" '
                f'stroke-width="{width}" stroke-linecap="round" opacity="{opacity:.2f}"/>')

    def spectrum_ring(self, i, accent):
        spec = self.spec[i]
        n = len(spec)
        bars = []
        r0 = 206
        total = n * 2
        for k in range(total):
            # 左右对称：低频在上方，高频在下方
            b = k if k < n else total - 1 - k
            v = float(spec[b]) ** 1.4
            length = 6 + 125 * v
            ang = math.radians(-90 + (k + 0.5) * 360 / total)
            c, s = math.cos(ang), math.sin(ang)
            color = rgb(mix(mix(TEAL, BLUE, b / n), WHITE, v * 0.8))
            bars.append(f'<line x1="{CX + r0 * c:.1f}" y1="{CY + r0 * s:.1f}" x2="{CX + (r0 + length) * c:.1f}" '
                        f'y2="{CY + (r0 + length) * s:.1f}" stroke="{color}" opacity="{0.55 + 0.45 * v:.2f}"/>')
        return f'<g stroke-width="5.5" stroke-linecap="round">{"".join(bars)}</g>'

    def cover(self, i, kick):
        s = 1 + 0.045 * kick
        return (f'<g transform="translate({CX} {CY}) scale({s:.4f}) translate({-CX} {-CY})">'
                f'<circle cx="{CX}" cy="{CY}" r="199" fill="#061423"/>'
                f'<image xlink:href="{self.cover_name}" x="{CX - 190}" y="{CY - 190}" width="380" height="380" clip-path="url(#coverclip)" '
                'preserveAspectRatio="xMidYMid slice"/>'
                f'<circle cx="{CX}" cy="{CY}" r="194" fill="none" stroke="#e9fffb" stroke-width="5"/>'
                f'<circle cx="{CX}" cy="{CY}" r="200" fill="none" stroke="#2fd6c3" stroke-width="2" opacity="0.8"/></g>')

    def hud(self, i, t, accent):
        dur = self.duration
        p = min(1.0, t / dur)
        x0, x1, y = 120, W - 120, 1012
        cur = f"{int(t // 60):02d}:{int(t % 60):02d}"
        total = f"{int(dur // 60):02d}:{int(dur % 60):02d}"
        head = x0 + (x1 - x0) * p
        appear = ease_out(min(1.0, max(0.0, (t - 1.0) / 2.0)))
        dy = 30 * (1 - appear)
        return (f'<g opacity="{appear:.3f}" transform="translate(0 {f1(dy)})" font-family="{FONT}">'
                f'<text x="{x0}" y="952" font-size="54" fill="#ffffff" letter-spacing="4">{esc(TITLE)}</text>'
                f'<text x="{x0 + 262}" y="952" font-size="26" fill="{rgb(accent)}" letter-spacing="2">{esc(ARTIST)}</text>'
                f'<text x="{x1}" y="952" font-size="20" fill="#bfeefa" text-anchor="end" letter-spacing="6" opacity="0.85">{esc(ALBUM)}</text>'
                f'<rect x="{x0}" y="{y - 1.5}" width="{x1 - x0}" height="3" rx="1.5" fill="#ffffff" opacity="0.18"/>'
                f'<rect x="{x0}" y="{y - 1.5}" width="{f1(head - x0)}" height="3" rx="1.5" fill="url(#prog)"/>'
                f'<circle cx="{f1(head)}" cy="{y}" r="10" fill="#8ff0e6" opacity="0.25"/>'
                f'<circle cx="{f1(head)}" cy="{y}" r="4.5" fill="#ffffff"/>'
                f'<text x="{x0}" y="{y + 36}" font-size="20" fill="#dffcff" opacity="0.8" letter-spacing="2">{cur}</text>'
                f'<text x="{x1}" y="{y + 36}" font-size="20" fill="#dffcff" opacity="0.8" text-anchor="end" letter-spacing="2">{total}</text>'
                '</g>')


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


STAGE = ('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#000;overflow:hidden}'
         '</style></head><body><div id="s"></div></body></html>')


class Renderer:
    """在无头 Chromium 里渲染 SVG，返回 JPEG 截图。"""

    def __init__(self, scene):
        self.scene = scene
        stage = os.path.join(scene.cover_dir, ".stage.html")
        with open(stage, "w", encoding="utf-8") as f:
            f.write(STAGE)
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--font-render-hinting=none", "--force-color-profile=srgb"])
        self.page = self.browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        self.page.goto("file://" + stage)

    def frame(self, i):
        self.page.evaluate("s => { document.getElementById('s').innerHTML = s; }", self.scene.svg(i))
        return self.page.screenshot(type="jpeg", quality=100)

    def close(self):
        self.browser.close()
        self.pw.stop()


def worker(args, a, b, seg_path):
    scene = Scene(args.audio, args.features, args.cover)
    renderer = Renderer(scene)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-x264-params", "keyint=120:min-keyint=120", seg_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    start = time.time()
    for i in range(a, b):
        proc.stdin.write(renderer.frame(i))
        done = i - a + 1
        if done % 300 == 0 or i == b - 1:
            rate = done / max(time.time() - start, 1e-6)
            print(f"[{os.path.basename(seg_path)}] {done}/{b - a} 帧，{rate:.1f} 帧/秒", flush=True)
    renderer.close()
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg 失败: {seg_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("features")
    ap.add_argument("cover")
    ap.add_argument("output")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--frames", default=None, help="A:B 只渲染这一段")
    ap.add_argument("--still", default=None, help="逗号分隔的帧号，输出 PNG 预览")
    args = ap.parse_args()

    if args.still:
        renderer = Renderer(Scene(args.audio, args.features, args.cover))
        for s in args.still.split(","):
            i = int(s)
            path = f"{os.path.splitext(args.output)[0]}_{i:05d}.jpg"
            with open(path, "wb") as f:
                f.write(renderer.frame(i))
            print(path)
        renderer.close()
        return

    n = int(np.load(args.features)["n_frames"])
    a, b = (0, n) if not args.frames else map(int, args.frames.split(":"))
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
    print(f"渲染完成，用时 {(time.time() - t0) / 60:.1f} 分钟")

    listing = os.path.join(work, "list.txt")
    with open(listing, "w") as f:
        for s in segs:
            f.write(f"file '{os.path.abspath(s)}'\n")
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    start = a / FPS
    cmd = [ff, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing,
           "-ss", f"{start:.4f}", "-t", f"{(b - a) / FPS:.4f}", "-i", args.audio,
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
           "-movflags", "+faststart", "-shortest",
           "-metadata", f"title={TITLE}", "-metadata", f"artist={ARTIST}", "-metadata", f"album={ALBUM}", args.output]
    subprocess.run(cmd, check=True)
    print("输出:", args.output)


if __name__ == "__main__":
    main()
