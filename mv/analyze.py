#!/usr/bin/env python3
"""音频分析：按 60fps 输出每帧的频谱、响度、鼓点等特征。

用法: analyze.py <音频文件> <输出.npz>
"""
import sys

import numpy as np
import soundfile as sf

FPS = 60
N_BANDS = 72
WIN = 4096


def smooth_decay(x, decay):
    """瞬时上升、指数回落。"""
    out = np.empty_like(x)
    v = 0.0
    for i, s in enumerate(x):
        v = max(s, v * decay)
        out[i] = v
    return out


def moving_average(x, n):
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - n // 2 - 1), mode="edge"), k, mode="valid")


def normalize(x, lo=5, hi=99.5):
    a, b = np.percentile(x, lo), np.percentile(x, hi)
    return np.clip((x - a) / max(b - a, 1e-9), 0, 1)


def main(path, out):
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    hop = sr / FPS
    n_frames = int(np.ceil(len(mono) / hop))
    padded = np.pad(mono, (WIN, WIN))
    window = np.hanning(WIN).astype(np.float32)
    freqs = np.fft.rfftfreq(WIN, 1 / sr)
    edges = np.geomspace(35, 16000, N_BANDS + 1)
    band_idx = [np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0] for i in range(N_BANDS)]
    # 低频段 FFT 分辨率不够时，至少取最近的一个 bin
    band_idx = [idx if len(idx) else np.array([np.argmin(np.abs(freqs - edges[i]))]) for i, idx in enumerate(band_idx)]
    bass_bins = np.where((freqs >= 30) & (freqs < 140))[0]

    bands = np.zeros((n_frames, N_BANDS), np.float32)
    bass = np.zeros(n_frames, np.float32)
    rms = np.zeros(n_frames, np.float32)
    flux = np.zeros(n_frames, np.float32)
    prev = None
    for i in range(n_frames):
        c = int(i * hop) + WIN
        seg = padded[c - WIN // 2:c + WIN // 2]
        spec = np.abs(np.fft.rfft(seg * window))
        power = spec ** 2
        bands[i] = [power[idx].mean() for idx in band_idx]
        bass[i] = power[bass_bins].mean()
        rms[i] = np.sqrt(np.mean(seg[WIN // 2 - 367:WIN // 2 + 368] ** 2))
        logspec = np.log1p(spec)
        if prev is not None:
            flux[i] = np.maximum(logspec - prev, 0).sum()
        prev = logspec

    # 频谱：dB 后逐频段归一化，再加回落
    db = 10 * np.log10(bands + 1e-10)
    norm = np.zeros_like(db)
    for b in range(N_BANDS):
        norm[:, b] = normalize(db[:, b], 20, 99.7)
    spectrum = np.stack([smooth_decay(norm[:, b], 0.86) for b in range(N_BANDS)], axis=1)

    # 低音鼓点：低频能量的正向变化
    bass_db = 10 * np.log10(bass + 1e-10)
    bass_n = normalize(bass_db, 10, 99.5)
    rise = np.maximum(np.diff(bass_n, prepend=bass_n[0]), 0)
    thresh = moving_average(rise, FPS) + 0.06
    kicks = []
    last = -999
    for i in range(1, n_frames - 1):
        if rise[i] > thresh[i] and rise[i] >= rise[i - 1] and rise[i] >= rise[i + 1] and i - last >= 12 and bass_n[i] > 0.45:
            kicks.append(i)
            last = i
    kick_env = np.zeros(n_frames, np.float32)
    for k in kicks:
        kick_env[k] = 1.0
    kick_env = smooth_decay(kick_env, 0.88)

    # 整体强度：约 1.5 秒平滑的响度
    loud = normalize(20 * np.log10(rms + 1e-6), 5, 99)
    intensity = normalize(moving_average(loud, int(FPS * 1.5)), 3, 97)

    # BPM：起音强度的自相关
    onset = normalize(flux, 1, 99.5)
    o = onset - moving_average(onset, FPS)
    ac = np.correlate(o, o, mode="full")[len(o) - 1:]
    lags = np.arange(len(ac))
    bpms = 60 * FPS / np.maximum(lags, 1)
    valid = (bpms >= 90) & (bpms <= 200)
    lag = lags[valid][np.argmax(ac[valid])]
    # 用抛物线插值求更精确的周期
    # 电子乐常被测成半速：半周期处也很强时取倍速
    if 60 * FPS / lag < 120 and ac[int(round(lag / 2))] > 0.5 * ac[lag]:
        lag = int(round(lag / 2))
    # 在候选周期附近精细搜索周期与相位，使拍点落在起音强度最大处
    best = (-1.0, float(lag), 0.0)
    for period in np.linspace(lag - 1.5, lag + 1.5, 121):
        grid = np.arange(0, n_frames - 1, period)
        for phase in np.linspace(0, period, 48, endpoint=False):
            idx = np.clip(np.round(grid + phase).astype(int), 0, n_frames - 1)
            score = float(onset[idx].mean())
            if score > best[0]:
                best = (score, float(period), float(phase))
    _, period, phase = best
    bpm = 60 * FPS / period

    np.savez_compressed(
        out, fps=FPS, sr=sr, n_frames=n_frames, spectrum=spectrum.astype(np.float32),
        bass=bass_n.astype(np.float32), kick=kick_env, kicks=np.array(kicks), loud=loud.astype(np.float32),
        intensity=intensity.astype(np.float32), onset=onset.astype(np.float32), bpm=bpm, beat_phase=phase,
        beat_period=period,
    )
    print(f"帧数 {n_frames}，时长 {len(mono) / sr:.2f}s，BPM≈{bpm:.2f}，鼓点 {len(kicks)} 个")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
