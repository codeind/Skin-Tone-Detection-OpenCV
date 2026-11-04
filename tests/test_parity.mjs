// Checks that browser_backend/skintone.js gives the same result as the Python pipeline.
// Run: node tests/test_parity.mjs
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const SkinTone = require("../browser_backend/skintone.js");
const cases = JSON.parse(readFileSync(new URL("./fixtures/parity.json", import.meta.url)));

let failed = 0;
const close = (a, b, tol) => Math.abs(a - b) <= tol;
for (const c of cases) {
  const got = SkinTone.analyzeRgb(c.pixels, c.width, c.height);
  const exp = c.expected;
  const problems = [];
  if (got.label !== exp.label) problems.push(`label ${got.label} != ${exp.label}`);
  if (got.skin_pixels !== exp.skin_pixels) problems.push(`skin_pixels ${got.skin_pixels} != ${exp.skin_pixels}`);
  if ("ita" in exp) {
    if (!close(got.ita, exp.ita, 0.1)) problems.push(`ita ${got.ita} != ${exp.ita}`);
    got.rgb.forEach((v, i) => { if (!close(v, exp.rgb[i], 1)) problems.push(`rgb ${got.rgb} != ${exp.rgb}`); });
    if (!close(got.cluster_share, exp.cluster_share, 0.001)) problems.push(`share ${got.cluster_share} != ${exp.cluster_share}`);
  }
  if (problems.length) { failed++; console.log(`FAIL ${c.name}: ${problems.join("; ")}`); }
  else console.log(`ok   ${c.name.padEnd(8)} ${got.label}${"ita" in got ? `  ITA ${got.ita}` : ""}`);
}
console.log(`${cases.length - failed}/${cases.length} cases match`);
process.exit(failed ? 1 : 0);
