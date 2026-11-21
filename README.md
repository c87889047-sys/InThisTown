# In This Town — Roblox R6 story shorts

Vertical (1080×1920) Roblox-style storytime video, in the style of the "In this town…" TikTok shorts.

**Episode 1: "In This Town, Smiling Is Illegal"** → `output/in_this_town_smiling_is_illegal.mp4`

## Pipeline
| Step | Script | What it does |
|---|---|---|
| Faces | `tools/extract_faces.py` | Cuts the face decals (eyes/brows/mouth on transparent background) out of front-facing close-ups in the reference videos → `assets/faces/*.png` |
| Story | `story/script.json` | Shots, who says each line, voices, caption highlight colours |
| 3D | `build/r6.py`, `build/render_shots.py` | Builds R6 rigs (torso 2×2×1, arms/legs 1×2×1, classic head) with the face decals, sets (town, mayor's office) and renders one still per shot in Blender Cycles |
| Voices | `build/tts.py` | Kokoro TTS (offline), one voice per character, word timings for captions |
| Edit | `build/assemble.py` | Punch-in + slow zoom per shot, camera shake, word-by-word pop captions (ASS/libass), synthesized music + SFX, final mp4 |

## Rebuild
```bash
pip install bpy kokoro-onnx soundfile scipy scikit-image fonttools brotli pillow
# kokoro-v1.0.onnx + voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx releases
python build/render_shots.py renders            # add --preview for fast low-res
python build/tts.py kokoro.onnx voices.bin voice
python build/assemble.py renders voice work output/in_this_town_smiling_is_illegal.mp4
```
