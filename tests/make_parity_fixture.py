"""Write tests/fixtures/parity.json: small synthetic images and the Python result for each.

tests/test_parity.mjs runs web/skintone.js on the same pixels and compares.

    python tests/make_parity_fixture.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from skintone import core  # noqa: E402

MST = ["#f6ede4", "#f3e7db", "#f7ead0", "#eadaba", "#d7bd96", "#a07e56", "#825c43", "#604134", "#3a312a", "#292420"]
BGS = ["#3060c0", "#ffffff", "#1f2a44", "#40a050", "#808080"]
OUT = Path(__file__).parent / "fixtures" / "parity.json"


def rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def scene(skin, bg, seed, shadow=False, w=48, h=40):
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3))
    img[:] = rgb(bg)
    yy, xx = np.mgrid[0:h, 0:w]
    face = ((xx - w / 2) / (w * 0.28)) ** 2 + ((yy - h / 2) / (h * 0.42)) ** 2 <= 1
    img[face] = rgb(skin)
    if shadow:                                   # darker right side and a highlight, like side lighting
        img[face & (xx > w * 0.6)] *= 0.7
        img[face & (xx < w * 0.4) & (yy < h * 0.4)] = np.minimum(255, img[face & (xx < w * 0.4) & (yy < h * 0.4)] * 1.15)
    img += rng.normal(0, 6, img.shape)
    return np.clip(np.round(img), 0, 255).astype(int)


def main():
    cases = []
    for i, c in enumerate(MST):
        img = scene(c, BGS[i % len(BGS)], seed=i, shadow=i % 2 == 1)
        cases.append({"name": f"MST {i + 1}", "img": img})
    cases.append({"name": "no skin", "img": np.clip(np.full((30, 30, 3), rgb("#3060c0")), 0, 255).astype(int)})
    out = []
    for c in cases:
        img = c["img"]
        out.append({"name": c["name"], "height": img.shape[0], "width": img.shape[1],
                    "pixels": img.reshape(-1).tolist(), "expected": core.analyze_rgb(img.astype(float))})
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    for c in out:
        e = c["expected"]
        print(f"{c['name']:8s} {e['label']:16s} ita={e.get('ita')}")


if __name__ == "__main__":
    main()
