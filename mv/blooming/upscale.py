#!/usr/bin/env python3
"""用 Real-ESRGAN（动漫模型，ncnn CPU 推理）把封面放大 4 倍，给全屏特写镜头用。

模型取自 Real-ESRGAN 的 ncnn 发布包（models/realesrgan-x4plus-anime.param/.bin）。
用法: python3 upscale.py <模型目录> <输入图> <输出图> [--tile 192]
"""
import argparse
import time

import ncnn
import numpy as np
from PIL import Image

SCALE = 4


def upscale(model_dir, src, tile=192, pad=12):
    net = ncnn.Net()
    net.opt.use_vulkan_compute = False
    net.opt.num_threads = 4
    net.load_param(f"{model_dir}/realesrgan-x4plus-anime.param")
    net.load_model(f"{model_dir}/realesrgan-x4plus-anime.bin")
    img = np.asarray(Image.open(src).convert("RGB"), np.float32) / 255
    h, w, _ = img.shape
    out = np.zeros((h * SCALE, w * SCALE, 3), np.float32)
    padded = np.pad(img, ((pad, pad), (pad, pad), (0, 0)), mode="reflect")
    t0 = time.time()
    tiles = [(y, x) for y in range(0, h, tile) for x in range(0, w, tile)]
    for k, (y, x) in enumerate(tiles):
        th, tw = min(tile, h - y), min(tile, w - x)
        patch = np.ascontiguousarray(padded[y:y + th + 2 * pad, x:x + tw + 2 * pad].transpose(2, 0, 1))
        ex = net.create_extractor()
        ex.input("data", ncnn.Mat(patch))
        _, res = ex.extract("output")
        res = np.array(res).transpose(1, 2, 0)
        p = pad * SCALE
        out[y * SCALE:(y + th) * SCALE, x * SCALE:(x + tw) * SCALE] = res[p:p + th * SCALE, p:p + tw * SCALE]
        if k % 10 == 0:
            print(f"{k + 1}/{len(tiles)}  {time.time() - t0:.0f}s", flush=True)
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("models")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--tile", type=int, default=192)
    a = ap.parse_args()
    upscale(a.models, a.src, a.tile).save(a.dst, quality=95)
