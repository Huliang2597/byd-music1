#!/usr/bin/env python3
"""《Blooming Planet》叙事 PV 全曲版：沿用 refpv.py 确认过的参考特效谱风格，把整首（0:00–5:05）排满。

剧情（按歌词与段落强度）：
  前奏 黑场里一道光展开，标题浮现 → 静寂の中 目覚める（花苞在圆环里醒来）→ 花びらが舞う 夢の世界で（花瓣之梦）
  → 第一段高潮（线稿星球自转 / 雾中花影升起 / 随拍扩散的白环 / 冰霜植物与光带）→ 第二段主歌（星空 / 花瓣）
  → 回落（曼陀罗）→ 第二段高潮（线稿叶 / 灰雨）→ 全黑（路断了）→ 雾中前行，远处出现未知之门
  → 彼方へ広がる 未知の扉 / 新たな冒険の → 光的隧道冲刺 → 新しい世界へ / 花開く惑星（穿门，开满花的星球）
  → 花海与曼陀罗 → 未来へ舞い上がれ / 君となら、輝く（两朵花相会）/ 新しい世界へ / 花開く惑星
  → 全曲最强段 → 最后一段（refpv.py 的试片）→ 尾声：星徽、credits、logo。

用法: fullpv.py <fx目录> <音频> <歌词.lrc> <feat60.npz> <fonts目录> <输出.mp4> [--start 0 --end 305.6] [--still 秒,...]
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effectpv as E  # noqa: E402
import post as P  # noqa: E402
import refpv as R  # noqa: E402
from effectpv import CX, CY, H, W, clamp, ease_io, ease_out, lerp, n  # noqa: E402
from refpv import sine_io  # noqa: E402

PETAL = "M0 -12 C9 -10 12 6 0 12 C-12 6 -9 -10 0 -12 Z"

# 新场景：转场、运镜、字幕色、后期调色（沿用已有场景的调色）
R.TRANS.update({
    "bud": ("defocus", 1.4), "petals": ("bloom", 1.0), "planet": ("zoom", 0.8), "field": ("defocus", 0.8),
    "rings": ("dark", 0.8), "frost": ("bloom", 0.8), "navy2": ("drift", 1.0), "petals2": ("bloom", 1.0),
    "mandala2": ("defocus", 1.2), "line2": ("zoom", 0.8), "rain2": ("dark", 0.8), "dark": ("defocus", 1.4),
    "fog": ("defocus", 1.6), "doorfar": ("defocus", 1.2), "door": ("zoom", 1.2), "door2": ("zoom", 1.0),
    "rush": ("zoom", 0.8), "through": ("bloom", 1.0), "bloomfield": ("bloom", 0.8), "mandala3": ("zoom", 0.8),
    "ascend": ("drift", 0.8), "meet": ("defocus", 0.8), "door3": ("zoom", 0.8), "bplanet": ("bloom", 0.8),
    "climax1": ("zoom", 0.8), "climax2": ("bloom", 0.8), "warm": ("defocus", 1.0),
})
R.CAM.update({
    "void": (0, 0, 0, 0, 1.0, 1.04, 0, 0), "bud": (0, 10, 0, -10, 1.0, 1.06, 0, 0.3), "petals": (-30, 0, 30, 0, 1.02, 1.06, 0, 0),
    "planet": (0, 0, 0, 0, 1.0, 1.08, 0, 4), "field": (40, 0, -40, 0, 1.02, 1.06, 0, 0), "rings": (0, 0, 0, 0, 1.0, 1.1, 0, -3),
    "frost": (-30, 0, 30, 0, 1.03, 1.06, 0, 0), "navy2": (0, 30, 0, -20, 1.0, 1.06, 0, 0), "petals2": (30, 0, -30, 0, 1.02, 1.08, 0, 0.5),
    "mandala2": (0, 0, 0, 0, 1.0, 1.05, 0, 2), "line2": (40, 0, -40, 0, 1.02, 1.06, 0.3, -0.3), "rain2": (0, -20, 0, 10, 1.02, 1.07, -0.3, 0.2),
    "dark": (0, 0, 0, 0, 1.0, 1.04, 0, 0), "fog": (0, 0, 0, 0, 1.0, 1.1, 0, 0), "doorfar": (0, 0, 0, 0, 1.0, 1.08, 0, 0),
    "door": (0, 0, 0, 0, 1.0, 1.08, 0, 0), "door2": (0, 0, 0, 0, 1.0, 1.1, 0, 0), "rush": (0, 0, 0, 0, 1.0, 1.15, 0, 6),
    "through": (0, 0, 0, 0, 1.06, 1.0, 0, 0), "bloomfield": (-40, 0, 40, 0, 1.02, 1.08, 0, 0), "mandala3": (0, 0, 0, 0, 1.08, 1.0, 0, 3),
    "ascend": (0, -60, 0, 60, 1.02, 1.06, 0, 0), "meet": (0, 0, 0, 0, 1.0, 1.06, 0, 0), "door3": (0, 0, 0, 0, 1.0, 1.25, 0, 0),
    "bplanet": (0, 0, 0, 0, 1.0, 1.06, 0, 1), "climax1": (0, 0, 0, 0, 1.0, 1.12, 0, -5), "climax2": (0, 0, 0, 0, 1.02, 1.1, 0, 4),
    "teal": (0, 0, 0, 0, 1.0, 1.06, 0, 0),
})
R.SUB.update({"bud": "#e6ecf2", "petals": "#5a3a30", "navy2": "#e6eef8", "petals2": "#5a3a30", "door": "#eef4f4",
              "door2": "#eef4f4", "through": "#4a3a34", "ascend": "#eef2f8", "meet": "#e8e8e8", "door3": "#eef4f4",
              "bplanet": "#4a3a34"})
for key, base in {"void": "line", "bud": "gray", "petals": "warm", "planet": "navy", "field": "teal", "rings": "smoke",
                  "frost": "ice", "navy2": "navy", "petals2": "warm", "mandala2": "mandala", "line2": "line", "rain2": "gray",
                  "dark": "smoke", "fog": "teal", "doorfar": "teal", "door": "teal", "door2": "teal", "door3": "teal",
                  "rush": "navy", "through": "warm", "bloomfield": "warm", "mandala3": "mandala", "ascend": "navy",
                  "meet": "smoke", "bplanet": "warm", "climax1": "smoke", "climax2": "navy"}.items():
    P.GRADE[key] = P.GRADE[base]


class FullPV(R.RefPV):
    def __init__(self, fx, lrc, features):
        super().__init__(fx, lrc, features)
        lines = E.parse_lrc(lrc)
        self.subs = [(t, zh) for t, _, zh in lines]
        V1a, V1b, V2a, V2b, D1, D2, N1, N2, C1, C2, C3, C4 = (t for t, _, _ in lines[:12])
        q = self.q

        def bar(k):
            return self.phase + k * 16 * self.period / 4

        self.bar = bar
        self.t_c2b = q(C2, 4)  # 「輝く」：两朵花相碰
        self.t_n2 = N2
        early = [(0.0, "void"), (bar(16), "bud"), (bar(24), "petals"), (bar(32), "planet"), (bar(40), "field"),
                 (bar(48), "rings"), (bar(56), "frost"), (bar(64), "navy2"), (bar(72), "petals2"), (bar(80), "mandala2"),
                 (bar(88), "line2"), (bar(96), "rain2"), (bar(104), "dark"), (bar(112), "fog"), (bar(120), "doorfar"),
                 (bar(128), "door"), (bar(136), "door2"), (bar(144), "rush"), (bar(152), "through"), (bar(160), "bloomfield"),
                 (bar(168), "mandala3"), (bar(176), "ascend"), (C2, "meet"), (C3, "door3"), (C4, "bplanet"),
                 (bar(192), "climax1"), (bar(200), "climax2"), (bar(208), "warm")]
        self.scenes = early + [s for s in self.scenes if s[1] != "warm"]
        self.chunks = sorted(self.chunks + [
            (V1a, "静寂の中", 560, 360, 96, "white"), (q(V1a, 8), "目覚める", 1420, 640, 110, "white"),
            (V1b, "花びらが舞う", 880, 420, 92, "warm"), (q(V1b, 8), "夢の世界で", 1080, 590, 100, "warm"),
            (V2a, "静寂の中", 780, 420, 100, "white"), (q(V2a, 8), "目覚める", 1120, 600, 116, "white"),
            (V2b, "花びら舞う", 880, 420, 96, "warm"), (q(V2b, 8), "夢の世界で", 1080, 590, 104, "warm"),
            (D1, "彼方へ広がる", 520, 340, 88, "white"), (q(D1, 8), "未知の扉", 1420, 560, 108, "outline"),
            (D2, "新たな冒険の", 500, 340, 88, "white"), (q(D2, 8), "始まり求めて", 1420, 560, 96, "white"),
            (N1, "新しい世界へ", 960, 300, 96, "echo"), (N2, "花開く惑星", 960, 300, 116, "echo"),
            (C1, "未来へ", 800, 420, 110, "white"), (q(C1, 4), "舞い上がれ", 1100, 580, 110, "white"),
            (C2, "君となら", 760, 330, 100, "white"), (self.t_c2b, "輝く", 1180, 330, 150, "outline"),
            (C3, "新しい世界へ", 960, 330, 104, "echo"), (C4, "花開く惑星", 960, 300, 116, "echo")])
        rng = np.random.default_rng(33)
        self.pdata = rng.random((90, 8))
        self.warp = rng.random((120, 4))
        self.streams = rng.random((50, 4))
        self.last_end = 305.6

    # ---------- 字：句子最多停留 6 秒；字幕最多 9 秒 ----------
    def chunk_end(self, k):
        t0 = self.chunks[k][0]
        _, s0, s1 = self.scene(t0)
        nxt = [c[0] for c in self.chunks if s0 <= c[0] < s1 and c[0] > t0]
        return min([s1, t0 + 6.0] + nxt)

    def subtitle_for(self, t, name):
        if name == "teal":
            return ""
        out = []
        for k, (t0, zh) in enumerate(self.subs):
            t1 = min(self.subs[k + 1][0] if k + 1 < len(self.subs) else self.END, t0 + 9.0)
            a = sine_io((t - t0 + 0.2) / 0.6) * (1 - sine_io((t - t1 + 0.2) / 0.5))
            if a <= 0.003:
                continue
            out.append(f'<text x="{CX}" y="{n(H - E.BAR - 144 - 8 * a)}" text-anchor="middle" font-family="{E.HAND}" font-size="30" '
                       f'letter-spacing="2" fill="{R.SUB.get(name, "#e8e8e8")}" opacity="{0.9 * a:.3f}"'
                       f'{self.blur_filter(4 * (1 - a), None)}>{zh}</text>')
        return "".join(out)

    # ---------- 通用元素 ----------
    def petal_field(self, t, count, colors=("#fbe9ea", "#ffffff", "#f4d3da"), speed=1.0, up=False, op=1.0):
        out = []
        for m in range(count):
            d = self.pdata[m]
            depth = d[0]
            size = 6 + 22 * depth ** 1.5
            vx = (30 + 60 * depth) * speed
            vy = (40 + 70 * depth) * speed * (-1 if up else 1)
            x = (d[1] * (W + 400) + vx * t) % (W + 400) - 200 + 40 * math.sin(t * 0.8 + d[3] * 6)
            y = (d[2] * (H + 400) + vy * t) % (H + 400) - 200
            flip = max(0.15, abs(math.cos(t * (1.5 + 2 * d[6]) + d[7] * 6)))
            filt = ' filter="url(#fb3)"' if depth > 0.85 else (' filter="url(#fb1)"' if depth < 0.2 else "")
            out.append(f'<path d="{PETAL}" fill="{colors[m % len(colors)]}" opacity="{op * (0.35 + 0.55 * depth):.3f}"{filt} '
                       f'transform="translate({n(x)} {n(y)}) rotate({t * (40 + 90 * d[4]) + d[5] * 360:.1f}) '
                       f'scale({size / 12 * flip:.3f} {size / 12:.3f})"/>')
        return "".join(out)

    def star_dots(self, t, op=1.0):
        out = []
        for st in self.stars:
            a = op * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * (1 + 3 * st[3]) + st[2] * 20)))
            out.append(f'<circle cx="{n(st[0] * W)}" cy="{n(80 + st[1] * 800)}" r="{n(0.8 + 1.8 * st[2] ** 3)}" fill="#ffffff" opacity="{a:.3f}"/>')
        return "".join(out)

    def beat_rings(self, t, cx, cy, color="#ffffff", reach=760, strong=1.0):
        out = []
        b = self.beat(t)
        for kb in range(int(b) - 7, int(b) + 1):
            age = (b - kb) * self.period
            if age < 0 or age > 1.9:
                continue
            big = kb % 4 == 0
            k = age / 1.9
            r = 60 + reach * ease_out(k)
            out.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="none" stroke="{color}" '
                       f'stroke-width="{(3.0 if big else 1.4) * (1 - k) + 0.5:.2f}" opacity="{strong * (0.85 if big else 0.45) * (1 - k) ** 1.5:.3f}" '
                       f'filter="url(#gls)"/>')
        return "".join(out)

    def warp_lines(self, u, op=0.6, speed=1.0):
        out = []
        for d in self.warp:
            a = d[0] * 2 * math.pi
            r = (d[1] * 1100 + (300 + 600 * d[2]) * u * speed) % 1100 + 40
            L = 30 + r * 0.28
            c, s = math.cos(a), math.sin(a) * 0.8
            out.append(f'<line x1="{n(CX + r * c)}" y1="{n(CY + r * s)}" x2="{n(CX + (r + L) * c)}" y2="{n(CY + (r + L) * s)}" '
                       f'stroke="#ffffff" stroke-width="{1 + r / 700:.2f}" opacity="{op * min(1.0, r / 320):.3f}"/>')
        return "".join(out)

    def planet_svg(self, cx, cy, R0, t, flowers=0.0, color="#eef4ff", glow=1.0):
        p = self.pulse(t, 3)
        tilt = 18
        tau = math.radians(20)
        o = [f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R0 * 1.3)}" fill="url(#hWhite)" opacity="{glow * (0.12 + 0.06 * p):.3f}"/>',
             f'<g transform="rotate({-tilt} {n(cx)} {n(cy)})" fill="none" stroke="{color}" stroke-linecap="round">',
             f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R0)}" stroke-width="2.2" opacity="0.9" filter="url(#gls)"/>']
        for lat in (-60, -30, 0, 30, 60):
            la = math.radians(lat)
            o.append(f'<ellipse cx="{n(cx)}" cy="{n(cy - R0 * math.sin(la) * math.cos(tau))}" rx="{n(R0 * math.cos(la))}" '
                     f'ry="{n(R0 * math.cos(la) * math.sin(tau))}" stroke-width="1.1" opacity="0.45"/>')
        for k in range(6):
            lam = k * math.pi / 6 + t * 0.35
            o.append(f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n(R0 * abs(math.sin(lam)))}" ry="{n(R0)}" stroke-width="1.0" opacity="0.32"/>')
        o.append(f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n(R0 * 1.7)}" ry="{n(R0 * 0.38)}" stroke-width="1.4" opacity="0.55"/></g>')
        ca, sa = math.cos(math.radians(-tilt)), math.sin(math.radians(-tilt))
        for k in range(3):  # 轨道上的光点
            a = t * 0.8 + k * 2.1
            x, y = R0 * 1.7 * math.cos(a), R0 * 0.38 * math.sin(a)
            sx, sy = cx + x * ca - y * sa, cy + x * sa + y * ca
            o.append(f'<circle cx="{n(sx)}" cy="{n(sy)}" r="18" fill="url(#hWhite)" opacity="0.5"/><circle cx="{n(sx)}" cy="{n(sy)}" r="3.5" fill="#fff"/>')
        if flowers > 0:  # 星球边缘开出的白花
            for k in range(11):
                ang = math.radians(195 + k * 15)
                f = sine_io(flowers * 1.8 - k * 0.07)
                if f <= 0:
                    continue
                s = (90 + 70 * ((k * 37) % 5) / 4) * (0.3 + 0.7 * f)
                fx, fy = cx + R0 * 1.02 * math.cos(ang), cy + R0 * 1.02 * math.sin(ang)
                o.append(self.img("white_flower.png", fx - s / 2, fy - s / 2, s, s,
                                  f'opacity="{f:.3f}" transform="rotate({k * 33 + t * 6:.1f} {n(fx)} {n(fy)})"'))
        return "".join(o)

    def door_svg(self, cx, yb, s, glow=1.0, fill=0.0):
        w, h = 220 * s, 380 * s
        x0, x1, r = cx - w / 2, cx + w / 2, w / 2
        yt = yb - h
        path = f"M{n(x0)} {n(yb)} L{n(x0)} {n(yt + r)} A{n(r)} {n(r)} 0 0 1 {n(x1)} {n(yt + r)} L{n(x1)} {n(yb)} Z"
        k = 1.08
        path2 = (f"M{n(cx - w * k / 2)} {n(yb)} L{n(cx - w * k / 2)} {n(yb - h * k + r * k)} A{n(r * k)} {n(r * k)} 0 0 1 "
                 f"{n(cx + w * k / 2)} {n(yb - h * k + r * k)} L{n(cx + w * k / 2)} {n(yb)}")
        return (f'<ellipse cx="{n(cx)}" cy="{n(yb)}" rx="{n(w * 1.9)}" ry="{n(26 * s)}" fill="url(#hWhite)" opacity="{0.4 * glow:.3f}"/>'
                f'<circle cx="{n(cx)}" cy="{n(yb - h * 0.5)}" r="{n(h * 0.9)}" fill="url(#hWhite)" opacity="{0.22 * glow:.3f}"/>'
                f'<path d="{path}" fill="url(#hDoor)" opacity="{min(1.0, 0.75 * glow + fill):.3f}"/>'
                f'<path d="{path}" fill="#ffffff" opacity="{fill:.3f}"/>'
                f'<path d="{path}" fill="none" stroke="#ffffff" stroke-width="{n(1.4 + 1.2 * s ** 0.5)}" filter="url(#gls)"/>'
                f'<path d="{path2}" fill="none" stroke="#ffffff" stroke-width="1" opacity="0.5"/>')

    # ---------- 场景 ----------
    def sc_void(self, t, u):
        g = sine_io(u / 8)
        out = [f'<rect width="{W}" height="{H}" fill="#050608"/>', self.plate_img("navy.jpg", u, 0.02, 'opacity="0.35"'),
               f'<ellipse cx="{CX}" cy="{CY - 40}" rx="{n(40 + 900 * g)}" ry="1.6" fill="#ffffff" opacity="{0.25 + 0.45 * g:.3f}" filter="url(#bl3)"/>',
               f'<ellipse cx="{CX}" cy="{CY - 40}" rx="{n(20 + 520 * g)}" ry="30" fill="url(#hWhite)" opacity="{0.14 * g:.3f}"/>',
               self.motes(t, "#dfe8f0", 0.45 * sine_io(u / 4), 24, up=True, size=2.2)]
        ring = sine_io((u - 9.9) / 3.0)
        if ring > 0:
            out.append(self.arc(CX, CY - 40, 240 + 6 * self.pulse(t, 3), "#e8eef4", 0.55, 1.4, ring, -90, "gls"))
        a = sine_io((u - 12.0) / 1.8) * (1 - sine_io((u - 18.3) / 1.2))
        if a > 0.003:
            blur = self.blur_filter(7 * (1 - a), None)
            out.append(self.emblem(CX, CY - 40, 0.75, a))
            out.append(f'<g text-anchor="middle" opacity="{a:.3f}"{blur}>'
                       f'<text x="{CX}" y="{CY + 110}" font-family="{E.LOGO}" font-size="64" font-weight="500" fill="#f2f6f8" letter-spacing="6">'
                       f'Blooming Planet</text><text x="{CX}" y="{CY + 156}" font-family="{E.LOGO}" font-size="24" fill="#c9d3da" '
                       f'letter-spacing="4">Xyris / <tspan font-family="{E.SERIF}">花隈千冬</tspan></text></g>')
        return "".join(out), ""

    def sc_bud(self, t, u):
        cx, cy = 1000, 500
        g = sine_io(u / 9.0)
        s = 150 + 180 * g
        out = [self.plate_img("gray.jpg", u, 0.03), f'<rect width="{W}" height="{H}" fill="#0a0c10" opacity="0.45"/>',
               self.img("rays_top.png", -140, -60, 2200, 1300, f'opacity="{0.25 + 0.08 * math.sin(t * 1.3):.3f}" style="mix-blend-mode:screen"'),
               f'<circle cx="{cx}" cy="{cy}" r="{n(s * 0.9)}" fill="url(#hWhite)" opacity="{0.1 + 0.2 * g:.3f}"/>',
               self.img("white_flower.png", cx - s / 2, cy - s / 2, s, s,
                        f'opacity="{0.4 + 0.6 * sine_io(u / 2):.3f}" transform="rotate({-30 + 20 * g:.2f} {cx} {cy})"'),
               self.arc(cx, cy, 250 + 8 * self.pulse(t, 3), "#e8eef4", 0.55, 1.6, sine_io(u / 2.5), -90, "gls"),
               self.motes(t, "#e8eef4", 0.5, 30, up=True, size=2.5)]
        return "".join(out), ""

    def sc_petals(self, t, u, strong=False):
        out = [self.plate_img("warm.jpg", u, 0.04), f'<ellipse cx="1350" cy="220" rx="900" ry="520" fill="url(#hWarmLight)" opacity="0.35"/>']
        if strong:
            out.append(f'<g opacity="0.45">{self.mandala_svg(t, 1.0)}</g>')
        out.append(self.petal_field(t, 70 if strong else 50, speed=1.2 if strong else 1.0))
        return "".join(out), ""

    def sc_petals2(self, t, u):
        return self.sc_petals(t, u, True)

    def sc_planet(self, t, u):
        out = [self.plate_img("navy.jpg", u, 0.03), self.star_dots(t), self.planet_svg(CX, CY + 20, 300, t),
               self.beat_rings(t, CX, CY + 20, "#dfe8ff", 700, 0.5), self.motes(t, "#e6eeff", 0.5, 30, size=2.2)]
        return "".join(out), ""

    def sc_field(self, t, u):
        rise = 260 * (1 - sine_io(u / 3.0))
        p = self.pulse(t, 3)
        b1, _ = self.band(t, 560, 70, 46, "#1b2527", 0.45 + 0.1 * p, 0.45, 0.0)
        b2, _ = self.band(t, 600, 60, 30, "#2a3638", 0.35, 0.36, 2.1, 0.9)
        b3, _ = self.band(t, 540, 80, 18, "#e8f0f0", 0.12 + 0.1 * p, 0.5, 4.0, 1.3)
        out = [self.plate_img("teal.jpg", u, 0.03), b2, b1, b3,
               self.petal_field(t, 30, colors=("#eef6f6", "#dfeeee"), speed=0.7, up=True, op=0.8),
               self.img("fg_teal.png", -96 - 20 * u, H - 600 + rise, 2112, 620, 'opacity="0.9"')]
        return "".join(out), ""

    def sc_rings(self, t, u, strong=False):
        cx, cy = CX, CY
        s = 230
        out = [f'<rect width="{W}" height="{H}" fill="#040405"/>']
        if strong:
            out += [self.star_dots(t, 0.6), f'<g opacity="0.3">{self.mandala_svg(t, 1.1)}</g>']
        out.append('<g fill="none" stroke="#ffffff" stroke-linecap="round" filter="url(#gls)">')
        for k, P0 in enumerate(self.threads):
            sway = 14 * math.sin(t * 0.9 + k)
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = P0
            out.append(f'<path d="M{x0} {y0} C{n(x1 + sway)} {n(y1 - sway)} {n(x2 - sway)} {n(y2 + sway)} {x3} {y3}" '
                       f'stroke-width="{1.0 + 0.4 * (k % 3)}" opacity="{0.3 + 0.1 * (k % 3)}"/>')
        out.append('</g>')
        out += [self.beat_rings(t, cx, cy, "#ffffff", 820 if strong else 700, 1.0),
                f'<circle cx="{cx}" cy="{cy}" r="{n(s * 0.8)}" fill="url(#hWhite)" opacity="{0.18 + 0.1 * self.pulse(t):.3f}"/>',
                self.img("white_flower.png", cx - s / 2, cy - s / 2, s, s, f'transform="rotate({t * 12:.1f} {cx} {cy})"'),
                self.petal_field(t, 40 if strong else 26, colors=("#ffffff", "#e8e8e8"), speed=1.5, op=0.8)]
        return "".join(out), ""

    def sc_climax1(self, t, u):
        return self.sc_rings(t, u, True)

    def sc_frost(self, t, u):
        under, over = self.sc_ice(t, u)
        b = self.beat(t)
        streaks = []
        for kb in range(int(b) - 3, int(b) + 1):
            if kb % 2:
                continue
            age = (b - kb) * self.period
            y = 260 + ((kb * 97) % 420)
            x = -700 + 2800 * ease_io(age / 1.2)
            streaks.append(f'<ellipse cx="{n(x)}" cy="{y}" rx="620" ry="3" fill="#ffffff" opacity="{0.7 * (1 - clamp(age / 1.2)):.3f}" filter="url(#bl3)"/>')
        return under + "".join(streaks), over

    def sc_navy2(self, t, u):
        return self.sc_navy(t, u)

    def sc_mandala2(self, t, u):
        out = [self.plate_img("mauve.jpg", u), f'<g opacity="0.8">{self.mandala_svg(t * 0.5, 1.0)}</g>',
               f'<circle cx="{CX}" cy="{CY}" r="420" fill="url(#hWhite)" opacity="{0.16 + 0.05 * self.pulse(t, 2):.3f}"/>',
               self.motes(t, "#fff4f0", 0.5, 30, size=2.2)]
        return "".join(out), ""

    def sc_mandala3(self, t, u):
        under, over = self.sc_mandala(t, u, hold=0.2 + 0.55 * math.exp(-u / 2.5))
        return under + self.petal_field(t, 40, speed=1.4, op=0.8), over

    def sc_line2(self, t, u):
        return self.sc_line(t, u)

    def sc_rain2(self, t, u):
        return self.sc_gray(t, u)

    def sc_dark(self, t, u):
        v = sine_io(u / 7.0)
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = self.threads[1]
        py = -40 + 95 * u
        out = [f'<rect width="{W}" height="{H}" fill="#020203"/>',
               f'<path d="M{x0} {y0} C{x1} {y1} {x2} {y2} {x3} {y3}" fill="none" stroke="#ffffff" stroke-width="1.3" opacity="0.5" '
               f'pathLength="1" stroke-dasharray="{v:.4f} 2" filter="url(#gls)"/>',
               self.arc(CX, CY, 300, "#ffffff", 0.18 * (1 - sine_io((u - 6) / 3)), 1.0, 0.7, 120 + 3 * u),
               f'<path d="{PETAL}" fill="#eeeeee" opacity="0.85" filter="url(#gls)" transform="translate({n(960 + 60 * math.sin(u * 0.9))} {n(py)}) '
               f'rotate({u * 50:.1f}) scale({1.6 * max(0.2, abs(math.cos(u * 1.3))):.3f} 1.6)"/>',
               self.motes(t, "#ffffff", 0.25, 12, size=1.6)]
        return "".join(out), ""

    def fog_base(self, t, u, door=None):
        vx, vy = CX, 470
        out = [self.plate_img("teal.jpg", u, 0.03), f'<rect width="{W}" height="{H}" fill="#0b1112" opacity="0.35"/>',
               f'<circle cx="{vx}" cy="{vy}" r="{n(200 + 20 * self.pulse(t, 3))}" fill="url(#hWhite)" opacity="0.3"/>',
               '<g stroke="#ffffff" stroke-linecap="round" fill="none">']
        for k, bx in enumerate(np.linspace(-900, W + 900, 13)):  # 汇向远处的光线
            out.append(f'<line x1="{n(bx)}" y1="{H + 60}" x2="{vx}" y2="{vy}" stroke-width="1.2" opacity="0.22" '
                       f'stroke-dasharray="46 70" stroke-dashoffset="{n(t * 180 + k * 13)}"/>')
        out.append('</g>')
        for d in self.dots[:40]:  # 迎面飘来的尘
            r = ((d[0] + u * (0.05 + 0.08 * d[1])) % 1.0) ** 2 * 1300
            a = d[2] * 2 * math.pi
            out.append(f'<circle cx="{n(vx + r * math.cos(a))}" cy="{n(vy + r * math.sin(a) * 0.7)}" r="{n(0.8 + r / 400)}" fill="#eef6f6" '
                       f'opacity="{0.6 * min(1.0, r / 200):.3f}"/>')
        if door:
            out.append(self.door_svg(vx, vy + 190 * door[0], door[0], door[1], door[2]))
        return "".join(out)

    def sc_fog(self, t, u):
        return self.fog_base(t, u), ""

    def sc_doorfar(self, t, u):
        a = sine_io(u / 4)
        return self.fog_base(t, u, (0.22 + 0.12 * sine_io(u / 9.8), 0.6 * a, 0.0)), ""

    def sc_door(self, t, u):
        return self.fog_base(t, u, (0.42 + 0.3 * sine_io(u / 9.8), 0.9, 0.0)), ""

    def sc_door2(self, t, u):
        b1, _ = self.band(t, 760, 40, 30, "#e8f0f0", 0.14, 0.6, 1.0, 1.1)
        return self.fog_base(t, u, (0.78 + 0.35 * sine_io(u / 9.8), 1.0, 0.0)) + b1, ""

    def sc_door3(self, t, u):
        k = sine_io(u / 5.0)
        return self.fog_base(t, u, (1.15 + 2.2 * k, 1.0, 0.6 * k)), ""

    def sc_rush(self, t, u):
        g = sine_io(u / 9.8)
        out = [self.plate_img("navy.jpg", u, 0.03), f'<rect width="{W}" height="{H}" fill="#05070c" opacity="0.4"/>',
               self.warp_lines(u, 0.4 + 0.4 * g, 1.0 + g), self.beat_rings(t, CX, CY, "#e8f0ff", 760, 0.7),
               f'<circle cx="{CX}" cy="{CY}" r="{n(150 + 500 * g)}" fill="url(#hWhite)" opacity="{0.25 + 0.5 * g:.3f}"/>']
        return "".join(out), ""

    def sc_through(self, t, u):
        f = sine_io((t - self.t_n2) / 2.8)
        white = 1 - sine_io(u / 2.2)
        out = [self.plate_img("warm.jpg", u, 0.03), f'<rect width="{W}" height="{H}" fill="#3a2a22" opacity="0.18"/>',
               self.planet_svg(CX, CY + 90, 250, t, f, color="#6b4f44", glow=0.8),
               self.petal_field(t, 30, speed=0.8, op=0.8)]
        over = f'<rect width="{W}" height="{H}" fill="#ffffff" opacity="{0.9 * white:.3f}"/>' if white > 0.003 else ""
        return "".join(out), over

    def sc_bloomfield(self, t, u):
        b = self.beat(t) - self.beat(self.span_start("bloomfield"))
        out = [self.plate_img("warm.jpg", u, 0.04), f'<rect width="{W}" height="{H}" fill="#3a2a22" opacity="0.15"/>']
        b1, _ = self.band(t, 620, 60, 26, "#ffffff", 0.18, 0.5, 1.0)
        out.append(b1)
        for k in range(9):  # 地平线上的花一拍一朵开出来
            f = sine_io((b - k * 2) / 1.5)
            if f <= 0:
                continue
            x = 120 + k * 210 + 30 * math.sin(k * 2.3)
            s = (200 + 120 * ((k * 53) % 7) / 6) * (0.35 + 0.65 * f)
            y = H - 230 - 60 * ((k * 31) % 3)
            out.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(s * 0.7)}" fill="url(#hWhite)" opacity="{0.25 * f:.3f}"/>')
            out.append(self.img("white_flower.png", x - s / 2, y - s / 2, s, s, f'opacity="{f:.3f}" transform="rotate({k * 40 + t * 8:.1f} {n(x)} {n(y)})"'))
        out.append(self.petal_field(t, 80, speed=1.4))
        return "".join(out), f'<ellipse cx="1350" cy="200" rx="900" ry="520" fill="url(#hWarmLight)" opacity="0.3"/>'

    def sc_ascend(self, t, u):
        out = [self.plate_img("navy.jpg", u, 0.03), self.star_dots(t, 0.8)]
        for d in self.streams:  # 往上冲的光流
            y = (d[1] * (H + 400) - (700 + 900 * d[2]) * u) % (H + 400) - 200
            L = 80 + 160 * d[3]
            out.append(f'<line x1="{n(d[0] * W)}" y1="{n(y)}" x2="{n(d[0] * W)}" y2="{n(y + L)}" stroke="#eef4ff" '
                       f'stroke-width="{1 + 2 * d[3]:.2f}" opacity="{0.25 + 0.45 * d[2]:.3f}" filter="url(#gls)"/>')
        out.append(self.petal_field(t, 50, speed=2.2, up=True, op=0.9))
        out.append(f'<ellipse cx="{CX}" cy="-60" rx="1000" ry="380" fill="url(#hWhite)" opacity="0.35"/>')
        return "".join(out), ""

    def sc_meet(self, t, u):
        """君となら、輝く：两朵白花在圆环里慢慢靠近，「輝く」时相碰、亮起来"""
        k = sine_io(u / (self.t_c2b - self.span_start("meet") + 0.2))
        tb = t - self.t_c2b
        glow = math.exp(-max(0.0, tb) / 0.9) if tb >= 0 else 0.0
        (ax, ay), (bx, by) = (lerp(820, 905, k), lerp(520, 505, k)), (lerp(1110, 1020, k), lerp(500, 490, k))
        s = 230
        out = [f'<rect width="{W}" height="{H}" fill="#040406"/>', self.star_dots(t, 0.5),
               self.arc(CX, CY - 20, 300, "#f2f2f2", 0.8, 2.4, sine_io(u / 1.2), -90, "gls"),
               f'<g fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" filter="url(#gls)">'
               f'<path d="M640 1200 Q760 820 {n(ax + 10)} {n(ay + 60)}"/><path d="M1300 1200 Q1180 820 {n(bx - 10)} {n(by + 60)}"/></g>',
               self.img("white_flower.png", ax - s / 2, ay - s / 2, s, s, f'transform="rotate({20 + 10 * k:.1f} {n(ax)} {n(ay)})"'),
               self.img("white_flower.png", bx - s / 2, by - s / 2, s, s, f'transform="rotate({-40 - 10 * k:.1f} {n(bx)} {n(by)})"')]
        if tb >= 0:
            out.append(f'<circle cx="{n((ax + bx) / 2)}" cy="{n((ay + by) / 2)}" r="{n(200 + 500 * (1 - glow))}" fill="url(#hWhite)" '
                       f'opacity="{0.25 + 0.45 * glow:.3f}"/>')
            out.append(self.beat_rings(t, (ax + bx) / 2, (ay + by) / 2, "#ffffff", 700, 0.6))
        return "".join(out), ""

    def sc_bplanet(self, t, u, strong=False):
        out = [self.plate_img("warm.jpg", u, 0.03), f'<rect width="{W}" height="{H}" fill="#3a2a22" opacity="0.2"/>',
               self.planet_svg(CX, CY + 40, 280, t, sine_io(u / 2.2) if not strong else 1.0, color="#6b4f44", glow=0.8),
               self.petal_field(t, 60 if strong else 40, speed=1.3 if strong else 0.9)]
        return "".join(out), ""

    def sc_climax2(self, t, u):
        out = [self.plate_img("navy.jpg", u, 0.03), self.star_dots(t), self.warp_lines(u, 0.35, 1.2),
               self.planet_svg(CX, CY + 20, 290, t, 1.0), self.beat_rings(t, CX, CY + 20, "#e8f0ff", 800, 0.8),
               self.petal_field(t, 40, colors=("#ffffff", "#e8eeff"), speed=1.6, op=0.8)]
        return "".join(out), ""

    def sc_teal(self, t, u):
        """尾声（4:37–5:05）：星徽沿丝带滑进来 → credits → logo → 随音乐淡出"""
        under = [self.plate_img("teal.jpg", u, 0.03)]
        b1, (xs, yc) = self.band(t, 560, 70, 46, "#1b2527", 0.5, 0.35, 0.0)
        b2, _ = self.band(t, 600, 60, 30, "#2a3638", 0.4, 0.28, 2.1, 0.9)
        b3, _ = self.band(t, 540, 80, 18, "#e8f0f0", 0.12, 0.4, 4.0, 1.3)
        under += [b2, b1, b3, self.img("fg_teal.png", -96 - 10 * u, H - 600, 2112, 620, 'opacity="0.9"')]
        ex = lerp(-120, 700, ease_io(u / 3.0))
        ey = float(np.interp(ex, xs, yc))
        logo = sine_io((u - 11.0) / 1.8)
        cred = sine_io((u - 2.8) / 1.2) * (1 - sine_io((u - 9.6) / 1.0))
        if logo > 0:
            ex, ey = lerp(ex, 862, logo), lerp(ey, 600, logo)
        over = [self.emblem(ex, ey, 1.0 - 0.15 * logo, ease_out(u / 0.8))]
        if cred > 0.003:
            over.append(f'<g font-family="{E.LOGO}" fill="#f2f6f6" opacity="{cred:.3f}"{self.blur_filter(5 * (1 - cred), "sh")}>'
                        f'<text x="300" y="250" font-size="44" font-weight="500">Music</text>'
                        f'<line x1="290" y1="268" x2="520" y2="268" stroke="#f2f6f6" stroke-width="1" opacity="0.6"/>'
                        f'<text x="300" y="306" font-size="24">Xyris / <tspan font-family="{E.SERIF}">花隈千冬</tspan></text>'
                        f'<text x="1620" y="250" font-size="44" font-weight="500" text-anchor="end">Album</text>'
                        f'<line x1="1400" y1="268" x2="1630" y2="268" stroke="#f2f6f6" stroke-width="1" opacity="0.6"/>'
                        f'<text x="1620" y="306" font-size="24" text-anchor="end">ARTIFACTS:ASCENSIØN</text>'
                        f'<text x="1620" y="340" font-size="20" text-anchor="end" opacity="0.8">fan-made narrative PV</text></g>')
        if logo > 0:
            sw = sine_io((u - 11.8) / 1.6)
            over.append(f'<g font-family="{E.LOGO}" font-weight="500" fill="#f6fafa"{self.blur_filter(8 * (1 - logo), "gl")} opacity="{logo:.3f}">'
                        f'<text x="860" y="545" font-size="92" letter-spacing="-1">Blooming</text>'
                        f'<text x="930" y="628" font-size="104" letter-spacing="-1">Planet</text></g>')
            if sw > 0:
                over.append(f'<path d="M1080 520 C1180 470 1230 400 1150 380 C1060 360 950 420 900 430 M1150 380 C1230 380 1270 470 1230 560 '
                            f'C1205 610 1160 628 1130 610" fill="none" stroke="#f6fafa" stroke-width="2.4" stroke-linecap="round" '
                            f'pathLength="1" stroke-dasharray="{sw:.4f} 2" filter="url(#gls)" opacity="{logo:.3f}"/>')
                for fx, fy in ((1040, 405), (1105, 440)):
                    k = sine_io((u - 12.6) / 0.8)
                    over.append(f'<g transform="translate({fx} {fy}) scale({k:.3f})" fill="none" stroke="#f6fafa" stroke-width="1.2" opacity="0.8">' +
                                "".join(f'<ellipse cx="0" cy="-7" rx="3.5" ry="7" transform="rotate({a})"/>' for a in range(0, 360, 72)) + '</g>')
        fade = sine_io((u - 19.0) / 3.5)  # 音乐在 4:56 左右结束
        if fade > 0:
            over.append(f'<rect x="-200" y="-200" width="{W + 400}" height="{H + 400}" fill="#000" opacity="{fade:.3f}"/>')
        return "".join(under), "".join(over)

    DEFS = R.RefPV.DEFS.replace('</defs>', (
        '<radialGradient id="hDoor" cx="0.5" cy="0.6" r="0.65"><stop offset="0" stop-color="#ffffff" stop-opacity="1"/>'
        '<stop offset="0.7" stop-color="#f2fafa" stop-opacity="0.85"/><stop offset="1" stop-color="#dff0f0" stop-opacity="0.5"/></radialGradient>'
        '</defs>'))

    def warm(self):
        return super().warm() + "BloomingPlanetXyris/花隈千冬"


if __name__ == "__main__":
    E.EffectPV = FullPV
    if "--start" not in sys.argv:
        sys.argv += ["--start", "0"]
    if "--end" not in sys.argv:
        sys.argv += ["--end", "305.6"]
    E.main()
