#!/usr/bin/env python3
"""矢量玫瑰（俯视，可压扁成斜视）：螺旋花心 + 多层圆润花瓣 + 卷边线 + 径向渐变。

rose_svg() 直接给 effectpv.py 逐帧画；render_pngs() 预渲染透明 PNG 给 fxtex.py 做剪影/水彩/冰色前景。
用法: python3 rose.py <输出目录>
"""
import math
import os
import sys

import numpy as np

RINGS = [3, 4, 5, 6, 7, 8]

STYLES = {
    # 渐变色标（从花心到外缘）、描边色、卷边线色
    "ink": dict(stops=[(0, "#141414"), (0.16, "#5a5a5a"), (0.42, "#e4e4e4"), (1, "#ffffff")], stroke="#101010", curl="#101010",
                leaf=[(0, "#1a1a1a"), (1, "#f2f2f2")], leaf_stroke="#101010"),
    "bloom": dict(stops=[(0, "#6d1f3a"), (0.22, "#b8466a"), (0.55, "#f2a3bb"), (1, "#fff3f6")], stroke="#8a3350", curl="#ffffff",
                  leaf=[(0, "#1f5f55"), (1, "#8fd3bd")], leaf_stroke="#1f4f47"),
    "gray": dict(stops=[(0, "#2b2f33"), (0.3, "#6b7177"), (1, "#e9ecee")], stroke="#3a3f44", curl="#ffffff",
                 leaf=[(0, "#40464b"), (1, "#c9cdd0")], leaf_stroke="#3a3f44"),
    "ice": dict(stops=[(0, "#1d4f7c"), (0.3, "#5c9fd0"), (0.7, "#cfeeff"), (1, "#ffffff")], stroke="#2a6a9a", curl="#ffffff",
                leaf=[(0, "#2c6f9a"), (1, "#d9f4ff")], leaf_stroke="#2a6a9a"),
    "sepia": dict(stops=[(0, "#2e2114"), (0.4, "#6e5538"), (1, "#c9b28c")], stroke="#2e2114", curl="#e8d8bb",
                  leaf=[(0, "#3a2a19"), (1, "#8d7352")], leaf_stroke="#2e2114"),
    "line": dict(stops=None, stroke="#ffffff", curl="#ffffff", leaf=None, leaf_stroke="#ffffff"),
}


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _pts(pts):
    return " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def petal(cx, cy, phi, r0, r1, half, squash, rot, point=0.0):
    """一片花瓣：局部 (沿半径 x, 切向 y) 画出宽圆的瓣形，再映射回极坐标，所以花瓣会顺着圈弯"""
    tau = np.linspace(0, math.pi, 34)
    s = np.sin(tau)
    # point > 0：外层花瓣边缘外卷形成的小尖；< 0：内层瓣缘的小凹
    x = r0 + (r1 - r0) * s ** 0.7 + (r1 - r0) * point * np.exp(-((tau - math.pi / 2) / 0.15) ** 2)
    y = np.cos(tau) * s ** 0.3 * 1.2
    ang = phi + half * y + rot
    X, Y = cx + x * np.cos(ang), cy + x * np.sin(ang) * squash
    outline = "M" + _pts(zip(X, Y)) + " Z"
    k = (tau > 0.3 * math.pi) & (tau < 0.62 * math.pi)
    xc = x[k] - (r1 - r0) * 0.09
    curl = "M" + _pts(zip(cx + xc * np.cos(ang[k]), cy + xc * np.sin(ang[k]) * squash))
    return outline, curl


def leaf(cx, cy, ang, L, Wd, squash):
    c, s = math.cos(ang), math.sin(ang)

    def p(u, v):
        return f"{cx + (u * c - v * s):.1f} {cy + (u * s + v * c) * squash:.1f}"
    body = f"M{p(0, 0)} C{p(L * .25, -Wd)} {p(L * .7, -Wd * .9)} {p(L, 0)} C{p(L * .7, Wd * .9)} {p(L * .25, Wd)} {p(0, 0)} Z"
    veins = [f"M{p(L * .05, 0)} L{p(L * .92, 0)}"]
    for v in (0.22, 0.4, 0.58, 0.74):
        e = Wd * 0.62 * math.sin(math.pi * (v + .14)) ** 0.8  # 叶脉终点收在叶缘以内
        veins.append(f"M{p(L * v, 0)} Q{p(L * (v + .07), -e * .5)} {p(L * (v + .14), -e)}")
        veins.append(f"M{p(L * v, 0)} Q{p(L * (v + .07), e * .5)} {p(L * (v + .14), e)}")
    return body, veins


