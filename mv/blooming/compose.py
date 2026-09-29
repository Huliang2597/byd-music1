#!/usr/bin/env python3
"""把 Blender 渲出的三渲二画面与 2D 叠加层（日语歌词、转场、特效）合成为视频。

用法:
  compose.py <帧目录> <音频> <歌词.lrc> <features.npz> <fonts目录> <输出.mp4> --start 秒 --end 秒 [--fps 24] [--still 秒,...]
"""
import argparse
import math
import os
import re
import subprocess
import sys
import time

import imageio_ffmpeg
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from story import SERIF, TECH, stage_html  # noqa: E402

W, H = 1920, 1080
T_LINE1, T_LINE2, T_LINE3, T_LINE4 = 218.21, 222.83, 228.19, 232.86
T_MEET = 226.30
T_THROUGH = 232.60
CUTS = [T_LINE2, T_LINE3]  # 硬切（加白闪）


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rnd(k, salt=0):
    x = math.sin(k * 12.9898 + salt * 78.233) * 43758.5453
    return x - math.floor(x)


def parse_lrc(path):
    lines = []
    for raw in open(path, encoding="utf-8"):
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", raw.strip())
        if not m:
            continue
        text = re.sub(r"\s*[（(]翻译[：:].*[)）]\s*$", "", m.group(3)).strip()
        lines.append((int(m.group(1)) * 60 + float(m.group(2)), text))
    lines.sort()
    return [(t, lines[i + 1][0] if i + 1 < len(lines) else t + 5, s) for i, (t, s) in enumerate(lines)]


