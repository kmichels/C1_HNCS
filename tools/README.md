# Tools: refitting or extending the profile

These are the research scripts that produced HNCS E4. They are written for macOS with Capture One
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
| 1 | **Phocus targets.** For each raw: apply the Standard preset, HDR off, lens corrections off, white balance As Shot. Export TIFF 16-bit in ProPhoto RGB. The factory TIFF-16 preset is locked to Adobe RGB, so duplicate it and change the colour space. 100% or 50% both work. Batch changes through the Modify dialog copy white balance unless you untick it. | Phocus UI |
| 2 | **Check the sidecars.** Phocus writes `<raw>.phos` next to each raw when you export. Diff the active settings across frames; only white balance, lens correction, crop and output size should differ. | `phos_diff.py RAW_DIR [RAW_DIR …]` |
| 3 | **Name the exports.** Phocus renames exports (`B_0004_prv.tif` …). Each sidecar's `ExportName` says which export it made, and `pair_session.py` uses that. Without sidecars, match by content. Exports cropped in Phocus (e.g. a 65:24 in-camera crop) can't be paired; skip them. | `match_exports.py PHOCUS_DIR C1_PROBE_DIR` |
| 4 | **Capture One sources.** Render each raw through the probe profile: reset adjustments, film curve Linear Response, sharpening and noise reduction 0, Light Falloff / distortion / sharpness falloff 0. Export TIFF 16-bit ROMM RGB at the same scale as the Phocus export. `render_probe_all` does every image in the open session, optionally at a fixed white balance (to match a Phocus export made at fixed numbers). | `applescript/render_probe_all.applescript 50 Probe [temp tint]` |
| 5 | **Pair.** Align each probe render with its Phocus export and store per-block data: tetrahedral weights for the 33³ grid, Phocus Lab, masks. Use `--block 32` for full-size, `--block 16` for half-size. `--lift c2,c4` removes Phocus's edge brightening (step 6). | `pair_session.py RAW_DIR PROBE_DIR PHOCUS_DIR OUT --block 16 --lift c2,c4` (or `pairs.py` for one frame) |
| 6 | **Edge lift (new lens only).** Pair without `--lift`, measure against a centre-calibrated LUT, then re-pair with the pooled value. | `edge_lift.py fit/lut_e4.npz PAIRS_DIR RAW_DIR FRAME …` |
| 7 | **Fit.** Fits one table on several pairs sets described by a JSON config, then refits inside the range the ICC can store. `fit_multi.py` cross-validates the smoothness; `fit_anchored.py` also gives sets from another camera their own offset so your frames set the overall balance (how E4 was made). | `fit_anchored.py fit/configs/e4.json OUT.npz` |
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
| `fit_anchored.py` | The E4 fit: several sources, an offset per non-anchored source, exact joint solve |
| `fit_multi.py` | Several sources, cross-validated smoothness, no offsets |
| `fit_e3.py` | The E3 fit (your two lenses only), kept for reference |
| `pair_session.py` | Pair a whole session, using the export names in the Phocus sidecars |
| `write_profile.py` | LUT → `HasselbladX2DII100C-<Name>.icm` plus `<Name>.costyle` |
| `edge_lift.py` | Phocus edge brightening per lens |
| `save_phocus_lab.py` | Block Lab of a Phocus export (for corrections-on comparisons) |
| `score_closed_loop.py`, `score_light_falloff.py` | Validation against real Capture One renders |
| `phos_diff.py`, `match_exports.py` | Phocus housekeeping |
| `build_probe.py` | Rebuild the probe profile |
| `applescript/` | Capture One render jobs. Frame lists and recipe names are hard-coded; edit them. |

## Capture One scripting notes

