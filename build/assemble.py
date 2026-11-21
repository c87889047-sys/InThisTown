"""Assemble rendered shots + voice lines into the final vertical video with word-by-word captions,
music and sound effects.
Usage: python assemble.py <shots_dir> <voice_dir> <work_dir> <out.mp4>
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS, SR = 1080, 1920, 30, 48000

PAD_IN, GAP, PAD_OUT = 0.15, 0.3, 0.35
SHAKE = {"s11": 9, "s17": 12, "s13": 5}
SFX = {"s11": "siren", "s17": "pop", "s10": "boing", "s19": "boing", "s01": "sting"}

COLORS = {  # ASS &HBBGGRR
    "white": "&H00FFFFFF", "yellow": "&H0000D8FF", "red": "&H004040FF", "green": "&H0055E65A",
    "blue": "&H00FFAA4A", "purple": "&H00FF78C8",
}


# ------------------------------------------------------------------ audio synthesis
def load_mono(path):
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1:
        a = a.mean(1)
    if sr != SR:
        x = np.arange(0, len(a), sr / SR)
        a = np.interp(x, np.arange(len(a)), a).astype(np.float32)
    return a


def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)
    return e


def pluck(freq, dur, r=0.25, bright=3):
    t = np.arange(int(dur * SR)) / SR
    s = sum(np.sin(2 * np.pi * freq * k * t) / k ** 1.6 for k in range(1, bright + 1))
    return (s * env(len(t), 0.003, r)).astype(np.float32)


def music(total):
    """Light, bouncy 'sneaky cartoon' loop: plucked bass + staccato melody + soft hat, 112 bpm."""
    bpm = 112
    beat = 60 / bpm
    out = np.zeros(int((total + 2) * SR), np.float32)
    n = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    bass_prog = [45, 45, 52, 52, 50, 50, 52, 40]  # A A E E D D E E (low)
    melody = [69, None, 72, 71, 69, None, 64, None, 67, None, 69, 67, 64, None, 62, 64,
              65, None, 69, 67, 65, None, 62, None, 64, 67, 71, 68, 69, None, None, None]
    t = 0.0
    step = 0
    while t < total + 1:
        i = int(t * SR)
        bar_pos = step % 32
        if bar_pos % 2 == 0:
            b = pluck(n(bass_prog[(step // 4) % 8]), beat * 0.9, r=0.18, bright=4) * 0.35
            out[i:i + len(b)] += b[: len(out) - i]
        m = melody[bar_pos]
        if m is not None:
            p = pluck(n(m + 12), beat * 0.45, r=0.09, bright=3) * 0.16
            out[i:i + len(p)] += p[: len(out) - i]
        # hat on off-beats
        if step % 2 == 1:
            hl = int(0.04 * SR)
            hat = np.random.default_rng(step).standard_normal(hl).astype(np.float32) * env(hl, 0.001, 0.012) * 0.05
            out[i:i + hl] += hat[: len(out) - i]
        t += beat / 2
        step += 1
    return out[: int(total * SR)]


def sfx(kind):
    rng = np.random.default_rng(1)
    if kind == "siren":
        d = 2.2
        t = np.arange(int(d * SR)) / SR
        f = 750 + 250 * np.sign(np.sin(2 * np.pi * 1.6 * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        s = (np.sin(ph) * 0.6 + 0.4 * np.sign(np.sin(ph)) * 0.3) * np.minimum(1, t / 0.2) * np.minimum(1, (d - t) / 0.4)
        return (s * 0.22).astype(np.float32)
    if kind == "pop":
        d = 0.25
        t = np.arange(int(d * SR)) / SR
        f = 900 * np.exp(-t * 18) + 120
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.001, 0.05) * 0.6).astype(np.float32)
    if kind == "boing":
        d = 0.6
        t = np.arange(int(d * SR)) / SR
        f = 220 + 140 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 4) + 160 * t
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.002, 0.25) * 0.35).astype(np.float32)
    if kind == "sting":
        s = sum(pluck(440 * 2 ** ((m - 69) / 12), 1.2, r=0.5, bright=4) for m in (57, 61, 64, 69)) * 0.12
        return s.astype(np.float32)
    if kind == "whoosh":
        d = 0.3
        nn = rng.standard_normal(int(d * SR)).astype(np.float32)
        k = np.ones(40) / 40
        nn = np.convolve(nn, k, "same")
        t = np.arange(len(nn)) / SR
        return (nn * np.sin(np.pi * t / d) ** 2 * 0.25).astype(np.float32)
    raise KeyError(kind)


# ------------------------------------------------------------------ captions
def ass_header(font):
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{font},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,1,0,1,7,4,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(t):
    t = max(0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def norm_word(w):
    return re.sub(r"[^a-z0-9'\-]", "", w.lower())


# ------------------------------------------------------------------ main
def main():
    shots_dir, voice_dir, work, out = sys.argv[1:5]
    os.makedirs(work, exist_ok=True)
    script = json.load(open(os.path.join(ROOT, "story", "script.json")))
    hl = {norm_word(k): v for k, v in script["highlight"].items()}
    timeline = json.load(open(os.path.join(voice_dir, "timeline.json")))

    # caption font with a clean family name for libass
    from fontTools.ttLib import TTFont
    fdir = os.path.join(work, "fonts")
    os.makedirs(fdir, exist_ok=True)
    f = TTFont(os.path.join(ROOT, "assets", "fonts", "Montserrat-900.ttf"))
    for rec in f["name"].names:
        if rec.nameID in (1, 4, 16):
            rec.string = "Caption Black"
        if rec.nameID in (2, 17):
            rec.string = "Regular"
        if rec.nameID == 6:
            rec.string = "CaptionBlack-Regular"
    f.save(os.path.join(fdir, "CaptionBlack.ttf"))

    # timing
    plan = []
    t = 0.0
    for shot in timeline:
        start = t
        cur = PAD_IN
        lines = []
        for ln in shot["lines"]:
            lines.append((cur, ln))
            cur += ln["dur"] + GAP
        dur = cur - GAP + PAD_OUT
        if shot is timeline[-1]:
            dur += 1.2
        plan.append({"id": shot["id"], "start": start, "dur": dur, "lines": lines})
        t += dur
    total = t
    print(f"total {total:.2f}s", flush=True)

    # audio
    mix = np.zeros(int((total + 1) * SR), np.float32)
    for p in plan:
        for off, ln in p["lines"]:
            a = load_mono(ln["wav"])
            i = int((p["start"] + off) * SR)
            mix[i:i + len(a)] += a * 0.95
        if p["id"] in SFX:
            s = sfx(SFX[p["id"]])
            i = int((p["start"] + (0.0 if SFX[p["id"]] in ("siren", "sting") else 0.1)) * SR)
            mix[i:i + len(s)] += s[: len(mix) - i]
        if p is not plan[0]:
            s = sfx("whoosh") * 0.5
            i = max(0, int((p["start"] - 0.12) * SR))
            mix[i:i + len(s)] += s[: len(mix) - i]
    voice_env = np.convolve(np.abs(mix), np.ones(4800) / 4800, "same")
    duck = 1.0 - 0.45 * np.clip(voice_env / 0.05, 0, 1)
    mus = music(total + 1)
    mix[: len(mus)] += mus * 0.5 * duck[: len(mus)]
    mix = np.tanh(mix * 1.1) * 0.92
    wav = os.path.join(work, "mix.wav")
    sf.write(wav, mix[: int(total * SR)], SR)

    # captions (one word at a time, pop-in)
    ass = [ass_header("Caption Black")]
    for p in plan:
        for off, ln in p["lines"]:
            words = ln["words"]
            for k, (w, a, b) in enumerate(words):
                st = p["start"] + off + a
                en = p["start"] + off + (words[k + 1][1] if k + 1 < len(words) else b + 0.25)
                en = min(en, p["start"] + p["dur"])
                col = COLORS[hl.get(norm_word(w), "white")]
                shown = re.sub(r"[^A-Za-z0-9'\-$]", "", w).upper()
                if not shown:
                    continue
                anim = r"\fscx70\fscy70\t(0,70,\fscx115\fscy115)\t(70,140,\fscx100\fscy100)"
                ass.append(f"Dialogue: 0,{ts(st)},{ts(en)},Word,,0,0,0,,{{\\pos({W // 2},{int(H * 0.63)})"
                           f"\\1c{col}{anim}}}{shown}\n")
    ass_path = os.path.join(work, "captions.ass")
    open(ass_path, "w").write("".join(ass))

    # video frames: punch-in + slow push + optional shake, piped to ffmpeg
    vf = f"ass={ass_path}:fontsdir={fdir}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", wav, "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    rng = np.random.default_rng(3)
    frame_total = int(round(total * FPS))
    fi = 0
    for p in plan:
        img = Image.open(os.path.join(shots_dir, p["id"] + ".png")).convert("RGB").resize((W, H), Image.LANCZOS)
        n = int(round((p["start"] + p["dur"]) * FPS)) - fi
        shake = SHAKE.get(p["id"], 0)
        for j in range(n):
            tt = j / FPS
            z = 1.0 + 0.05 * (tt / p["dur"])
            if tt < 0.22:
                e = 1 - (1 - tt / 0.22) ** 3
                z += 0.09 * (1 - e)
            dx = dy = 0.0
            if shake:
                amp = shake * (0.35 + 0.65 * np.exp(-tt * 1.5))
                dx, dy = rng.uniform(-amp, amp, 2)
            # affine: output pixel (x,y) samples input at centre + (x - centre)/z
            cx, cy = W / 2 + dx, H / 2 + dy
            a = 1 / z
            fr = img.transform((W, H), Image.AFFINE, (a, 0, cx - a * W / 2, 0, a, cy - a * H / 2), Image.BILINEAR)
            proc.stdin.write(fr.tobytes())
            fi += 1
    proc.stdin.close()
    proc.wait()
    print("frames", fi, "of", frame_total, "->", out)


if __name__ == "__main__":
    main()
