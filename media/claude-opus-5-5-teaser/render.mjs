// Renders scene.html frame by frame (deterministic clock) and pipes PNGs into ffmpeg.
// Usage: node render.mjs <out.mp4|frames-dir> [fps=30] [start=0] [end=15] [step]
// With a directory as the first argument, writes individual PNG stills instead (for previews).
import { spawn, execSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
// Playwright may be installed locally or globally; resolve whichever exists.
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require("playwright")); }
catch { ({ chromium } = require(path.join(execSync("npm root -g").toString().trim(), "playwright"))); }
const [out, fpsArg = "30", startArg = "0", endArg = "15", stepArg] = process.argv.slice(2);
const fps = Number(fpsArg), start = Number(startArg), end = Number(endArg);
const step = stepArg ? Number(stepArg) : 1 / fps;
const stills = !out.endsWith(".mp4");

const browser = await chromium.launch({
  executablePath: process.env.CHROME || undefined,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--allow-file-access-from-files"],
});
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
page.on("pageerror", e => { console.error(e); process.exit(1); });
page.on("console", m => console.log("[page]", m.text()));
await page.goto("file://" + path.join(here, "scene.html"));
await page.evaluate(() => window.ready);
const stage = await page.$("#stage");

let ff;
if (stills) mkdirSync(out, { recursive: true });
else {
  ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "png", "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", out], { stdio: ["pipe", "inherit", "inherit"] });
}

const frames = Math.round((end - start) / step);
const t0 = Date.now();
for (let i = 0; i < frames; i++) {
  const t = start + i * step;
  await page.evaluate(t => window.render(t), t);
  const png = await stage.screenshot({ type: "png" });
  if (stills) {
    const { writeFileSync } = await import("node:fs");
    writeFileSync(path.join(out, `f_${t.toFixed(2).padStart(5, "0")}.png`), png);
  } else if (!ff.stdin.write(png)) await new Promise(r => ff.stdin.once("drain", r));
  if (i % 30 === 0) console.log(`frame ${i}/${frames} t=${t.toFixed(2)} ${((Date.now() - t0) / (i + 1)).toFixed(0)}ms/frame`);
}
if (ff) { ff.stdin.end(); await new Promise(r => ff.on("close", r)); }
await browser.close();