- Always render a **clone** of the variant (`clone variant`) so the original edit is untouched.
- `color profile` takes the display name ("Hasselblad X2D II 100C HNCS E4"), not the file name.
- `delete` on a clone variant removes only that variant. `delete` on an image fails (-10006).
- AppleScript treats `before` and similar words as keywords; don't use them as variable names.
- If Capture One stops answering scripts after a quit request, it's waiting on a confirmation sheet.
- A recipe's `color profile` with a wrong name fails silently. "ROMM RGB" works. Read it back.
- Name the recipe in `process c recipe "…"`; without it Capture One uses whatever recipes are enabled.
- `process` returns immediately. Poll the output folder until the file sizes stop changing.
- `job` is a dictionary class, so `set job to process …` won't compile.
- New profiles and styles appear only after restarting Capture One.
- Reset adjustments turns distortion correction back on. Turn it off when comparing pixel-for-pixel
  with a Phocus export that only corrected vignetting, or fine texture will look like colour error.

## Data

Pairs, renders and exports are large and are not committed (`data/` is git-ignored). `fit/configs/e4.json`
expects `data/pairs_28p_lifted`, `data/pairs_35100_lifted` and `data/pairs_e4_lifted`. Regenerate them with
steps 1–5, or ask the repo owner for the pairs archive.

## Synthetic raws (E5)

Measure Phocus with designed inputs instead of photographs. Background and results:
[../docs/research-log.md](../docs/research-log.md).

**Drive Phocus's hot folder without its GUI.** `phocus_hotfolder.py` does all of this from Python (a
private watch folder under `~/Pictures`, one sidecar per file, preferences restored); the tools below use
it. By hand: quit Phocus, then:

```sh
defaults export dk.hasselblad.phocus phocus-prefs-backup.plist      # keep a copy
defaults write dk.hasselblad.phocus AutoExport -int 1
defaults write dk.hasselblad.phocus exportDirectory -string "$HOME/Pictures/Phocus synth"
open -a Phocus
```

Phocus watches the folder its browser last showed, and exports with the last-used output preset (set a
16-bit ProPhoto TIFF preset once). For each file, copy `<name>.3fr.phos` (a sidecar with the wanted
settings: Standard, HDR off, `LensCorrection` 0 or 4, `ColorTemperature` 0 for As Shot) into the folder
first, then the raw. The export appears in about 10 s, and the sidecar's `ExportName` names it.
Afterwards, restore with `defaults import dk.hasselblad.phocus phocus-prefs-backup.plist`. Don't send
AppleScript to Phocus: it triggers a macOS automation prompt.