def rose_svg(uid, cx, cy, R, style, g=1.0, rot=0.0, squash=1.0, seed=0, leaves=True, reveal=None, opacity=1.0, bg="#050507"):
    """g = 开放程度 0..1（从花心往外一圈圈长出来）；reveal = 线稿描出进度（仅 line 风格）"""
    st = STYLES[style]
    rng = np.random.default_rng(seed)
    sw = max(0.8, R / 170 * 1.5)
    defs = ""
    if st["stops"]:
        stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in st["stops"])
        lstops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in st["leaf"])
        defs = (f'<defs><radialGradient id="rg{uid}" gradientUnits="userSpaceOnUse" cx="{cx:.1f}" cy="{cy:.1f}" r="{R:.1f}" '
                f'gradientTransform="translate(0 {cy * (1 - squash):.1f}) scale(1 {squash:.3f})">{stops}</radialGradient>'
                f'<radialGradient id="lg{uid}" gradientUnits="userSpaceOnUse" cx="{cx:.1f}" cy="{cy:.1f}" r="{R * 1.5:.1f}">{lstops}</radialGradient></defs>')
    out = [f'<g opacity="{opacity:.3f}">', defs]
    line = style == "line"
    dash = (lambda k: f' pathLength="1" stroke-dasharray="{k:.4f} 2"') if line and reveal is not None else (lambda k: "")
    n = len(RINGS)
    if leaves:
        la = ease_out(g * 1.6)
        for j in range(5):
            a = rot + j * 2 * math.pi / 5 + 0.4 + rng.normal(0, 0.12)
            L = R * (1.05 + 0.2 * rng.random()) * (0.4 + 0.6 * la)
            body, veins = leaf(cx, cy, a, L, L * 0.36, squash)
            k = ease_out((reveal - 0.05 * j) / 0.4) if reveal is not None else 1
            fill = bg if line else f"url(#lg{uid})"
            out.append(f'<path d="{body}" fill="{fill}" stroke="{st["leaf_stroke"]}" stroke-width="{sw:.2f}"{dash(k)}/>')
            out.append(f'<g fill="none" stroke="{st["leaf_stroke"]}" stroke-width="{sw * 0.6:.2f}" opacity="0.7">' +
                       "".join(f'<path d="{v}"{dash(k)}/>' for v in veins) + '</g>')
    if not line:  # 花心底色，免得叶子从中间露出来
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R * 0.22:.1f}" fill="url(#rg{uid})" transform="translate(0 {cy * (1 - squash):.1f}) scale(1 {squash:.3f})"/>')
    for k in range(n - 1, -1, -1):
        a = ease_out(g * (n + 2) / 2.2 - k * 0.42)
        if a <= 0:
            continue
        frac = (k + 1) / n
        r1 = R * (0.16 + 0.84 * frac ** 1.25) * (0.35 + 0.65 * a)
        r0 = R * 0.02 + r1 * 0.2
        m = RINGS[k]
        off = k * 2.39996 + rng.normal(0, 0.1)
        half = math.pi / m * (1.25 + 0.5 * (1 - frac))  # 越往里包得越紧
        point = 0.12 * frac - 0.04
        ring_rot = rot * (1 + 0.15 * k)
        for j in range(m):
            phi = off + j * 2 * math.pi / m + rng.normal(0, 0.06)
            o, c = petal(cx, cy, phi, r0, r1 * (1 + rng.normal(0, 0.06)), half * (1 + rng.normal(0, 0.08)), squash, ring_rot, point)
            if line:  # 线稿：用底色填充遮住下面的线，保持干净
                kk = ease_out(((reveal if reveal is not None else 1) - 0.06 * (n - k)) / 0.45)
                out.append(f'<path d="{o}" fill="{bg}" fill-opacity="{kk:.3f}" stroke="{st["stroke"]}" stroke-width="{sw:.2f}"{dash(kk)}/>')
                if frac > 0.5:
                    out.append(f'<path d="{c}" fill="none" stroke="{st["curl"]}" stroke-width="{sw * 0.6:.2f}" opacity="{0.6 * kk:.3f}"/>')
            else:
                out.append(f'<path d="{o}" fill="url(#rg{uid})" stroke="{st["stroke"]}" stroke-width="{sw * (0.7 + 0.5 * frac):.2f}" '
                           f'stroke-linejoin="round"/>')
                if frac > 0.4:
                    out.append(f'<path d="{c}" fill="none" stroke="{st["curl"]}" stroke-width="{sw * 0.8:.2f}" opacity="0.6"/>')
    th = np.linspace(0, 4.2 * math.pi, 90)
    r = R * (0.012 + 0.0115 * th) * (0.5 + 0.5 * ease_out(g * 2))
    sp = "M" + _pts(zip(cx + r * np.cos(th + rot * 1.3), cy + r * np.sin(th + rot * 1.3) * squash))
    out.append(f'<path d="{sp}" fill="none" stroke="{st["stroke"]}" stroke-width="{sw:.2f}" stroke-linecap="round"'
               f'{dash(ease_out(((reveal or 1) - 0.1) / 0.5)) if line else ""}/>')
    out.append('</g>')
    return "".join(out)


def render_pngs(out, size=900):
    """预渲染几种风格的透明 PNG：top = 俯视，tilt = 斜视（压扁 0.62）"""
    from playwright.sync_api import sync_playwright
    jobs = [("rose_gray_top", "gray", 1.0, 1), ("rose_gray_tilt", "gray", 0.62, 2), ("rose_gray_top2", "gray", 1.0, 3),
            ("rose_ice_tilt", "ice", 0.62, 4), ("rose_ice_tilt2", "ice", 0.7, 5), ("rose_dark_tilt", "gray", 0.62, 6)]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": size, "height": size})
        for name, style, sq, seed in jobs:
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">' +
                   rose_svg(name, size / 2, size / 2, size * 0.3, style, 1.0, seed * 0.7, sq, seed) + '</svg>')
            page.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
            page.screenshot(path=os.path.join(out, f"{name}.png"), omit_background=True)
        b.close()


if __name__ == "__main__":
    os.makedirs(sys.argv[1], exist_ok=True)
    render_pngs(sys.argv[1])
