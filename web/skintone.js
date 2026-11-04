/* Skin tone estimation: JavaScript port of skintone/core.py (analyze_rgb).
 *
 * The live demo runs this in a Web Worker in place of the Django API, because GitHub Pages
 * can only serve static files. tests/test_parity.mjs checks that it returns the same result
 * as the Python version for the cases in tests/fixtures/parity.json.
 *
 * Works in a browser, a Web Worker and Node (no dependencies).
 */
(function (root) {
  "use strict";

  const HSV = { h: [0, 25], s: [10, 200], v: [30, 255] };
  const HSV_HUE_WRAP = 175;
  const YCRCB = { cr: [128, 175], cb: [77, 132] };
  const MIN_SKIN_PIXELS = 200;
  const MIN_SKIN_FRACTION = 0.01;
  const K = 3, MAX_SAMPLE = 20000, MAX_ITER = 20, MERGE_DELTA_E = 10;
  const ITA_CATEGORIES = [[55, "Very light"], [41, "Light"], [28, "Intermediate"], [10, "Tan"], [-30, "Brown"], [-Infinity, "Dark"]];

  // ---------- colour conversions (one pixel) ----------
  function rgbToHsv(r, g, b) {
    const v = Math.max(r, g, b), mn = Math.min(r, g, b), d = v - mn;
    const s = v > 0 ? d / v * 255 : 0;
    let h = 0;
    if (d > 0) {
      if (v === r) h = 60 * (g - b) / d;
      else if (v === g) h = 120 + 60 * (b - r) / d;
      else h = 240 + 60 * (r - g) / d;
      if (h < 0) h += 360;
    }
    return [h / 2, s, v];
  }

  function rgbToYcrcb(r, g, b) {
    const y = 0.299 * r + 0.587 * g + 0.114 * b;
    return [y, (r - y) * 0.713 + 128, (b - y) * 0.564 + 128];
  }

  function rgbToLab(r, g, b) {
    const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    const R = lin(r), G = lin(g), B = lin(b);
    const x = (0.4124 * R + 0.3576 * G + 0.1805 * B) / 0.95047;
    const y = (0.2126 * R + 0.7152 * G + 0.0722 * B) / 1.00000;
    const z = (0.0193 * R + 0.1192 * G + 0.9505 * B) / 1.08883;
    const f = (t) => t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116;
    const fx = f(x), fy = f(y), fz = f(z);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
  }

  const ita = (lab) => Math.atan2(lab[0] - 50, lab[2]) * 180 / Math.PI;
  function itaCategory(angle) {
    for (const [lower, label] of ITA_CATEGORIES) if (angle > lower) return label;
    return ITA_CATEGORIES[ITA_CATEGORIES.length - 1][1];
  }

  // Python-style rounding helpers
  function roundHalfEven(x) {
    const f = Math.floor(x), diff = x - f;
    if (diff > 0.5) return f + 1;
    if (diff < 0.5) return f;
    return f % 2 === 0 ? f : f + 1;
  }
  const roundTo = (x, n) => { const m = Math.pow(10, n); return roundHalfEven(x * m) / m; };

  // ---------- 2. mask ----------
  function boxBlur3(rgb, w, h) {
    const out = new Float64Array(w * h * 3);
    const at = (y, x, c) => rgb[(Math.min(h - 1, Math.max(0, y)) * w + Math.min(w - 1, Math.max(0, x))) * 3 + c];
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) for (let c = 0; c < 3; c++) {
      let s = 0;                                  // same summation order as the Python version
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) s += at(y + i, x + j, c);
      out[(y * w + x) * 3 + c] = s / 9;
    }
    return out;
  }

  function open3x3(m, w, h) {
    const get = (a, y, x, fill) => (y < 0 || y >= h || x < 0 || x >= w) ? fill : a[y * w + x];
    const er = new Uint8Array(w * h), out = new Uint8Array(w * h);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      let all = 1;
      for (let i = -1; i <= 1 && all; i++) for (let j = -1; j <= 1; j++) if (!get(m, y + i, x + j, 1)) { all = 0; break; }
      er[y * w + x] = all;
    }
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      let any = 0;
      for (let i = -1; i <= 1 && !any; i++) for (let j = -1; j <= 1; j++) if (get(er, y + i, x + j, 0)) { any = 1; break; }
      out[y * w + x] = any;
    }
    return out;
  }

  function skinMask(smooth, w, h) {
    const m = new Uint8Array(w * h);
    const inside = (a, r) => a >= r[0] && a <= r[1];
    for (let p = 0; p < w * h; p++) {
      const r = smooth[p * 3], g = smooth[p * 3 + 1], b = smooth[p * 3 + 2];
      const [hh, s, v] = rgbToHsv(r, g, b);
      const [, cr, cb] = rgbToYcrcb(r, g, b);
      const hueOk = inside(hh, HSV.h) || hh >= HSV_HUE_WRAP;
      m[p] = hueOk && inside(s, HSV.s) && inside(v, HSV.v) && inside(cr, YCRCB.cr) && inside(cb, YCRCB.cb) ? 1 : 0;
    }
    return open3x3(m, w, h);
  }

  // ---------- 3. k-means (same deterministic start as Python) ----------
  const dist2 = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
  function median(values) {
    const s = Float64Array.from(values).sort();
    const n = s.length, m = n >> 1;
    return n % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  function argmin(arr) { let k = 0; for (let i = 1; i < arr.length; i++) if (arr[i] < arr[k]) k = i; return k; }
  function argmax(arr) { let k = 0; for (let i = 1; i < arr.length; i++) if (arr[i] > arr[k]) k = i; return k; }

  function assign(x, c) {
    const labels = new Int32Array(x.length);
    for (let i = 0; i < x.length; i++) {
      let best = 0, bd = dist2(x[i], c[0]);
      for (let j = 1; j < c.length; j++) { const d = dist2(x[i], c[j]); if (d < bd) { bd = d; best = j; } }
      labels[i] = best;
    }
    return labels;
  }

  function kmeans(x, k = K, maxIter = MAX_ITER) {
    k = Math.min(k, x.length);
    const med = [0, 1, 2].map((c) => median(x.map((p) => p[c])));
    let c = [x[argmin(x.map((p) => dist2(p, med)))]];
    let d = x.map((p) => dist2(p, c[0]));
    for (let t = 1; t < k; t++) {
      const next = x[argmax(d)];
      c.push(next);
      d = d.map((v, i) => Math.min(v, dist2(x[i], next)));
    }
    c = c.map((p) => p.slice());
    for (let it = 0; it < maxIter; it++) {
      const labels = assign(x, c);
      const sums = c.map(() => [0, 0, 0]), n = new Array(k).fill(0);
      for (let i = 0; i < x.length; i++) { const j = labels[i]; n[j]++; for (let q = 0; q < 3; q++) sums[j][q] += x[i][q]; }
      const fresh = c.map((old, j) => n[j] ? sums[j].map((s) => s / n[j]) : old);
      const close = fresh.every((p, j) => p.every((v, q) => Math.abs(v - c[j][q]) <= 1e-8 + 1e-5 * Math.abs(c[j][q])));
      if (close) break;
      c = fresh;
    }
    const labels = assign(x, c);
    const counts = new Array(k).fill(0);
    for (const l of labels) counts[l]++;
    return { centres: c, counts, labels };
  }

  // ---------- full pipeline ----------
  /**
   * rgb: flat array of RGB values (length w*h*3, 0-255).
   * opts.region: [x, y, w, h] to analyse. opts.debug: also return mask, clusters and timings.
   */
  function analyzeRgb(rgb, w, h, opts = {}) {
    if (opts.region) {
      const [rx, ry, rw, rh] = opts.region;
      const crop = new Float64Array(rw * rh * 3);
      for (let y = 0; y < rh; y++) for (let x = 0; x < rw; x++) for (let c = 0; c < 3; c++)
        crop[(y * rw + x) * 3 + c] = rgb[((ry + y) * w + rx + x) * 3 + c];
      rgb = crop; w = rw; h = rh;
    }
    const smooth = boxBlur3(rgb, w, h);
    const mask = skinMask(smooth, w, h);
    let nSkin = 0;
    for (const v of mask) nSkin += v;
    const total = w * h;
    const out = { skin_pixels: nSkin, skin_fraction: total ? roundTo(nSkin / total, 4) : 0 };
    const debug = opts.debug ? { mask, width: w, height: h } : null;
    if (nSkin < MIN_SKIN_PIXELS || nSkin / total < MIN_SKIN_FRACTION) {
      const r = { ...out, label: "No skin detected" };
      if (debug) r.debug = debug;
      return r;
    }
    const all = [];
    for (let p = 0; p < total; p++) if (mask[p]) all.push([smooth[p * 3], smooth[p * 3 + 1], smooth[p * 3 + 2]]);
    const step = Math.max(1, Math.ceil(all.length / MAX_SAMPLE));
    const pixels = all.filter((_, i) => i % step === 0);
    const labPixels = pixels.map((p) => rgbToLab(p[0], p[1], p[2]));
    const { centres, counts, labels } = kmeans(labPixels);
    const top = argmax(counts);
    const same = centres.map((c) => Math.sqrt(dist2(c, centres[top])) < MERGE_DELTA_E);
    const colour = [0, 0, 0];
    let nChosen = 0;
    for (let i = 0; i < pixels.length; i++) if (same[labels[i]]) { nChosen++; for (let q = 0; q < 3; q++) colour[q] += pixels[i][q]; }
    for (let q = 0; q < 3; q++) colour[q] /= nChosen;
    const lab = rgbToLab(colour[0], colour[1], colour[2]);
    const angle = ita(lab);
    const [r, g, b] = colour.map(roundHalfEven);
    const hex = "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
    const result = {
      ...out,
      label: itaCategory(angle),
      ita: roundTo(angle, 1),
      lab: lab.map((v) => roundTo(v, 1)),
      rgb: [r, g, b],
      hex,
      cluster_share: roundTo(nChosen / pixels.length, 3),
    };
    if (debug) {
      debug.clusters = centres.map((c, j) => {
        const s = [0, 0, 0];
        let n = 0;
        for (let i = 0; i < pixels.length; i++) if (labels[i] === j) { n++; for (let q = 0; q < 3; q++) s[q] += pixels[i][q]; }
        return { rgb: n ? s.map((v) => Math.round(v / n)) : [0, 0, 0], share: n / pixels.length, chosen: same[j], lab: c };
      });
      debug.sampled = pixels.length;
      result.debug = debug;
    }
    return result;
  }

  const api = { analyzeRgb, rgbToLab, rgbToHsv, rgbToYcrcb, ita, itaCategory, ITA_CATEGORIES };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SkinTone = api;
})(typeof self !== "undefined" ? self : this);
