"""Voice every line of story/script.json with Kokoro (offline TTS) and estimate per-word timings.
Usage: python tts.py <kokoro.onnx> <voices.bin> <out_dir>
Writes <out_dir>/<shot>_<n>.wav and <out_dir>/timeline.json
"""
import json
import os
import re
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 24000


def trim(a, thr=0.012):
    idx = np.nonzero(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    return a[max(0, idx[0] - 240): idx[-1] + 480]


def word_weights(k, words):
    w = []
    for word in words:
        clean = re.sub(r"[^A-Za-z0-9'\-]", "", word) or "a"
        try:
            ph = k.tokenizer.phonemize(clean.replace("-", " "), "en-us")
            n = len(re.sub(r"\s", "", ph))
        except Exception:
            n = len(clean)
        n = max(n, 2)
        if re.search(r"[.!?]$", word):
            n += 3  # pause after sentence end
        elif word.endswith(","):
            n += 2
        w.append(n)
    w = np.array(w, float)
    return w / w.sum()


def main():
    model, voices, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    k = Kokoro(model, voices)
    script = json.load(open(os.path.join(ROOT, "story", "script.json")))
    timeline = []
    for shot in script["shots"]:
        lines = []
        for n, (spk, txt) in enumerate(shot["lines"]):
            v = script["voices"][spk]
            audio, sr = k.create(txt, voice=v["voice"], speed=v["speed"], lang="en-us")
            assert sr == SR
            audio = trim(np.asarray(audio, np.float32))
            # gentle normalisation
            audio = audio / (np.abs(audio).max() + 1e-6) * 0.9
            path = os.path.join(out, f"{shot['id']}_{n}.wav")
            sf.write(path, audio, SR)
            dur = len(audio) / SR
            words = txt.split()
            ww = word_weights(k, words)
            t = 0.04
            span = dur - 0.08
            wt = []
            for word, f in zip(words, ww):
                wt.append([word, round(t, 3), round(t + f * span, 3)])
                t += f * span
            lines.append({"speaker": spk, "text": txt, "wav": path, "dur": dur, "words": wt})
            print(shot["id"], n, f"{dur:.2f}s", txt, flush=True)
        timeline.append({"id": shot["id"], "lines": lines})
    json.dump(timeline, open(os.path.join(out, "timeline.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
