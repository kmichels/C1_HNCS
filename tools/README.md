# Tools: refitting or extending the profile

These are the research scripts that produced HNCS E3. They are written for macOS with Capture One
16.9 and Phocus 4.2, and for the Hasselblad X2D II 100C. Read [../docs/methodology.md](../docs/methodology.md)
first; this page is the step-by-step.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements.txt
```

Run scripts with `.venv/bin/python -I tools/<script>.py …`.

Install the probe profile once: copy `tools/profiles/HasselbladX2DII100C-E0 Probe.icm` to
`~/Library/ColorSync/Profiles` and restart Capture One. It lists as "Hasselblad X2D II 100C E0 Probe".
Rendering a raw through it and exporting to ROMM RGB 16-bit gives you exactly the camera RGB that
Capture One hands to a camera profile. `build_probe.py` regenerates it.

## Pipeline

| Step | What | Tool |
|---|---|---|
| 1 | **Phocus targets.** For each raw: apply the Standard preset, HDR off, lens corrections off, white balance As Shot. Export TIFF 16-bit in ProPhoto RGB. The factory TIFF-16 preset is locked to Adobe RGB, so duplicate it and change the colour space. 100% or 50% both work. | Phocus UI |
| 2 | **Check the sidecars.** Phocus writes `<raw>.phos` next to each raw when you export. Diff the active settings across frames; only white balance, lens correction, crop and output size should differ. | `phos_diff.py RAW_DIR [RAW_DIR …]` |
| 3 | **Name the exports.** Phocus renames exports (`B_0004_prv.tif` …). Match them to raws by content. Exports cropped in Phocus (e.g. a 65:24 in-camera crop) can't be paired; skip them. | `match_exports.py PHOCUS_DIR C1_PROBE_DIR` |
| 4 | **Capture One sources.** Render each raw through the probe profile: reset adjustments, film curve Linear Response, sharpening and noise reduction 0, Light Falloff / distortion / sharpness falloff 0. Export TIFF 16-bit ROMM RGB at the same scale as the Phocus export. Edit the frame list in the script. | `applescript/render_probe.applescript` |
| 5 | **Pair.** Align each probe render with its Phocus export and store per-block data: tetrahedral weights for the 33³ grid, Phocus Lab, masks. Use `--block 32` for full-size, `--block 16` for half-size. `--lift c2,c4` removes Phocus's edge brightening (step 6). | `pairs.py C1.tif PHOCUS.tif OUT.npz --block 32 --lift c2,c4` |
| 6 | **Edge lift (new lens only).** Pair without `--lift`, measure against a centre-calibrated LUT, then re-pair with the pooled value. | `edge_lift.py fit/lut_e3c.npz PAIRS_DIR RAW_DIR FRAME …` |
| 7 | **Fit.** Cross-validates the smoothness, fits, then refits inside the range the ICC can store. Frame lists for train/test are at the top of the script; edit them for new data. | `fit_e3.py ROOT PAIRS_28P PAIRS_35100 OUT.npz` |
| 8 | **Write profile + style.** | `write_profile.py LUT.npz "HNCS E4" OUTDIR` |
| 9 | **Validate.** Install, restart Capture One, render held-out frames with the new style (Light Falloff 0), score against Phocus. | `applescript/render_closed_loop.applescript`, `score_closed_loop.py` |
| 10 | **Light Falloff.** Export a few frames from Phocus with lens corrections ON, extract their Lab, render in Capture One at several Light Falloff values, score. | `save_phocus_lab.py`, `applescript/render_light_falloff.applescript`, `score_light_falloff.py` |
| 11 | **Contact sheet.** | `contact_sheet.py` |

Measured edge lifts (Phocus, lens corrections off, `--lift` values):

| Lens | c2 | c4 | lift at r = 0.6 |
|---|---|---|---|
| XCD 28P | 0.619 | 0.300 | 0.26 stop |
| XCD 35-100 (35–100 mm, about the same throughout) | 0.201 | −0.032 | 0.07 stop |

## Files

| File | Purpose |
|---|---|
| `icc.py` | Parse and write ICC v2 profiles (`mft2`, legacy 16-bit Lab), Lab/XYZ, CIEDE2000 |
| `tetra.py` | Tetrahedral evaluation of an `mft2` LUT (how Capture One interpolates) |
| `fit.py` | Shaper, sparse tetrahedral weights, smoothness operator, parametric base model, LUT solve |
| `pairs.py` | Align a probe render with a Phocus export and extract block data |
| `render_lab.py` | Block-mean Lab of a Capture One render on a pairs grid |
| `fit_e3.py` | The E3 fit (both lenses) |
| `write_profile.py` | LUT → `HasselbladX2DII100C-<Name>.icm` plus `<Name>.costyle` |
| `edge_lift.py` | Phocus edge brightening per lens |
| `save_phocus_lab.py` | Block Lab of a Phocus export (for corrections-on comparisons) |
| `score_closed_loop.py`, `score_light_falloff.py` | Validation against real Capture One renders |
| `phos_diff.py`, `match_exports.py` | Phocus housekeeping |
| `contact_sheet.py` | The comparison image in the README |
| `build_probe.py` | Rebuild the probe profile |
| `applescript/` | Capture One render jobs. Frame lists and recipe names are hard-coded; edit them. |

## Capture One scripting notes

- Always render a **clone** of the variant (`clone variant`) so the original edit is untouched.
- `color profile` takes the display name ("Hasselblad X2D II 100C HNCS E3"), not the file name.
- A recipe's `color profile` with a wrong name fails silently. "ROMM RGB" works. Read it back.
- Name the recipe in `process c recipe "…"`; without it Capture One uses whatever recipes are enabled.
- `process` returns immediately. Poll the output folder until the file sizes stop changing.
- `job` is a dictionary class, so `set job to process …` won't compile.
- New profiles and styles appear only after restarting Capture One.
- Reset adjustments turns distortion correction back on. Turn it off when comparing pixel-for-pixel
  with a Phocus export that only corrected vignetting, or fine texture will look like colour error.

## Data

Pairs, renders and exports are large and are not committed (`data/` is git-ignored). Regenerate them
with steps 1–5, or ask the repo owner for the pairs archive.
