"""Tests use synthetic images only: a patch of a known colour on a background.

The 10 reference colours are the Monk Skin Tone Scale (Google, CC BY 4.0, skintone.google).
"""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from skintone import core

MST = ["#f6ede4", "#f3e7db", "#f7ead0", "#eadaba", "#d7bd96", "#a07e56", "#825c43", "#604134", "#3a312a", "#292420"]
EXPECTED = ["Very light"] * 4 + ["Light", "Tan", "Brown", "Dark", "Dark", "Dark"]
BACKGROUNDS = {"white": "#ffffff", "gray": "#808080", "black": "#101010", "blue": "#3060c0", "green": "#40a050",
               "red": "#d02020", "sky": "#87ceeb", "navy": "#1f2a44", "yellow": "#f0d020", "pink": "#f4a6c0"}
FIXTURES = Path(__file__).parent / "fixtures" / "parity.json"


def rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def patch(colour, bg="#3060c0", noise=0.0, seed=0):
    img = np.zeros((120, 160, 3))
    img[:] = rgb(bg)
    img[20:100, 40:120] = rgb(colour)
    if noise:
        img = img + np.random.default_rng(seed).normal(0, noise, img.shape)
    return np.clip(img, 0, 255)


@pytest.mark.parametrize("colour,label", list(zip(MST, EXPECTED)))
def test_each_monk_tone_is_detected_and_labelled(colour, label):
    r = core.analyze_rgb(patch(colour, noise=8))
    assert r["label"] == label
    assert r["skin_fraction"] > 0.15                       # the patch is a third of the image


def test_ita_ordering_follows_the_scale():
    angles = [core.analyze_rgb(patch(c))["ita"] for c in MST]
    assert angles == sorted(angles, reverse=True)


def test_measured_colour_is_unbiased_under_noise():
    for c in MST:
        true = core.ita(core.rgb_to_lab(rgb(c)))
        assert abs(core.analyze_rgb(patch(c, noise=12))["ita"] - true) < 3


@pytest.mark.parametrize("name", BACKGROUNDS)
def test_common_backgrounds_are_not_skin(name):
    img = np.full((80, 80, 3), rgb(BACKGROUNDS[name]), dtype=float)
    assert core.analyze_rgb(img)["label"] == "No skin detected"


def test_no_skin_returns_a_result_instead_of_crashing():
    r = core.analyze_rgb(np.zeros((50, 50, 3)))
    assert r == {"skin_pixels": 0, "skin_fraction": 0.0, "label": "No skin detected"}


def test_ita_category_boundaries():
    assert [core.ita_category(a) for a in (56, 55, 42, 30, 11, -29, -31)] == \
        ["Very light", "Light", "Light", "Intermediate", "Tan", "Brown", "Dark"]


def test_lab_matches_opencv():
    px = np.random.default_rng(0).integers(0, 256, (2000, 3)).astype(np.uint8)
    ours = core.rgb_to_lab(px)
    ref = cv2.cvtColor(px[None, :, ::-1].astype(np.float32) / 255, cv2.COLOR_BGR2Lab)[0]
    assert np.abs(ours - ref).max() < 0.5


def test_hsv_and_ycrcb_match_opencv():
    px = np.random.default_rng(1).integers(0, 256, (2000, 3)).astype(np.uint8)
    bgr = px[None, :, ::-1]
    hsv_ref = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0].astype(float)
    hsv = core.rgb_to_hsv(px)
    hue_diff = np.abs(hsv[:, 0] - hsv_ref[:, 0])
    assert np.minimum(hue_diff, 180 - hue_diff).max() <= 1          # hue wraps at 180
    assert np.abs(hsv[:, 1:] - hsv_ref[:, 1:]).max() <= 1
    ycc_ref = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)[0].astype(float)
    assert np.abs(core.rgb_to_ycrcb(px) - ycc_ref).max() <= 1


def test_bgr_input_is_handled_the_same_as_rgb():
    img = patch(MST[5]).astype(np.uint8)
    assert core.analyze_bgr(img[..., ::-1].copy(), use_face=False)["ita"] == core.analyze_rgb(img)["ita"]


def test_encoded_bytes_are_analysed_in_memory():
    img = patch(MST[6]).astype(np.uint8)[..., ::-1]
    ok, png = cv2.imencode(".png", img)
    r = core.analyze_bytes(png.tobytes(), use_face=False)
    assert r["label"] == "Brown" and r["face_found"] is False


def test_unreadable_bytes_raise():
    with pytest.raises(ValueError):
        core.analyze_bytes(b"not an image")


def test_parity_fixture_is_current():
    """web/skintone.js is checked against this file (tests/test_parity.mjs)."""
    cases = json.loads(FIXTURES.read_text())
    for case in cases:
        img = np.array(case["pixels"], dtype=float).reshape(case["height"], case["width"], 3)
        assert core.analyze_rgb(img) == case["expected"], case["name"]
