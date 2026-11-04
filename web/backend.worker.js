/* In-browser stand-in for the Django endpoint POST /image-process.
 * Receives the photo's pixels, runs the same pipeline (skintone.js) off the main thread and
 * replies with the same JSON fields the API returns. */
importScripts("skintone.js");

self.onmessage = (e) => {
  const { id, width, height, rgba, region } = e.data;
  const t0 = performance.now();
  try {
    const rgb = new Float64Array(width * height * 3);
    for (let p = 0, q = 0; p < width * height; p++, q += 4) {
      rgb[p * 3] = rgba[q]; rgb[p * 3 + 1] = rgba[q + 1]; rgb[p * 3 + 2] = rgba[q + 2];
    }
    const result = self.SkinTone.analyzeRgb(rgb, width, height, { region, debug: true });
    const debug = result.debug;
    delete result.debug;
    result.face_found = false;
    if (result.rgb) Object.assign(result, { result: result.label, colorR: result.rgb[0], colorG: result.rgb[1], colorB: result.rgb[2] });
    else Object.assign(result, { result: result.label, colorR: null, colorG: null, colorB: null });
    self.postMessage({ id, ok: true, result, debug, ms: Math.round(performance.now() - t0) }, [debug.mask.buffer]);
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message || err) });
  }
};
