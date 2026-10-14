# Optional map image

Drop a top-down radar image named `de_mirage_radar.png` (or `.jpg`, or `mirage.png`)
into this folder and FACEFUNNY draws it under the stylised layout.

The image is never downloaded: only a local file is used. If it is missing or
cannot be decoded, the app falls back to its own built-in Mirage scheme.

Markers follow the built-in layout (`app/map_data.py`), so a third-party image
will only line up if it matches that layout; the built-in outlines stay visible
on top at reduced opacity to keep the paths readable.
