"""逐帧合成后期（给 effectpv.py 的截图加质感）：泛光 + 光晕、色差、胶片颗粒、暗角、分场景调色。"""
import cv2
import numpy as np

W, H = 1920, 1080
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_R2 = (((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2)
VIGNETTE = (1 - 0.32 * _R2 ** 1.3).clip(0, 1)[..., None]

# 分场景：泛光阈值 / 强度 / 光晕色 / 颗粒强度 / 调色（lift, gain）
GRADE = {
    "sepia": dict(th=0.62, bloom=0.45, halo=(1.0, 0.82, 0.6), grain=0.022, lift=(0.03, 0.02, 0.0), gain=(1.02, 0.98, 0.9)),
    "rain": dict(th=0.6, bloom=0.5, halo=(0.9, 0.95, 1.0), grain=0.025, lift=(0.0, 0.01, 0.02), gain=(0.96, 0.99, 1.02)),
    "ink": dict(th=0.8, bloom=0.3, halo=(1.0, 1.0, 1.0), grain=0.022, lift=(0.0, 0.0, 0.0), gain=(1.0, 1.0, 1.0)),
    "bloom": dict(th=0.7, bloom=0.55, halo=(1.0, 0.8, 0.78), grain=0.018, lift=(0.02, 0.0, 0.0), gain=(1.02, 0.98, 0.97)),
    "star": dict(th=0.5, bloom=0.8, halo=(0.7, 0.88, 1.0), grain=0.02, lift=(0.0, 0.01, 0.03), gain=(0.97, 1.0, 1.03)),
    "line": dict(th=0.55, bloom=0.7, halo=(0.9, 0.95, 1.0), grain=0.022, lift=(0.012, 0.012, 0.018), gain=(1.0, 1.0, 1.0)),
    "score": dict(th=0.85, bloom=0.25, halo=(1.0, 0.95, 0.88), grain=0.02, lift=(0.02, 0.015, 0.0), gain=(1.0, 0.99, 0.96)),
    "end": dict(th=0.85, bloom=0.3, halo=(1.0, 0.92, 0.8), grain=0.018, lift=(0.02, 0.015, 0.0), gain=(1.0, 0.99, 0.96)),
}


def process(jpeg_bytes, scene, frame_index, bar=118):
    img = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR).astype(np.float32) / 255  # BGR
    g = GRADE[scene]
    lum = img @ np.array([0.114, 0.587, 0.299], np.float32)
    bright = img * np.clip((lum - g["th"]) / (1 - g["th"] + 1e-3), 0, 1)[..., None] ** 1.5
    small = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    bloom = sum(w * cv2.resize(cv2.GaussianBlur(small, (0, 0), s), (W, H)) for s, w in ((2, 0.5), (6, 0.35), (16, 0.3)))
    halo = np.array(g["halo"][::-1], np.float32)
    img = img + g["bloom"] * bloom * halo
    img = np.where(img > 0.85, 0.85 + (1 - np.exp(-(img - 0.85) * 6.7)) * 0.15, img)  # 高光软肩，泛光不死白
    # 色差：红、蓝通道沿径向轻微错开
    b, gch, r = cv2.split(img)
    k = 0.0018
    M_r = np.float32([[1 + k, 0, -W / 2 * k], [0, 1 + k, -H / 2 * k]])
    M_b = np.float32([[1 - k, 0, W / 2 * k], [0, 1 - k, H / 2 * k]])
    r = cv2.warpAffine(r, M_r, (W, H), borderMode=cv2.BORDER_REFLECT)
    b = cv2.warpAffine(b, M_b, (W, H), borderMode=cv2.BORDER_REFLECT)
    img = cv2.merge([b, gch, r])
    img = np.array(g["lift"][::-1], np.float32) + img * np.array(g["gain"][::-1], np.float32)
    img *= VIGNETTE
    # 胶片颗粒：半分辨率噪声放大，颗粒更有团块感；中间调最明显
    rng = np.random.default_rng(frame_index)
    noise = cv2.resize(rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    lum = img @ np.array([0.114, 0.587, 0.299], np.float32)
    img += (g["grain"] * noise * (0.35 + 0.65 * (1 - np.abs(lum * 2 - 1))))[..., None]
    out = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    out[:bar] = 0
    out[H - bar:] = 0
    return cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 97])[1].tobytes()
