#!/usr/bin/env python3
"""《Blooming Planet》叙事 PV · 照参考特效谱逐镜复刻（不含方块路和光球）。

参考画面的共同点：大面积雾与过曝柔光、低对比、构图很空；细线圆环、白色细丝、深色半透明丝带；
花草是发光/虚化的剪影或烟雾；字不大，带柔光，「満開の瞬間」有左右残影；底部小号手写翻译。
素材由 reftex.py 生成，时间轴/字幕/渲染流程沿用 effectpv.py，最后过 post.py。

用法: refpv.py <fx目录> <音频> <歌词.lrc> <feat60.npz> <fonts目录> <输出.mp4> [--still 秒,...]
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effectpv as E  # noqa: E402
import post as P  # noqa: E402
from effectpv import BAR, CX, CY, H, W, clamp, ease_io, ease_out, lerp, n  # noqa: E402

# 字的样式：颜色 / 描边 / 滤镜 / 不透明度
TEXT = {
    "warm": dict(fill="#7a3a2c", op=0.62, filt=None),
    "white": dict(fill="#f6f8fa", op=0.92, filt="gl"),
    "echo": dict(fill="#5e4040", op=0.72, filt=None),
    "outline": dict(fill="none", stroke="#ffffff", sw=2.4, op=0.95, filt="gl"),
    "gray": dict(fill="#555555", op=0.9, filt=None),
}
# 每一幕的匀速运镜：起止平移 (dx, dy)、缩放、旋转（度）
CAM = {"warm": (20, 0, -30, -10, 1.0, 1.06, 0, 0.4), "gray": (0, -20, 0, 10, 1.02, 1.07, -0.3, 0.2),
       "smoke": (0, 0, 0, 0, 1.0, 1.05, 0, -0.6), "mandala": (0, 0, 0, 0, 1.08, 1.0, 0, 1.2),
       "ice": (-30, 0, 30, 0, 1.03, 1.06, 0, 0), "navy": (0, 30, 0, -20, 1.0, 1.06, 0, 0),
       "line": (40, 0, -40, 0, 1.02, 1.06, 0.3, -0.3), "score": (-20, 10, 20, -10, 1.0, 1.05, 0, 0),
       "teal": (0, 0, 0, 0, 1.0, 1.04, 0, 0)}


def sine_io(x):
    x = clamp(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


SUB = {"warm": "#fff6ea", "gray": "#eef1f4", "smoke": "#e8e8e8", "mandala": "#4a3434", "ice": "#2f3d48",
       "navy": "#e6eef8", "line": "#e8e8e8", "score": "#333333", "teal": "#e8f0f0"}

P.GRADE.update({
    "warm": dict(th=0.55, bloom=0.9, halo=(1.0, 0.85, 0.7), grain=0.02, lift=(0.03, 0.02, 0.01), gain=(1.0, 0.97, 0.92)),
    "gray": dict(th=0.5, bloom=0.6, halo=(0.95, 0.97, 1.0), grain=0.022, lift=(0.02, 0.02, 0.025), gain=(0.98, 0.99, 1.0)),
    "smoke": dict(th=0.75, bloom=0.55, halo=(1.0, 1.0, 1.0), grain=0.02, lift=(0.0, 0.0, 0.0), gain=(1.0, 1.0, 1.0)),
    "mandala": dict(th=0.6, bloom=0.95, halo=(1.0, 0.9, 0.88), grain=0.02, lift=(0.02, 0.01, 0.01), gain=(1.0, 0.98, 0.97)),
    "ice": dict(th=0.6, bloom=0.8, halo=(0.85, 0.93, 1.0), grain=0.018, lift=(0.0, 0.01, 0.02), gain=(0.98, 1.0, 1.02)),
    "navy": dict(th=0.45, bloom=1.0, halo=(0.8, 0.9, 1.0), grain=0.02, lift=(0.0, 0.005, 0.015), gain=(1.0, 1.0, 1.02)),
    "line": dict(th=0.5, bloom=0.8, halo=(1.0, 1.0, 1.0), grain=0.02, lift=(0.01, 0.01, 0.012), gain=(1.0, 1.0, 1.0)),
    "score": dict(th=0.9, bloom=0.2, halo=(1.0, 1.0, 1.0), grain=0.015, lift=(0.0, 0.0, 0.0), gain=(1.0, 1.0, 1.0)),
    "teal": dict(th=0.62, bloom=0.7, halo=(0.9, 1.0, 1.0), grain=0.02, lift=(0.01, 0.015, 0.015), gain=(0.98, 1.0, 1.0)),
})


class RefPV(E.EffectPV):
    def __init__(self, fx, lrc, features):
        super().__init__(fx, lrc, features)
        L1, L2, L3, L4 = (t for t, _ in self.subs)
        q = self.q
        s_rain, s_bloom, s_score = q(L1, 6), q(L2, 8), q(L4, 8)
        self.t_smile = q(L3, 8)
        self.t_snap = q(L2, 4)  # 「花で」：心之花被折断
        self.scenes = [(-1e9, "warm"), (s_rain, "gray"), (L2, "smoke"), (s_bloom, "mandala"), (L3, "ice"),
                       (self.t_smile, "navy"), (L4, "line"), (s_score, "score"), (self.END, "teal")]
        # (出现时刻, 文字, x, y, 字号, 样式)
        self.chunks = [(L1, "泣き虫の", 800, 440, 128, "warm"),
                       (s_rain, "雨が", 900, 470, 84, "white"), (q(L1, 10), "降る", 1060, 560, 84, "white"),
                       (L2, "心の", 680, 380, 70, "white"), (q(L2, 4), "花で", 1420, 800, 70, "white"),
                       (s_bloom, "満開の瞬間", 960, 560, 104, "echo"),
                       (L3, "遠い", 760, 420, 88, "outline"), (q(L3, 4), "星", 990, 520, 200, "outline"),
                       (q(L3, 6), "が", 1170, 640, 88, "outline"),
                       (self.t_smile, "微", 1060, 470, 104, "white"), (q(L3, 10), "笑む", 1190, 600, 88, "white"),
                       (L4, "寄り", 800, 430, 84, "white"), (q(L4, 2), "添う", 1030, 470, 110, "white"),
                       (q(L4, 5), "愛", 1190, 640, 120, "white"),
                       (s_score, "永遠の歌", 900, 470, 84, "gray")]
        rng = np.random.default_rng(21)
        self.dots = rng.random((70, 6))
        self.stars = rng.random((90, 4))
        self.threads = [((-100, 1150), (500, 760), (900, 700), (2050, 330)), ((-50, 1180), (600, 820), (1050, 640), (2000, 520)),
                        ((200, 1200), (700, 850), (1100, 560), (1500, -60)), ((-80, 1000), (400, 900), (800, 620), (1250, 380)),
                        ((300, 1220), (820, 900), (1000, 700), (1800, -40))]
        self.lineleaves = [(420, 330, -0.4, 230), (560, 520, 0.5, 170), (1320, 430, -2.6, 210), (1510, 610, 2.4, 190),
                           (760, 760, 0.9, 150), (1180, 250, -1.2, 160), (260, 700, -0.1, 140), (1650, 330, 3.0, 150)]

    # ---------- 通用 ----------
    def arc(self, cx, cy, r, color, op, width=2.0, frac=1.0, rot=-90, filt=None):
        f = f' filter="url(#{filt})"' if filt else ""
        return (f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{op:.3f}" '
                f'pathLength="1" stroke-dasharray="{frac:.4f} 2" transform="rotate({rot:.1f} {n(cx)} {n(cy)})"{f}/>')

    def motes(self, t, color, op, count=40, up=True, size=3.0):
        out = []
        for d in self.dots[:count]:
            x = (d[0] * (W + 200) + (18 + 30 * d[1]) * t * (1 if up else 0.3)) % (W + 200) - 100
            y = (d[2] * (H + 200) + (-1 if up else 1) * (20 + 40 * d[3]) * t) % (H + 200) - 100
            a = op * (0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * (1.5 + 2 * d[4]) + d[5] * 9)))
            r = 0.8 + size * d[4] ** 2
            out.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r * 3)}" fill="url(#hDot)" opacity="{a * 0.6:.3f}"/>'
                       f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}" fill="{color}" opacity="{a:.3f}"/>')
        return "".join(out)

    def band(self, t, y0, amp, thick, color, op, speed, phase, wl=1.1):
        xs = np.linspace(-60, W + 60, 56)
        ph = t * speed + phase
        yc = y0 + amp * np.sin(xs / W * 2 * math.pi * wl + ph) + amp * 0.3 * np.sin(xs / W * 2 * math.pi * 2.1 - ph * 1.3)
        th = thick * (0.55 + 0.45 * np.sin(xs / W * 2 * math.pi * 0.8 + ph * 0.6 + phase))
        top = " L".join(f"{n(x)} {n(y)}" for x, y in zip(xs, yc - th / 2))
        bot = " L".join(f"{n(x)} {n(y)}" for x, y in zip(xs[::-1], (yc + th / 2)[::-1]))
        return f'<path d="M{top} L{bot} Z" fill="{color}" opacity="{op:.3f}"/>', (xs, yc)

    def plate_img(self, name, u, drift=0.04, extra=""):
        s = 1 + drift * ease_io(u / 6)
        return self.img(name, -96, -54, 2112, 1188, f'transform="translate(960 540) scale({s:.4f}) translate(-960 -540)" {extra}')

    # ---------- 场景（返回 字下层, 字上层） ----------
    def sc_warm(self, t, u):
        under = [self.plate_img("warm.jpg", u), self.arc(870, 470, 300, "#6b4030", 0.5, 2.2, 0.62, 110 + 6 * u),
                 self.motes(t, "#ffe2b0", 0.9, 46)]
        p = self.pulse(t, 4)
        over = [f'<ellipse cx="1420" cy="190" rx="900" ry="540" fill="url(#hWarmLight)" opacity="{0.72 + 0.1 * p:.3f}"/>',
                f'<ellipse cx="900" cy="235" rx="1250" ry="16" fill="#fffaf2" opacity="0.75" filter="url(#bl8)"/>',
                f'<ellipse cx="900" cy="235" rx="1150" ry="70" fill="#fff4e4" opacity="0.28" filter="url(#bl20)"/>',
                f'<rect x="{W - 520}" y="0" width="520" height="{H}" fill="url(#leakR)" opacity="0.5"/>']
        return "".join(under), "".join(over)

    def sc_gray(self, t, u):
        under = [self.plate_img("gray.jpg", u),
                 self.img("rays_top.png", -140, -60, 2200, 1300,
                          f'opacity="{0.55 + 0.15 * math.sin(t * 1.7):.3f}" style="mix-blend-mode:screen" '
                          f'transform="rotate({1.5 * math.sin(t * 0.6):.2f} 960 -300)"'),
                 self.arc(1150, 440, 38, "#f0f2f4", 0.8, 1.6), self.arc(960, 520, 320, "#e6e9ec", 0.18, 1.2)]
        d = []
        for r in self.rain[:120]:
            speed, length = 1500 + 700 * r[1], 40 + 60 * r[2]
            y = (r[3] * 1400 + speed * t) % 1400 - 160
            x = r[0] * (W + 300) - 150 - 0.12 * y
            d.append(f"M{n(x)} {n(y)} l{n(0.12 * length)} {n(-length)}")
        under.append(f'<path d="{"".join(d)}" stroke="#dfe3e7" stroke-width="1" opacity="0.18"/>')
        under.append(self.motes(t, "#e8ecf0", 0.5, 20, up=False, size=2))
        over = [f'<ellipse cx="960" cy="-80" rx="900" ry="420" fill="url(#hWhite)" opacity="0.35"/>']
        return "".join(under), "".join(over)

    def sc_smoke(self, t, u):
        """心の花で：细长花茎上的一朵白花，唱到「花で」时茎折断、花头垂落"""
        rx, ry = 1060, 460  # 圆环中心 = 花原本的位置
        bx, by = 1150, 540  # 折断点
        hx, hy = 1070, 395  # 花头
        g = sine_io(u / 1.1)
        tau = t - self.t_snap
        if tau < 0:
            th, fall = 2.0 * math.sin(t * 1.3), 0.0
        else:  # 断开后带回弹地垂下去
            th = -136 * (1 - math.exp(-4.2 * tau) * math.cos(9.5 * tau))
            fall = clamp(-th / 136)

        def rot(px, py):
            a = math.radians(th)
            return (bx + (px - bx) * math.cos(a) - (py - by) * math.sin(a),
                    by + (px - bx) * math.sin(a) + (py - by) * math.cos(a))
        under = [f'<rect width="{W}" height="{H}" fill="#040405"/>',
                 '<g fill="none" stroke="#ffffff" stroke-linecap="round" filter="url(#gls)">']
        for k, P0 in enumerate(self.threads):
            v = sine_io((u - 0.1 * k) / 1.5)
            sway = 10 * math.sin(t * 0.9 + k)
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = P0
            under.append(f'<path d="M{x0} {y0} C{n(x1 + sway)} {n(y1 - sway)} {n(x2 - sway)} {n(y2 + sway)} {x3} {y3}" '
                         f'stroke-width="{1.0 + 0.4 * (k % 3)}" opacity="{0.35 + 0.1 * (k % 3)}" pathLength="1" stroke-dasharray="{v:.4f} 2"/>')
        sv = sine_io(u / 1.1)
        under.append(f'<path d="M1330 1200 Q1210 860 {bx} {by}" stroke-width="3.4" opacity="0.95" pathLength="1" stroke-dasharray="{sv:.4f} 2"/>')
        if tau >= 0:  # 断口的毛刺
            under.append(f'<path d="M{bx} {by} l-7 -14 M{bx} {by} l6 -12 M{bx} {by} l1 -17" stroke-width="1.6" opacity="0.9"/>')
        under.append('</g>')
        under.append(self.arc(rx, ry, 300 * (1 + 0.015 * self.pulse(t)), "#f2f2f2", 0.9, 3.0, sine_io(u / 1.2), -90, "gls"))
        s = 380 * (0.7 + 0.3 * g)
        sq = 1 - 0.38 * fall  # 垂下去时花面转向下方，看起来被压扁
        under.append(f'<g transform="rotate({th:.2f} {bx} {by})" opacity="{g:.3f}">'
                     f'<path d="M{bx} {by} Q{bx - 14} {by - 90} {hx + 16} {hy + 55}" fill="none" stroke="#ffffff" stroke-width="3.4" '
                     f'stroke-linecap="round" filter="url(#gls)"/>'
                     f'<circle cx="{hx}" cy="{hy}" r="{n(s * 0.6)}" fill="url(#hWhite)" opacity="0.2"/>'
                     f'<g transform="translate({hx} {hy}) scale(1 {sq:.3f}) translate({-hx} {-hy})">' +
                     self.img("white_flower.png", hx - s / 2, hy - s / 2, s, s, f'transform="rotate({-12 + 4 * u:.2f} {hx} {hy})"') + '</g></g>')
        if tau >= 0:
            k = ease_out(tau / 0.35)
            under.append(f'<circle cx="{bx}" cy="{by}" r="{n(10 + 80 * k)}" fill="url(#hWhite)" opacity="{0.9 * (1 - k):.3f}"/>')
            for j, pp in enumerate(self.leave_petals[:9]):  # 从花头上掉下来的花瓣
                t_rel = self.t_snap + 0.04 + 0.07 * j
                if t < t_rel:
                    continue
                d = t - t_rel
                a_rel = math.radians(-136 * (1 - math.exp(-4.2 * (t_rel - self.t_snap)) * math.cos(9.5 * (t_rel - self.t_snap))))
                ox, oy = hx + (pp[0] - 0.5) * 150, hy + (pp[1] - 0.5) * 100
                sx = bx + (ox - bx) * math.cos(a_rel) - (oy - by) * math.sin(a_rel)
                sy = by + (ox - bx) * math.sin(a_rel) + (oy - by) * math.cos(a_rel)
                px = sx + (pp[2] - 0.5) * 120 * d + 18 * math.sin(d * 5 + j)
                py = sy + 220 * d * d + 50 * d
                op = 0.9 * clamp(1 - d / 1.4)
                under.append(f'<ellipse cx="0" cy="0" rx="{n(11 + 7 * pp[3])}" ry="{n(6 + 3 * pp[3])}" fill="#e9e9e9" opacity="{op:.3f}" '
                             f'transform="translate({n(px)} {n(py)}) rotate({n(d * 300 * (pp[4] - .5) + pp[4] * 360)})" filter="url(#gls)"/>')
        return "".join(under), ""

    def mandala_svg(self, t, s):
        out = [f'<g transform="translate({CX} {CY}) scale({s:.4f}) rotate({t * 1.5:.2f})" fill="none" stroke="#efe0dc" stroke-width="2.2" opacity="0.5">']
        for a in (0, 45, 90, 135):  # 交叉的大杏仁形花瓣
            out.append(f'<path d="M-780 0 Q0 -420 780 0 Q0 420 -780 0 Z" transform="rotate({a})"/>')
            out.append(f'<path d="M-600 0 Q0 -300 600 0 Q0 300 -600 0 Z" transform="rotate({a})" stroke-width="1.4"/>')
            out.append("".join(f'<circle cx="{n(x)}" cy="{n(-200 * (1 - (x / 560) ** 2) - 20)}" r="6" transform="rotate({a})"/>'
                               f'<circle cx="{n(x)}" cy="{n(200 * (1 - (x / 560) ** 2) + 20)}" r="6" transform="rotate({a})"/>'
                               for x in np.linspace(-470, 470, 17)))
        for a in range(0, 360, 30):  # 内圈花瓣
            out.append(f'<path d="M0 -360 C60 -420 70 -520 0 -600 C-70 -520 -60 -420 0 -360 Z" transform="rotate({a + 15})" stroke-width="1.6"/>')
        out.append('</g>')
        return "".join(out)

    def sc_mandala(self, t, u):
        s = 0.92 + 0.08 * ease_out(u / 1.5)
        burst = 0.75 + 0.25 * math.exp(-u / 0.6)
        under = [self.plate_img("mauve.jpg", u), self.mandala_svg(t, s),
                 f'<g transform="translate({CX} {CY}) rotate({t * 6:.2f})" opacity="{0.55 * burst:.3f}" style="mix-blend-mode:screen">' +
                 "".join(f'<path d="M0 0 L{n(12 * math.cos(math.radians(a + 90)))} {n(12 * math.sin(math.radians(a + 90)))} '
                         f'L{n((520 + 260 * ((a * 37) % 100) / 100) * math.cos(math.radians(a)))} {n((520 + 260 * ((a * 37) % 100) / 100) * math.sin(math.radians(a)))} Z" fill="#fff6f0"/>'
                         for a in range(0, 360, 12)) + '</g>',
                 f'<circle cx="{CX}" cy="{CY}" r="560" fill="url(#hWhite)" opacity="{0.8 * burst:.3f}"/>',
                 f'<circle cx="{CX}" cy="{CY}" r="{n(330 * (1 + 0.012 * self.pulse(t)))}" fill="#fffaf6" fill-opacity="{0.78 * burst:.3f}" '
                 f'stroke="#f7ece8" stroke-width="2"/>']
        return "".join(under), ""

    def sc_ice(self, t, u):
        under = [self.plate_img("ice.jpg", u)]
        for d in self.dots[:60]:  # 飘雪
            x = (d[0] * (W + 200) + 25 * math.sin(t * 0.7 + d[5] * 6)) % (W + 200) - 100
            y = (d[2] * (H + 100) + (25 + 45 * d[3]) * t) % (H + 100) - 50
            under.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(1.5 + 3.5 * d[4] ** 2)}" fill="#ffffff" opacity="{0.55 + 0.4 * d[1]:.3f}"/>')
        under.append(self.img("foliage_ice.png", -140 - 10 * u, H - 820, 2200, 834, 'opacity="0.55" filter="url(#bl8)"'))
        under.append(self.img("foliage_ice.png", -60 - 22 * u, H - 700, 2112, 800, ""))
        over = [f'<rect y="{H - 300}" width="{W}" height="300" fill="url(#hazeUp)" opacity="0.5"/>']
        return "".join(under), "".join(over)

    def sc_navy(self, t, u):
        under = [self.plate_img("navy.jpg", u)]
        for st in self.stars:
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * (1 + 3 * st[3]) + st[2] * 20))
            under.append(f'<circle cx="{n(st[0] * W)}" cy="{n(80 + st[1] * 700)}" r="{n(0.8 + 1.8 * st[2] ** 3)}" fill="#ffffff" opacity="{a:.3f}"/>')
        sx, sy = 960, 250
        p = self.pulse(t, 3)
        sm = math.exp(-u / 0.9)
        under += [f'<ellipse cx="{sx}" cy="{sy}" rx="{n(200 * (1 + 0.3 * sm))}" ry="{n(110 * (1 + 0.3 * sm))}" fill="url(#hWhite)" opacity="0.75"/>',
                  f'<ellipse cx="{sx}" cy="{sy}" rx="{n(48 + 6 * p)}" ry="{n(15 + 3 * p)}" fill="#ffffff" filter="url(#bl8)"/>',
                  f'<ellipse cx="{sx}" cy="{sy}" rx="{n(260 * (1 + 0.2 * sm))}" ry="3" fill="#ffffff" opacity="0.7" filter="url(#bl3)"/>',
                  f'<circle cx="{sx}" cy="{sy}" r="7" fill="#ffffff"/>',
                  f'<circle cx="1180" cy="420" r="4" fill="#ffffff"/><circle cx="1180" cy="420" r="22" fill="url(#hWhite)" opacity="0.6"/>']
        under.append(self.img("foliage_side.png", -80 - 8 * u, H - 900, 2112, 900, ""))
        return "".join(under), ""

    def sc_line(self, t, u):
        under = [f'<rect width="{W}" height="{H}" fill="#030304"/>', '<g fill="none" stroke="#ffffff" stroke-linecap="round" filter="url(#gls)">']
        for k in range(3):  # 细丝带（双线）
            v = sine_io((u - 0.15 * k) / 1.8)
            for off in (0, 9 + 4 * k):
                xs = np.linspace(-60, W + 60, 50)
                ys = 520 + 80 * k + 150 * np.sin(xs / W * 2 * math.pi * (0.8 + 0.15 * k) + t * 0.5 + k * 1.7) + off
                under.append(f'<path d="M{" L".join(f"{n(x)} {n(y)}" for x, y in zip(xs, ys))}" stroke-width="{1.4 if off == 0 else 0.8}" '
                             f'opacity="{0.8 if off == 0 else 0.45}" pathLength="1" stroke-dasharray="{v:.4f} 2"/>')
        for k, (x, y, a, L) in enumerate(self.lineleaves):
            v = sine_io((u - 0.25 - 0.12 * k) / 1.1)
            if v > 0:
                for d in E.leaf_paths(x, y, a + 0.05 * math.sin(t + k), L, L * 0.36):
                    under.append(f'<path d="{d}" stroke-width="1.6" pathLength="1" stroke-dasharray="{v:.4f} 2"/>')
        under.append('</g>')
        return "".join(under), ""

    def sc_score(self, t, u):
        under = [self.plate_img("paperw.jpg", u, 0.02)]
        rise = sine_io(u / 1.4)
        for i in range(5):  # 宽宽的灰色五线谱带，从左下斜向右上
            xs = np.linspace(-80, W + 80, 60)
            ys = 900 - (xs + 80) / (W + 160) * 760 + 90 * np.sin(xs / W * math.pi * 1.4 + 0.3 + t * 0.25) + (i - 2) * 92
            under.append(f'<path d="M{" L".join(f"{n(x)} {n(y)}" for x, y in zip(xs, ys))}" fill="none" stroke="#8e8e8e" '
                         f'stroke-width="17" opacity="{0.7 * rise:.3f}" pathLength="1" stroke-dasharray="{rise:.4f} 2"/>')
        under.append(f'<text x="120" y="1015" font-family="{E.MUSIC}" font-size="760" fill="#121212" text-anchor="middle" '
                     f'opacity="{rise:.3f}">{E.CLEF}</text>')
        b = self.beat(t) - self.beat(self.span_start("score"))
        for k, (ch, x, y, fs, col) in enumerate((("♪", 830, 700, 380, "#1a1a1a"), ("♫", 1480, 740, 280, "#6a6a6a"))):
            a = sine_io((b - 1 - 3 * k) / 0.9)
            if a > 0:
                sc = 1.12 - 0.12 * a
                under.append(f'<text x="{x}" y="{y}" font-family="{E.MUSIC}" font-size="{fs}" fill="{col}" text-anchor="middle" opacity="{a:.3f}" '
                             f'transform="translate({x} {y - fs * 0.3}) scale({sc:.3f}) translate({-x} {-(y - fs * 0.3)})">{ch}</text>')
        under.append(self.img("peonies.png", -80, 330, 1020, 850, f'opacity="{sine_io(u / 1.2):.3f}"'))
        return "".join(under), ""

    def emblem(self, x, y, s, op):
        pts = []
        for a in range(0, 360, 60):
            pts.append(f'<g transform="rotate({a})"><path d="M0 0 L-9 -20 L0 -58 Z" fill="#ffffff"/><path d="M0 0 L9 -20 L0 -58 Z" fill="#dfe8ea"/></g>'
                       f'<g transform="rotate({a + 30})"><path d="M0 -10 L-5 -21 L0 -32 L5 -21 Z" fill="#ffffff" opacity="0.85"/></g>')
        return (f'<g transform="translate({n(x)} {n(y)}) scale({s:.3f})" opacity="{op:.3f}" filter="url(#gl)">{"".join(pts)}'
                f'<circle r="5" fill="#ffffff"/></g>')

    def sc_teal(self, t, u):
        under = [self.plate_img("teal.jpg", u, 0.03)]
        b1, (xs, yc) = self.band(t, 560, 70, 46, "#1b2527", 0.5, 0.35, 0.0)
        b2, _ = self.band(t, 600, 60, 30, "#2a3638", 0.4, 0.28, 2.1, 0.9)
        b3, _ = self.band(t, 540, 80, 18, "#e8f0f0", 0.12, 0.4, 4.0, 1.3)
        under += [b2, b1, b3, self.img("fg_teal.png", -96 - 14 * u, H - 600, 2112, 620, 'opacity="0.9"')]
        # 星徽沿丝带滑进来 → credits → logo
        ex = lerp(-120, 700, ease_io(u / 2.4))
        ey = float(np.interp(ex, xs, yc))
        logo = sine_io((u - 4.2) / 1.6)
        cred = sine_io((u - 1.8) / 1.0) * (1 - sine_io((u - 3.7) / 0.8))
        if logo > 0:
            ex, ey = lerp(ex, 862, logo), lerp(ey, 600, logo)
        over = [self.emblem(ex, ey, 1.0 - 0.15 * logo, ease_out(u / 0.6))]
        if cred > 0:
            over.append(f'<g font-family="{E.LOGO}" fill="#f2f6f6" opacity="{cred:.3f}"{self.blur_filter(5 * (1 - cred), "sh")}>'
                        f'<text x="300" y="250" font-size="44" font-weight="500">Music</text>'
                        f'<line x1="290" y1="268" x2="520" y2="268" stroke="#f2f6f6" stroke-width="1" opacity="0.6"/>'
                        f'<text x="300" y="306" font-size="24">Xyris / <tspan font-family="{E.SERIF}">花隈千冬</tspan></text>'
                        f'<text x="1620" y="250" font-size="44" font-weight="500" text-anchor="end">Album</text>'
                        f'<line x1="1400" y1="268" x2="1630" y2="268" stroke="#f2f6f6" stroke-width="1" opacity="0.6"/>'
                        f'<text x="1620" y="306" font-size="24" text-anchor="end">ARTIFACTS:ASCENSIØN</text>'
                        f'<text x="1620" y="340" font-size="20" text-anchor="end" opacity="0.8">fan-made narrative PV</text></g>')
        if logo > 0:
            sw = sine_io((u - 5.0) / 1.6)
            over.append(f'<g font-family="{E.LOGO}" font-weight="500" fill="#f6fafa"{self.blur_filter(8 * (1 - logo), "gl")} opacity="{logo:.3f}">'
                        f'<text x="860" y="545" font-size="92" letter-spacing="-1">Blooming</text>'
                        f'<text x="930" y="628" font-size="104" letter-spacing="-1">Planet</text></g>')
            if sw > 0:
                over.append(f'<path d="M1080 520 C1180 470 1230 400 1150 380 C1060 360 950 420 900 430 M1150 380 C1230 380 1270 470 1230 560 '
                            f'C1205 610 1160 628 1130 610" fill="none" stroke="#f6fafa" stroke-width="2.4" stroke-linecap="round" '
                            f'pathLength="1" stroke-dasharray="{sw:.4f} 2" filter="url(#gls)" opacity="{logo:.3f}"/>')
                for fx, fy in ((1040, 405), (1105, 440)):
                    k = ease_out((u - 5.8) / 0.6)
                    over.append(f'<g transform="translate({fx} {fy}) scale({k:.3f})" fill="none" stroke="#f6fafa" stroke-width="1.2" opacity="0.8">' +
                                "".join(f'<ellipse cx="0" cy="-7" rx="3.5" ry="7" transform="rotate({a})"/>' for a in range(0, 360, 72)) + '</g>')
        return "".join(under), "".join(over)

    def span_start(self, name):
        for s, nm in self.scenes:
            if nm == name:
                return s
        raise KeyError(name)

    # ---------- 节拍：先起势再回落的平滑包络，避免每拍瞬间跳变 ----------
    def pulse(self, t, k=5.0):
        b = self.beat(t)
        f = b - math.floor(b)
        atk = 0.12
        return 0.5 - 0.5 * math.cos(math.pi * f / atk) if f < atk else math.exp(-(f - atk) * k)

    # ---------- 字 ----------
    BLURS = (1, 2, 3, 5, 8)

    def blur_filter(self, amount, base):
        """虚化程度 → 预先定义好的滤镜（fbN 纯模糊，fgN 模糊 + 柔光）"""
        if amount < 0.6:
            return f' filter="url(#{base})"' if base else ""
        lv = min(self.BLURS, key=lambda b: abs(b - amount))
        return f' filter="url(#{"fg" if base == "gl" else "fb"}{lv})"'

    def chunk_end(self, k):
        t0 = self.chunks[k][0]
        _, s0, s1 = self.scene(t0)
        nxt = [c[0] for c in self.chunks if s0 <= c[0] < s1 and c[0] > t0]
        return min(nxt) if nxt else s1

    def lyrics_for(self, t, s0, s1):
        out = []
        for k, (t0, text, x, y, size, style) in enumerate(self.chunks):
            if not (s0 <= t0 < s1) or t < t0 - 0.01:
                continue
            fo = 1 - sine_io((t - self.chunk_end(k) + 0.15) / 0.55)  # 出场：虚化、上漂、淡出
            if fo <= 0:
                continue
            st = TEXT[style]
            stroke = f' stroke="{st["stroke"]}" stroke-width="{st["sw"]}"' if "stroke" in st else ""
            life = t - t0
            spacing = size * (1.5 if style == "gray" else 1.02) * (1 + 0.035 * min(life, 4) / 4)  # 字距缓慢展开
            drift = -6 * life - 16 * (1 - fo)
            for j, ch in enumerate(text):
                tj = t - t0 - j * 0.09
                a = sine_io(tj / 0.75)
                if a <= 0:
                    continue
                cx = x + (j - (len(text) - 1) / 2) * spacing
                cy = y + 26 * (1 - ease_out(tj / 0.9)) + drift
                sc = 1.06 - 0.06 * a + 0.03 * (1 - fo)
                op = st["op"] * a * fo
                tr = f'translate({n(cx)} {n(cy)}) scale({sc:.3f}) translate({n(-cx)} {n(-cy)})'
                base = f'text-anchor="middle" font-family="{E.BRUSH}" font-size="{size}" fill="{st["fill"]}"{stroke}'
                filt = self.blur_filter(7 * (1 - a) + 6 * (1 - fo), st["filt"])
                out.append(f'<text x="{n(cx)}" y="{n(cy + size * 0.36)}" {base}{filt} opacity="{op:.3f}" transform="{tr}">{ch}</text>')
                if style == "echo":  # 左右残影，缓慢呼吸
                    for sgn in (-1, 1):
                        dx = sgn * size * (0.5 + 0.18 * math.sin(t * 1.3 + j))
                        out.append(f'<text x="{n(cx + dx)}" y="{n(cy + size * 0.36)}" {base} filter="url(#fb3)" opacity="{op * 0.25:.3f}" '
                                   f'transform="{tr}">{ch}</text>')
        return "".join(out)

    def subtitle_for(self, t, name):
        if name == "teal":
            return ""
        out = []
        for k, (t0, zh) in enumerate(self.subs):
            t1 = self.subs[k + 1][0] if k + 1 < len(self.subs) else self.END
            a = sine_io((t - t0 + 0.2) / 0.6) * (1 - sine_io((t - t1 + 0.2) / 0.5))
            if a <= 0.003:
                continue
            out.append(f'<text x="{CX}" y="{n(H - BAR - 144 - 8 * a)}" text-anchor="middle" font-family="{E.HAND}" font-size="30" '
                       f'letter-spacing="2" fill="{SUB[name]}" opacity="{0.9 * a:.3f}"{self.blur_filter(4 * (1 - a), None)}>{zh}</text>')
        return "".join(out)

    def flash(self, t):
        """柔和的曝光过渡：边界前 0.15s 起势，之后指数回落"""
        op = 0.0
        for s, name in self.scenes[1:]:
            dt = t - s
            strength, tau = {"mandala": (0.85, 0.45), "teal": (0.6, 0.5), "smoke": (0.5, 0.3)}.get(name, (0.4, 0.3))
            if -0.15 < dt < 0:
                op = max(op, strength * sine_io((dt + 0.15) / 0.15))
            elif 0 <= dt < 2.5:
                op = max(op, strength * math.exp(-dt / tau))
        return op

    DEFS = E.EffectPV.DEFS.replace('</defs>', (
        '<filter id="bl3" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>'
        '<filter id="bl8" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="8"/></filter>'
        '<filter id="bl20" x="-20%" y="-80%" width="140%" height="260%"><feGaussianBlur stdDeviation="20"/></filter>'
        '<radialGradient id="hWhite"><stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="hDot"><stop offset="0" stop-color="#fff3d6" stop-opacity="0.9"/><stop offset="1" stop-color="#fff3d6" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="hWarmLight"><stop offset="0" stop-color="#fffdf8" stop-opacity="1"/><stop offset="0.35" stop-color="#fff3e2" stop-opacity="0.85"/>'
        '<stop offset="1" stop-color="#ffe8cc" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="leakR" x1="0" x2="1"><stop offset="0" stop-color="#fff2e0" stop-opacity="0"/><stop offset="1" stop-color="#fff2e0" stop-opacity="0.9"/></linearGradient>'
        '<linearGradient id="hazeUp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset="1" stop-color="#ffffff" stop-opacity="0.9"/></linearGradient>'
        + "".join(f'<filter id="fb{b}" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="{b}"/></filter>'
                  f'<filter id="fg{b}" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="{b}" result="s"/>'
                  f'<feGaussianBlur in="s" stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/>'
                  f'<feMergeNode in="s"/></feMerge></filter>' for b in (1, 2, 3, 5, 8)) +
        '</defs>'))

    def scene_group(self, k, t, op):
        s0, name = self.scenes[k]
        s1 = self.scenes[k + 1][0] if k + 1 < len(self.scenes) else 1e9
        start = s0 if s0 > -1e8 else (self.t_in if self.t_in is not None else 256.9)
        end = s1 if s1 < 1e8 else start + 9
        under, over = getattr(self, "sc_" + name)(t, t - start)
        p = (t - start) / max(0.5, end - start)  # 匀速运镜：交叉溶解时两个镜头都在动
        dx0, dy0, dx1, dy1, z0, z1, r0, r1 = CAM[name]
        z = lerp(z0, z1, p) * (1 + 0.005 * self.pulse(t, 3))
        cam = (f'translate({n(CX + lerp(dx0, dx1, p))} {n(CY + lerp(dy0, dy1, p))}) rotate({lerp(r0, r1, p):.3f}) '
               f'scale({z:.4f}) translate({-CX} {-CY})')
        body = f'<g transform="{cam}">{under}{self.lyrics_for(t, s0, s1)}{over}</g>{self.subtitle_for(t, name)}'
        return body if op >= 0.999 else f'<g opacity="{op:.3f}">{body}</g>'

    def svg(self, i):
        t = i / FPS
        k = max(j for j, (s, _) in enumerate(self.scenes) if t >= s)
        s_cur = self.scenes[k][0]
        s_next = self.scenes[k + 1][0] if k + 1 < len(self.scenes) else 1e9
        TD = 0.28  # 交叉溶解的一半时长
        if k > 0 and t - s_cur < TD:
            layers = [self.scene_group(k - 1, t, 1.0), self.scene_group(k, t, sine_io((t - s_cur + TD) / (2 * TD)))]
        elif s_next - t < TD:
            layers = [self.scene_group(k, t, 1.0), self.scene_group(k + 1, t, sine_io((t - s_next + TD) / (2 * TD)))]
        else:
            layers = [self.scene_group(k, t, 1.0)]
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', self.DEFS] + layers
        fl = self.flash(t)
        if self.t_in is not None and t < self.t_in + 0.8:
            fl = max(fl, 1 - sine_io((t - self.t_in) / 0.8))
        if fl > 0.004:
            out.append(f'<rect width="{W}" height="{H}" fill="#ffffff" opacity="{min(fl, 1):.3f}"/>')
        if self.t_out is not None and t > self.t_out - 1.2:
            out.append(f'<rect width="{W}" height="{H}" fill="#000" opacity="{sine_io((t - self.t_out + 1.2) / 1.1):.3f}"/>')
        out.append(f'<rect width="{W}" height="{BAR}" fill="#000"/><rect y="{H - BAR}" width="{W}" height="{BAR}" fill="#000"/></svg>')
        return "".join(out)

    def warm(self):
        return super().warm() + "MusicAlbumfan-madenarrativePVXyris♪♫"


FPS = E.FPS

if __name__ == "__main__":
    E.EffectPV = RefPV
    E.main()
