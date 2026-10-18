"""Synthesises the 15 s ambient score for the teaser (numpy only) -> WAV.

Usage: python3 audio.py out.wav
Cues follow the timeline in scene.html: title shimmer (~1 s), galaxy riser (3-6 s),
flash impact (6.25 s), typing (6.95-8.3 s), send (8.4 s), moon swell (9 s),
end-card impact + chime (12.8 s), fade out (14.2-15 s).
"""
import sys
import wave

import numpy as np

SR = 48000
DUR = 15.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(11)


def env(start, attack, decay, shape=4.0):
    e = np.zeros(N)
    x = t - start
    a = (x >= 0) & (x < attack)
    e[a] = (x[a] / attack) ** 2
    d = x >= attack
    e[d] = np.exp(-(x[d] - attack) * shape / decay)
    return e


def lowpass(x, cutoff):
    # one-pole low-pass, cutoff may be an array (time-varying)
    cutoff = np.broadcast_to(cutoff, x.shape)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def smooth(a, b, x):
    k = np.clip((x - a) / (b - a), 0, 1)
    return k * k * (3 - 2 * k)


L = np.zeros(N)
R = np.zeros(N)

# --- drone pad -----------------------------------------------------------
pad_amp = smooth(0, 2.5, t) * (1 - smooth(14.0, 15.0, t))
for f, g in [(55.0, .5), (82.41, .32), (110.0, .22), (164.81, .12), (220.0, .06)]:
    lfo = .7 + .3 * np.sin(2 * np.pi * (.07 + f / 4000) * t + f)
    L += g * lfo * np.sin(2 * np.pi * f * t)
    R += g * lfo * np.sin(2 * np.pi * f * 1.003 * t + .7)
# brighten the pad as the galaxy grows, darken for the interface, open up on the moon
bright = .25 + .5 * smooth(3, 6, t) - .35 * smooth(6.2, 6.8, t) + .45 * smooth(9, 12, t)
L *= pad_amp * (.6 + .4 * bright) * .22
R *= pad_amp * (.6 + .4 * bright) * .22

# --- noise risers / whooshes --------------------------------------------
def riser(peak, length, gain, cut_lo, cut_hi):
    global L, R
    e = smooth(peak - length, peak, t) * np.exp(-np.clip(t - peak, 0, None) * 5)
    cut = cut_lo + (cut_hi - cut_lo) * e
    for ch in (0, 1):
        n = rng.standard_normal(N)
        s = lowpass(n, cut) - lowpass(n, cut * .25)
        if ch == 0:
            L += s * e * gain
        else:
            R += s * e * gain


riser(3.1, 2.4, .35, 300, 3500)
riser(6.25, 1.6, .55, 400, 7000)
riser(9.1, 1.2, .3, 200, 2500)
riser(12.75, 1.4, .45, 300, 6000)

# --- sub impacts ---------------------------------------------------------
def impact(at, gain):
    global L, R
    x = np.clip(t - at, 0, None)
    f = 35 + 60 * np.exp(-x * 9)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * env(at, .005, 2.2, 5) * gain
    L += s
    R += s


impact(6.25, .55)
impact(12.75, .6)

# --- shimmer chimes ------------------------------------------------------
def chime(at, base, gain):
    global L, R
    for k, (m, g) in enumerate([(1, 1), (2.01, .5), (3.02, .3), (4.2, .18), (5.43, .1)]):
        e = env(at + k * .03, .02, 3.2 - k * .4, 4)
        s = np.sin(2 * np.pi * base * m * t) * e * g * gain
        L += s * (1 - .15 * k)
        R += s * (.85 + .15 * k)


chime(1.0, 659.25, .07)
chime(1.25, 987.77, .045)
chime(12.85, 523.25, .08)
chime(13.05, 783.99, .05)

# --- typing ticks + send -------------------------------------------------
chars = 36
for i in range(chars):
    at = 6.95 + 1.35 * (i + 1) / chars + rng.uniform(-.008, .008)
    i0 = int(at * SR)
    n = int(.04 * SR)
    burst = np.diff(rng.standard_normal(n + 1)) * np.exp(-np.arange(n) / SR * 200)  # bright, short tick
    pan = .5 + rng.uniform(-.15, .15)
    L[i0:i0 + n] += burst * .03 * (1 - pan) * 2
    R[i0:i0 + n] += burst * .03 * pan * 2
e = env(8.4, .002, .25, 6)
send = np.sin(2 * np.pi * 1318.5 * t) * e * .06 + np.sin(2 * np.pi * 1975.5 * t) * e * .03
L += send
R += send

# --- simple stereo reverb ------------------------------------------------
def reverb(x, seed, length=2.4, mix=.28):
    r = np.random.default_rng(seed)
    n = int(SR * length)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / SR * 3.2)
    ir[0] = 0
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]
    wet /= np.max(np.abs(wet)) + 1e-9
    return x * (1 - mix) + wet * np.max(np.abs(x)) * mix


L = reverb(L, 1)
R = reverb(R, 2)

master = smooth(0, .3, t) * (1 - smooth(14.2, 15.0, t))
L *= master
R *= master
peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
L = np.tanh(L / peak * 1.2) * .89
R = np.tanh(R / peak * 1.2) * .89

data = (np.stack([L, R], axis=1) * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(data.tobytes())