class Overlay:
    def __init__(self, frames_dir, lrc, features, fps, step=1, first=0):
        self.frames_dir = os.path.abspath(frames_dir)
        self.step, self.first = step, first  # step=2：3D 画面一拍二，叠加层仍逐帧
        self.lines = parse_lrc(lrc)
        self.fps = fps
        d = np.load(features)
        self.kick = d["kick"]

    def svg(self, i):
        t = i / self.fps
        kick = float(self.kick[min(i, len(self.kick) - 1)])
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
               '<defs>'
               '<radialGradient id="vig" cx="0.5" cy="0.5" r="0.72"><stop offset="0.6" stop-color="#000" stop-opacity="0"/>'
               '<stop offset="1" stop-color="#021018" stop-opacity="0.55"/></radialGradient>'
               '<radialGradient id="bloom"><stop offset="0" stop-color="#fff" stop-opacity="0.95"/>'
               '<stop offset="0.3" stop-color="#d8fff8" stop-opacity="0.5"/><stop offset="1" stop-color="#8ff0e6" stop-opacity="0"/></radialGradient>'
               '<filter id="soft" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>'
               '</defs>',
               f'<image href="file://{self.frames_dir}/{self.first + (i - self.first) // self.step * self.step:06d}.png" width="{W}" height="{H}"/>']
        out.append(self.speed_lines(t))
        out.append(self.sparkles(t, kick))
        # 两颗光相会
        if T_MEET - 0.1 < t < T_MEET + 1.4:
            p = (t - T_MEET + 0.1) / 1.5
            r = 120 + 1400 * ease_out(p)
            out.append(f'<circle cx="960" cy="470" r="{r:.1f}" fill="url(#bloom)" opacity="{(1 - p) ** 1.5:.3f}"/>')
        out.append(f'<rect width="{W}" height="{H}" fill="url(#vig)"/>')
        out.append(self.lyrics(t))
        # 转场白闪
        white = 0.0
        for c in CUTS:
            if c - 0.04 <= t < c + 0.35:
                white = max(white, 0.85 * (1 - (t - c) / 0.35))
        if T_THROUGH - 0.5 <= t < T_LINE4 + 0.7:
            if t < T_LINE4:
                white = max(white, clamp((t - (T_THROUGH - 0.5)) / 0.5))
            else:
                white = max(white, 1 - ease_out((t - T_LINE4) / 0.7))
        if white > 0:
            out.append(f'<rect width="{W}" height="{H}" fill="#f4fffd" opacity="{white:.3f}"/>')
        out.append('</svg>')
        return "".join(out)

    def speed_lines(self, t):
        if not (T_LINE1 + 0.3 < t < T_LINE2):
            return ""
        a = clamp((t - T_LINE1 - 0.3) / 0.6) * clamp((T_LINE2 - t) / 0.5)
        parts = [f'<g opacity="{0.55 * a:.3f}" stroke="#effffc" stroke-linecap="round">']
        for k in range(46):
            ang = rnd(k, 1) * 2 * math.pi
            ph = (t * 2.4 + rnd(k, 2)) % 1
            r1 = 380 + 900 * ph
            r2 = r1 + 90 + 260 * ph
            c, s = math.cos(ang), math.sin(ang)
            parts.append(f'<line x1="{960 + r1 * c:.1f}" y1="{540 + r1 * s:.1f}" x2="{960 + r2 * c:.1f}" y2="{540 + r2 * s:.1f}" '
                         f'stroke-width="{1 + 3 * ph:.2f}" opacity="{ph:.2f}"/>')
        parts.append('</g>')
        return "".join(parts)

    def sparkles(self, t, kick):
        parts = []
        for k in range(14):
            x = 120 + rnd(k, 5) * 1680
            y = 80 + rnd(k, 6) * 820
            tw = 0.5 + 0.5 * math.sin(t * (1.5 + rnd(k, 7) * 2) + k)
            a = (0.25 + 0.5 * tw) * (0.4 + 0.6 * kick)
            s = (6 + 10 * rnd(k, 8)) * (0.7 + 0.5 * tw + 0.4 * kick)
            parts.append(f'<g transform="translate({x:.1f} {y:.1f}) rotate({(t * 30 + k * 40) % 360:.1f}) scale({s / 10:.3f})" opacity="{a:.3f}">'
                         '<path d="M0 -10 Q1.2 -1.2 10 0 Q1.2 1.2 0 10 Q-1.2 1.2 -10 0 Q-1.2 -1.2 0 -10Z" fill="#fff"/></g>')
        return "".join(parts)

    def lyrics(self, t):
        cur = [(s, e, text) for s, e, text in self.lines if s - 0.05 <= t < e]
        if not cur:
            return ""
        start, end, text = cur[-1]
        end = min(end, start + 4.6)
        title = text == "花開く惑星"
        fade = 1 - clamp((t - (end - 0.35)) / 0.35)
        if fade <= 0:
            return ""
        chars = list(text)
        step = 0.07 if not title else 0.12
        if title:
            size, y = 118, 470
        else:
            size, y = 62, 930
        spacing = size * 1.08
        total = spacing * len(chars)
        x0 = 960 - total / 2 + spacing / 2
        parts = [f'<g opacity="{fade:.3f}" font-family="{SERIF}" font-weight="700" text-anchor="middle">']
        # 歌词底下的细线装饰
        if not title:
            lw = ease_out((t - start) / 0.5) * (total / 2 + 60)
            parts.append(f'<line x1="{960 - lw:.1f}" y1="{y + 30}" x2="{960 + lw:.1f}" y2="{y + 30}" stroke="#bff7f0" stroke-width="1.5" opacity="0.8"/>'
                         f'<text x="{960 - lw - 18:.1f}" y="{y + 36}" font-size="18" fill="#bff7f0">✿</text>'
                         f'<text x="{960 + lw + 18:.1f}" y="{y + 36}" font-size="18" fill="#bff7f0">✿</text>')
        for k, ch in enumerate(chars):
            p = (t - start - k * step) / 0.35
            if p <= 0:
                continue
            a = ease_out(p)
            dy = (1 - a) * 22
            x = x0 + k * spacing
            parts.append(f'<g transform="translate({x:.1f} {y + dy:.1f})" opacity="{a:.3f}">'
                         f'<text font-size="{size}" fill="#0b3a44" opacity="0.55" filter="url(#soft)">{esc(ch)}</text>'
                         f'<text font-size="{size}" fill="#ffffff" stroke="#1d6f78" stroke-width="{size * 0.08:.1f}" paint-order="stroke">{esc(ch)}</text></g>')
        if title:
            sub = ease_out((t - start - 0.9) / 0.6)
            parts.append(f'<g opacity="{sub:.3f}" font-weight="400">'
                         f'<rect x="560" y="{y + 36}" width="800" height="104" rx="52" fill="#06303a" opacity="0.45" filter="url(#soft)"/>'
                         f'<text x="960" y="{y + 80}" font-family="{TECH}" font-size="34" font-weight="700" fill="#ffffff" letter-spacing="16" '
                         f'stroke="#1d6f78" stroke-width="5" paint-order="stroke">BLOOMING PLANET</text>'
                         f'<text x="960" y="{y + 124}" font-family="{SERIF}" font-size="26" fill="#ffffff" letter-spacing="8" '
                         f'stroke="#1d6f78" stroke-width="4" paint-order="stroke">Xyris / 花隈千冬</text></g>')
        parts.append('</g>')
        return "".join(parts)


