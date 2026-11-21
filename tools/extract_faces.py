"""Extract Roblox face decals (transparent PNG) from frontal close-up frames of the reference videos.
Each entry: frame file, face-front rectangle (x0,y0,x1,y1) in frame pixels, boxes to ignore (captions).
Usage: python extract_faces.py <frames_dir> <out_dir>
"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

CAP = (0, 622, 576, 690)  # caption band
FACES = {
    "neutral":  ("b_32.png",    (90, 230, 490, 600),  [CAP]),
    "angry":    ("b_104.5.png", (128, 140, 558, 550), [CAP, (150, 470, 420, 550)]),
    "evilgrin": ("b_110.png",   (84, 612, 504, 940),  [CAP], False, 7),
    "crying":   ("b_93.8.png",  (70, 330, 530, 790),  [CAP]),
    "sad":      ("b_147.8.png", (132, 408, 516, 672), [CAP]),
    "shocked":  ("b_133.5.png", (90, 410, 488, 770),  [CAP], True, 6),
    "content":  ("b_135.5.png", (72, 180, 576, 516),  [CAP]),
    "gasp":     ("b_121.6.png", (62, 200, 532, 620),  [CAP]),
    "worried":  ("b_36.2.png",  (24, 240, 552, 744),  [(180, 622, 372, 690)], True, 5),
}

def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114

def extract(img, rect, ignore, force_white=False, close_it=3):
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    x0, y0, x1, y1 = rect
    L = lum(a)
    # skin illumination: grey closing removes thin dark ink, then smooth
    illum = ndi.grey_closing(L, size=(31, 31))
    illum = ndi.gaussian_filter(ndi.grey_opening(illum, size=(9, 9)), 6)
    ink = np.clip((0.78 - L / np.maximum(illum, 1e-3)) / 0.45, 0, 1)
    mask_ok = np.ones(L.shape, bool)
    for bx0, by0, bx1, by1 in ignore:
        mask_ok[by0:by1, bx0:bx1] = False
    ink *= mask_ok
    # skin region: per-channel closing removes ink, then chroma match against the face centre
    ac = np.dstack([ndi.grey_closing(a[..., c], size=(31, 31)) for c in range(3)])
    chrom = ac / (ac.sum(-1, keepdims=True) + 1e-4)
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    ref = np.median(chrom[cy - 20:cy + 20, cx - 20:cx + 20].reshape(-1, 3), axis=0)
    skinm = (np.linalg.norm(chrom - ref, axis=-1) < 0.05) & (lum(ac) > 0.25)
    skinm[:y0] = skinm[y1:] = False; skinm[:, :x0] = skinm[:, x1:] = False
    lab0, _ = ndi.label(skinm)
    skinm = lab0 == lab0[cy, cx]
    skinm = ndi.binary_fill_holes(skinm)
    inner = ndi.binary_erosion(skinm, iterations=6)
    ink *= skinm
    dark = ink > 0.4
    lab, n = ndi.label(dark)
    sizes = ndi.sum(np.ones_like(ink), lab, range(1, n + 1))
    touch = set(np.unique(lab[skinm & ~inner]))
    keep = np.isin(lab, [i + 1 for i, sz in enumerate(sizes) if sz >= 30 and (i + 1) not in touch])
    ink *= ndi.binary_dilation(keep, iterations=2)
    dark &= keep
    closed = ndi.binary_closing(dark, iterations=close_it)
    crop = np.zeros_like(dark); crop[y0:y1, x0:x1] = True
    enclosed = ndi.binary_fill_holes(closed & crop) & ~closed
    enclosed &= mask_ok
    # an enclosed region must be clearly different from skin (white eye, teeth, tongue)
    skin_rgb = np.median(a[y0:y1, x0:x1][~closed[y0:y1, x0:x1]], axis=0)
    gain = (lum(skin_rgb[None, None])[0, 0] / np.maximum(illum, 1e-3))[..., None]
    normed = np.clip(a * gain, 0, 1)
    diff = np.linalg.norm(normed - skin_rgb, axis=-1) > 0.12
    lab2, n2 = ndi.label(enclosed)
    good = [i for i in range(1, n2 + 1) if force_white or diff[lab2 == i].mean() > 0.5]
    enclosed = np.isin(lab2, good)
    if force_white:
        # rings/crescents whose outline has gaps: fill each large ink component's convex hull
        from skimage.morphology import convex_hull_image
        labd, nd = ndi.label(ndi.binary_dilation(dark, iterations=6))
        for i in range(1, nd + 1):
            comp = (labd == i) & dark
            if comp.sum() < 400:
                continue
            ys, xs = np.nonzero(comp)
            sub = comp[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            if not 0.6 < sub.shape[0] / sub.shape[1] < 1.7:
                continue  # only round rings (eyes)
            hull = convex_hull_image(sub)
            fill = np.zeros_like(comp); fill[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = hull
            enclosed |= fill & ~dark
    enclosed = ndi.binary_dilation(enclosed, iterations=1) & crop
    alpha = np.where(enclosed, 1.0, ink)
    if force_white:
        normed = np.full_like(normed, 0.97)
    rgb = np.where(enclosed[..., None], normed, 0.05)
    rgba = np.dstack([rgb, alpha])[y0:y1, x0:x1]
    return Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    for name, (f, rect, ign, *opt) in FACES.items():
        extract(Image.open(os.path.join(src, f)), rect, ign, *opt).save(os.path.join(dst, name + ".png"))
        print("ok", name)
