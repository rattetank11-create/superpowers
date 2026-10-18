# Claude Opus 5.5 — cinematic teaser (9:16)

`claude-opus-5-5-teaser.mp4` — 1080×1920, 15 s, 30 fps, H.264 + AAC stereo.

| Time | Scene |
|------|-------|
| 0–3 s | Deep space, star layers drifting toward the camera, bright particles fade in; "Claude Opus 5.5" resolves from a blur with a soft glow |
| 3–6 s | Push-in to a rotating spiral galaxy: differential rotation, orbiting particles, faint network links and dashed orbit rings |
| 6–9 s | Dive into the galactic core → white flash → minimal Claude prompt bar (logo, typed prompt, model chip, send) |
| 9–12 s | Camera pulls back to reveal a large, slowly rotating Moon with drifting dust; "Claude Opus 5.5" lights up etched into its surface |
| 12–15 s | Sun flare breaks over the lunar limb, end card with logo and title, fade to black |

Everything is procedural — no stock footage or external assets.

## Re-rendering

```bash
python3 audio.py score.wav                       # numpy-only soundtrack
node render.mjs video.mp4 30 0 15                # Playwright + Chromium (WebGL via SwiftShader) -> ffmpeg
ffmpeg -i video.mp4 -i score.wav -c:v copy -c:a aac -b:a 256k -shortest claude-opus-5-5-teaser.mp4
```

`node render.mjs stills/ 30 0 15 1.5` writes PNG stills every 1.5 s for quick previews.
All timings live in `state()` and the DOM section of `render()` in `scene.html`.
