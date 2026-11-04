"""Command line: python -m skintone photo.jpg [--no-face] [--save-mask mask.png]"""
import argparse
import json
import sys

import cv2

from .core import analyze_bgr, detect_face, skin_mask


def main():
    p = argparse.ArgumentParser(description="Estimate skin tone (ITA category) from a photo.")
    p.add_argument("image")
    p.add_argument("--no-face", action="store_true", help="analyse the whole image instead of the detected face")
    p.add_argument("--save-mask", metavar="PNG", help="save the skin mask that was used")
    a = p.parse_args()

    bgr = cv2.imread(a.image)
    if bgr is None:
        sys.exit(f"Could not read {a.image}")
    result = analyze_bgr(bgr, use_face=not a.no_face)
    print(json.dumps(result, indent=2))

    if a.save_mask:
        region = None if a.no_face else detect_face(bgr)
        crop = bgr if region is None else bgr[region[1]:region[1] + region[3], region[0]:region[0] + region[2]]
        cv2.imwrite(a.save_mask, skin_mask(crop[..., ::-1]).astype("uint8") * 255)


if __name__ == "__main__":
    main()
