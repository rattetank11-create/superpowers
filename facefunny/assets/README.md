# Map assets

| File | What it is |
|---|---|
| `source/mirage_radar_source.webp` | The original radar image (input) |
| `mirage_texture.png` | The re-textured map drawn by the app |
| `mirage_mask.txt` | 160×160 walkability grid used for path finding |

Both generated files come from `tools/build_map_assets.py`:

```sh
pip install -r requirements-dev.txt
python tools/build_map_assets.py                 # uses source/mirage_radar_source.webp
python tools/build_map_assets.py other_radar.png # or another top-down radar image
```

The tool crops away the A–P / 1–17 grid labels, finds the floor (anything brighter
than the near-black background), recolours it into the app's dark navy palette
(keeping fine detail such as crates and steps), adds the outline glow and writes
the walkability grid. Nothing is ever downloaded.

Spawn points, sites and lane points for this image live in
`app/map_data.py` (`textured_layout()`). If you rebuild from a different image,
adjust them too. If the assets are missing or broken, the app falls back to its
built-in stylised layout automatically.