| Tool | Purpose |
|---|---|
| `make_synthetic_raw.py HOST.3fr OUT.3fr [--levels 33 --part i/N] [--neutral-from RAW \| --neutral r,g,b] [--flat L]` | Patch grid (or a flat grey) in a copy of a real raw; `--neutral-from` / `--neutral` set white balance |
| `save_synth_pairs.py PATCHES C1_PROBE.tif PHOCUS.tif OUT.npz` | Save a grid's pairs (the `fit/synthetic/pairs/` format) so the renders can be deleted |
| `fit_synthetic.py OUT --gainmap MAP --pairs PAIRS.npz …` | Fit a table from saved pairs (or `--synth` from renders) |
| `applescript/render_probe_all.applescript` and the per-file probe script pattern | Capture One probe renders (camera RGB per patch) |
| `synth_compare.py` | Compare Phocus exports of synthetic files that share a patch layout |
| `makernote_transplant.py TARGET DONOR OUT TAGS` | Copy maker-note entries between raws in place (bisection) |
| `fit_synthetic.py OUT --synth NAME:PATCHES:C1.tif:PHOCUS.tif … --gainmap MAP` | Fit a table on synthetic pairs; score on real pairs |
| `flat_gain.py LUT PHOCUS_FLAT_EXPORT OUT` | Phocus's per-channel spatial gain from a flat-field export |
| `compare_gain_maps.py C1_FLAT_RENDER PHOCUS_MAP` | Capture One's spatial gain (Light Falloff, LCC) vs Phocus's |
| `make_lcc_raw.py HOST OUT --colour MAP` | LCC reference raw that reproduces a colour shading map |
| `write_profile.py … --input-gain r,g,b` | Profile with per-channel input gain (used to undo an LCC's overall shift) |
| `preprocess_folder.py IN_DIR OUT_DIR [--make-maps] [--make-profiles] [--no-sidecars]` | Corrected copies of a whole folder, making missing maps and lens profiles with Phocus; each copy gets a Capture One settings sidecar so it opens with the E5 profile, Linear Response and Light Falloff 0 |
| `auto_lens_profile.py RAW … [--name N] [--install]` | Build an HNCS E5 profile + styles for any lens from its raws, using only Phocus (Capture One's side comes from `fit/c1_patch_lookup.npz`) |
| `preprocess_3fr.py IN OUT --maps DIR` | Corrected copy of a 3FR with Phocus's lens correction and colour shading in the raw ([pre-processing](#pre-processing)) |
| `make_preprocess_map.py FLAT_GAIN FLAT.3fr DIR` | Raw-gain map for a lens state, from Phocus's render of a synthetic flat |
| `auto_maps.py RAW … [--maps DIR]` | Make the missing maps for every lens state among the raws, through Phocus's hot folder (automatic) |
| `phocus_hotfolder.py` | Python helper: render raws in Phocus without its GUI (private watch folder, settings per file, preferences restored) |
| `contact_sheet.py OUT.jpg --row LABEL PHOCUS.tif C1.tif … ` | Side-by-side sheet from finished renders, scored against Phocus |
| `score_render.py PHOCUS.tif C1.tif …` | Score finished Capture One renders against a Phocus export of the same raw (aligned, per block) |
| `highlight_test.py` | Phocus vs Capture One on a synthetic exposure ladder through raw clipping (Finding 23) |
| `body_gains.py RAW` | Read a body's factory calibration gains and print the profile input gain for that body |
| `hncs_structure.py LUT GAINMAP PAIRS…` | Tone curve, model comparison, hue constancy and gamut from synthetic pairs |
| `hncs_wb_structure.py LUT GAINMAP REF_PAIRS PAIRS…` | What changes with white balance: gains, a 3×3 before the table, or a 3×3 after |
| `round3/` | Analyses for Findings 14–16 (response keys, tone-stage space, factory gains) from the saved renders in `data/synth/r3/` |
| `round11/` | Finding 33: bright-colour and exposure-push ladder (`make_ladder.py`), white-balance grids from a Kelvin (`make_wb_grids.py`, `cct.py`), Phocus and Capture One renders (`render_phocus.py`, `render_c1.applescript`, `render_real.applescript`), and `analyze.py`; run from `data/synth/r11/` |

`fit/synthetic/pairs/` holds every synthetic patch's Capture One camera RGB and Phocus output, and
`fit/synthetic/flat_maps/` the flat-field gain maps, so E5 can be refitted without Phocus.

## Pre-processing

Maps for every lens state among some raws, automatically (Phocus is restarted and its preferences
restored; don't use it meanwhile):

```sh
python tools/auto_maps.py ~/Pictures/MySession/Capture/*.3FR
```

By hand, for a lens state that `fit/preprocess_maps/` doesn't have (lens, focal length, aperture and
focus code, which is byte 6 of maker-note 0x0018; the synthetic flat keeps its host raw's; exposure
doesn't matter):

```sh
python tools/make_synthetic_raw.py ANY_RAW_WITH_THAT_LENS_STATE.3fr flat.3fr --flat 30
# render flat.3fr in Phocus with lens corrections on (sidecar LensCorrection 4) via the hot folder above
python tools/flat_gain.py fit/lut_e5_28p.npz PHOCUS_EXPORT.tif flat_gain.npz        # or lut_e5_35-100
python tools/make_preprocess_map.py flat_gain.npz flat.3fr fit/preprocess_maps
```

Then `preprocess_3fr.py IN OUT --maps fit/preprocess_maps` picks the map from the file's metadata. It
also applies Phocus's per-lens-setting brightness: the gain between the map's centre and the map for the
profile's reference setting (`fit/lens_references.json`; `--no-lens-brightness` turns it off).

**Capture One sidecars.** `preprocess_folder.py` writes `OUT_DIR/CaptureOne/Settings<version>/<name>.cos`
before each copy appears. Capture One honours it only for files it hasn't seen before; it needs the image
UUID, `Version`, and a `VAR` with `ProductID` and its own UUID around the settings, or it ignores the file.