class Renderer:
    def __init__(self, overlay, fonts_dir, workdir):
        self.overlay = overlay
        warm = "".join(sorted({c for _, _, s in overlay.lines for c in s})) + "花隈千冬✿"
        path = os.path.join(workdir, ".compose_stage.html")
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
            const img = el.querySelector('image');
            if (!img) return res(true);
            const probe = new Image(); probe.onload = probe.onerror = () => requestAnimationFrame(() => res(true));
            probe.src = img.getAttribute('href');
        })""", self.overlay.svg(i))
        return self.page.screenshot(type="jpeg", quality=100)

    def close(self):
        self.browser.close()
        self.pw.stop()


def main():
    ap = argparse.ArgumentParser()
    for name in ("frames", "audio", "lrc", "features", "fonts", "output"):
        ap.add_argument(name)
    ap.add_argument("--start", type=float, default=217.0)
    ap.add_argument("--end", type=float, default=237.5)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--still", default=None)
    ap.add_argument("--step", type=int, default=1, help="3D 画面隔帧（2 = 一拍二）")
    args = ap.parse_args()
    ov = Overlay(args.frames, args.lrc, args.features, args.fps, args.step, round(args.start * args.fps))
    workdir = os.path.dirname(os.path.abspath(args.output))
    r = Renderer(ov, os.path.abspath(args.fonts), workdir)
    if args.still:
        for s in args.still.split(","):
            i = round(float(s) * args.fps)
            path = f"{os.path.splitext(args.output)[0]}_{float(s):07.2f}.jpg"
            with open(path, "wb") as f:
                f.write(r.frame(i))
            print(path)
        r.close()
        return
    a, b = round(args.start * args.fps), round(args.end * args.fps)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    dur = (b - a) / args.fps
    cmd = [ff, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(args.fps), "-c:v", "mjpeg", "-i", "-",
           "-ss", f"{a / args.fps:.4f}", "-t", f"{dur:.4f}", "-i", args.audio,
           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "320k", "-af", f"afade=t=in:d=0.3,afade=t=out:st={dur - 0.6:.3f}:d=0.6",
           "-movflags", "+faststart", "-shortest", args.output]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(a, b):
        proc.stdin.write(r.frame(i))
        if (i - a) % 120 == 0:
            print(f"{i - a + 1}/{b - a} 帧，{(i - a + 1) / (time.time() - t0):.1f} 帧/秒", flush=True)
    r.close()
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg 失败")
    print("输出:", args.output)


if __name__ == "__main__":
    main()
