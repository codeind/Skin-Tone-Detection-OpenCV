"""Skin tone estimation from a photo.

Pipeline (the same steps run in the browser version, browser_backend/skintone.js):

1. Region   - optionally crop to the face (OpenCV Haar cascade) so walls and clothes are ignored.
2. Mask     - smooth the image with a 3x3 average, keep pixels whose colour falls in skin ranges in
              two colour spaces (HSV and YCrCb), then remove specks with a 3x3 morphological opening.
3. Colour   - group the skin pixels into 3 colour clusters with k-means (in CIELAB) and take the
              largest cluster, plus any cluster of nearly the same colour, as the skin colour.
              Shadows, highlights and stray non-skin pixels fall into the other clusters.
4. Measure  - convert that colour to CIELAB and compute the Individual Typology Angle,
              ITA = arctan((L* - 50) / b*) in degrees, a standard skin colour measure in dermatology.
5. Label    - map ITA to one of six standard categories (very light ... dark).

All colour conversions are written out here with NumPy (no OpenCV rounding) so the Python and
JavaScript versions give the same answer for the same pixels.
"""
from __future__ import annotations

import math

import numpy as np

# --- 2. skin mask thresholds -----------------------------------------------------------------
# HSV uses OpenCV's scale: H 0-180, S and V 0-255. YCrCb uses the JPEG (BT.601) definition.
HSV_RANGE = {"h": (0, 25), "s": (10, 200), "v": (30, 255)}       # hue also wraps: 175-180 counts as red
HSV_HUE_WRAP = 175
YCRCB_RANGE = {"cr": (128, 175), "cb": (77, 132)}
MIN_SKIN_PIXELS = 200
MIN_SKIN_FRACTION = 0.01

# --- 3. clustering ---------------------------------------------------------------------------
K = 3
MAX_SAMPLE = 20_000
MAX_ITER = 20
MERGE_DELTA_E = 10   # CIE76 colour difference; about the smallest difference most people notice side by side is 2-3

# --- 5. ITA categories (Chardon et al., 1991; Del Bino et al., 2006) -------------------------
ITA_CATEGORIES = [            # (lower bound in degrees, label); checked from the top
    (55, "Very light"),
    (41, "Light"),
    (28, "Intermediate"),
    (10, "Tan"),
    (-30, "Brown"),
    (-math.inf, "Dark"),
]


# =============================================================================================
# colour conversions (input: float RGB arrays, 0-255, shape (..., 3))
# =============================================================================================
def rgb_to_hsv(rgb):
    rgb = np.asarray(rgb, dtype=np.float64)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    v = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = v - mn
    s = np.where(v > 0, d / np.where(v > 0, v, 1) * 255, 0)
    safe = np.where(d > 0, d, 1)
    h = np.where(v == r, 60 * (g - b) / safe,
        np.where(v == g, 120 + 60 * (b - r) / safe, 240 + 60 * (r - g) / safe))
    h = np.where(d > 0, h, 0)
    h = np.where(h < 0, h + 360, h) / 2          # OpenCV scale 0-180
    return np.stack([h, s, v], axis=-1)


def rgb_to_ycrcb(rgb):
    rgb = np.asarray(rgb, dtype=np.float64)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cr = (r - y) * 0.713 + 128
    cb = (b - y) * 0.564 + 128
    return np.stack([y, cr, cb], axis=-1)


def rgb_to_lab(rgb):
    """sRGB (0-255) -> CIELAB (D65)."""
    c = np.asarray(rgb, dtype=np.float64) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    x = (0.4124 * c[..., 0] + 0.3576 * c[..., 1] + 0.1805 * c[..., 2]) / 0.95047
    y = (0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]) / 1.00000
    z = (0.0193 * c[..., 0] + 0.1192 * c[..., 1] + 0.9505 * c[..., 2]) / 1.08883
    f = lambda t: np.where(t > 216 / 24389, np.cbrt(t), (24389 / 27 * t + 16) / 116)  # noqa: E731
    fx, fy, fz = f(x), f(y), f(z)
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)


def ita(lab):
    """Individual Typology Angle in degrees."""
    L, b = float(lab[0]), float(lab[2])
    return math.degrees(math.atan2(L - 50, b))


def ita_category(angle):
    for lower, label in ITA_CATEGORIES:
        if angle > lower:
            return label
    return ITA_CATEGORIES[-1][1]


# =============================================================================================
# 2. mask
# =============================================================================================
def box_blur3(rgb):
    """3x3 average (edges use the nearest pixel). Smooths camera noise before thresholding."""
    p = np.pad(np.asarray(rgb, dtype=np.float64), ((1, 1), (1, 1), (0, 0)), mode="edge")
    h, w = p.shape[0] - 2, p.shape[1] - 2
    return sum(p[i:i + h, j:j + w] for i in range(3) for j in range(3)) / 9


def skin_mask(rgb, smooth=None):
    """Boolean mask of skin-coloured pixels for an RGB image (H, W, 3)."""
    smooth = box_blur3(rgb) if smooth is None else smooth
    hsv = rgb_to_hsv(smooth)
    ycc = rgb_to_ycrcb(smooth)
    inside = lambda a, lo_hi: (a >= lo_hi[0]) & (a <= lo_hi[1])  # noqa: E731
    hue_ok = inside(hsv[..., 0], HSV_RANGE["h"]) | (hsv[..., 0] >= HSV_HUE_WRAP)
    m = (hue_ok & inside(hsv[..., 1], HSV_RANGE["s"])
         & inside(hsv[..., 2], HSV_RANGE["v"])
         & inside(ycc[..., 1], YCRCB_RANGE["cr"]) & inside(ycc[..., 2], YCRCB_RANGE["cb"]))
    return open3x3(m)


def _shift_stack(m, fill):
    p = np.pad(m, 1, constant_values=fill)
    h, w = m.shape
    return np.stack([p[i:i + h, j:j + w] for i in range(3) for j in range(3)])


def open3x3(m):
    """Morphological opening with a 3x3 square: erode then dilate. Removes specks."""
    eroded = _shift_stack(m, True).all(axis=0)
    return _shift_stack(eroded, False).any(axis=0)


# =============================================================================================
# 3. dominant colour
# =============================================================================================
def kmeans(pixels, k=K, max_iter=MAX_ITER):
    """Deterministic k-means: start at the pixel nearest the median, then add the pixel farthest
    from the existing centres. Returns (centres, counts)."""
    x = np.asarray(pixels, dtype=np.float64)
    k = min(k, len(x))
    med = np.median(x, axis=0)
    centres = [x[np.argmin(((x - med) ** 2).sum(1))]]
    d = ((x - centres[0]) ** 2).sum(1)
    for _ in range(1, k):
        centres.append(x[int(np.argmax(d))])
        d = np.minimum(d, ((x - centres[-1]) ** 2).sum(1))
    c = np.array(centres)
    for _ in range(max_iter):
        labels = ((x[:, None, :] - c[None, :, :]) ** 2).sum(2).argmin(1)
        new = np.array([x[labels == j].mean(0) if np.any(labels == j) else c[j] for j in range(k)])
        if np.allclose(new, c):
            break
        c = new
    labels = ((x[:, None, :] - c[None, :, :]) ** 2).sum(2).argmin(1)
    counts = np.bincount(labels, minlength=k)
    return c, counts, labels


def sample(pixels, max_n=MAX_SAMPLE):
    step = max(1, math.ceil(len(pixels) / max_n))
    return pixels[::step]


# =============================================================================================
# full pipeline
# =============================================================================================
def analyze_rgb(rgb, region=None):
    """Estimate skin tone for an RGB image array (H, W, 3, values 0-255).

    region: optional (x, y, w, h) box to analyse, e.g. a detected face.
    """
    rgb = np.asarray(rgb)
    if region is not None:
        x, y, w, h = region
        rgb = rgb[y:y + h, x:x + w]
    smooth = box_blur3(rgb)
    mask = skin_mask(rgb, smooth)
    n_skin = int(mask.sum())
    total = mask.size
    out = {"skin_pixels": n_skin, "skin_fraction": round(n_skin / total, 4) if total else 0.0}
    if n_skin < MIN_SKIN_PIXELS or n_skin / total < MIN_SKIN_FRACTION:
        return {**out, "label": "No skin detected"}

    pixels = sample(smooth[mask])
    lab_pixels = rgb_to_lab(pixels)
    centres, counts, labels = kmeans(lab_pixels)            # cluster in CIELAB: distances match perceived colour
    top = int(np.argmax(counts))
    # clusters closer than MERGE_DELTA_E to the largest one are the same colour (e.g. uniform skin
    # split three ways), so they are counted together
    same = np.sqrt(((centres - centres[top]) ** 2).sum(1)) < MERGE_DELTA_E
    chosen = np.isin(labels, np.flatnonzero(same))
    colour = pixels[chosen].mean(0)
    lab = rgb_to_lab(colour)
    angle = ita(lab)
    r, g, b = (int(round(v)) for v in colour)
    return {
        **out,
        "label": ita_category(angle),
        "ita": round(angle, 1),
        "lab": [round(float(v), 1) for v in lab],
        "rgb": [r, g, b],
        "hex": f"#{r:02x}{g:02x}{b:02x}",
        "cluster_share": round(float(chosen.mean()), 3),
    }


def detect_face(bgr):
    """Largest frontal face as (x, y, w, h), shrunk to its inner 70% to drop hair and background.
    Returns None if OpenCV finds no face."""
    import cv2

    path = getattr(getattr(cv2, "data", None), "haarcascades", "") + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(path)
    if cascade.empty():          # cascade file missing from this OpenCV build: analyse the whole image
        return None
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    dx, dy = int(w * 0.15), int(h * 0.15)
    return int(x + dx), int(y + dy), int(w - 2 * dx), int(h - 2 * dy)


def analyze_bgr(bgr, use_face=True):
    """Analyse an OpenCV (BGR) image. Crops to the face when one is found."""
    region = detect_face(bgr) if use_face else None
    result = analyze_rgb(bgr[..., ::-1], region)
    result["face_found"] = region is not None
    return result


def analyze_bytes(data: bytes, use_face=True):
    """Analyse an encoded image (JPEG/PNG bytes) without writing it to disk."""
    import cv2

    bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Not a readable image")
    return analyze_bgr(bgr, use_face)
