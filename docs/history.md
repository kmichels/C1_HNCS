# History

How the project got to where it is. The current method is in [methodology.md](methodology.md); every
experiment, with its numbers, is in [research-log.md](research-log.md). This page keeps the approaches
that were replaced, so their tools and data still make sense.

| Version | What it was | Replaced by |
|---|---|---|
| E0 | Test profiles and the probe, to learn what Capture One does with a camera profile | still used (the probe) |
| E1 | A table fitted on real photo pairs from the owner's 28P | E2 |
| E2 | E1 with Phocus's edge brightening removed before fitting | E3 |
| E3 | E2 fitted on both of the owner's lenses | E4 |
| E4 | Real photos from the owner's lenses plus DPReview's, with a per-source offset | E5 |
| E5 | Synthetic patches only, at six white balances (Findings 4, 9, 26, 34, 38) | current |

Lens correction went through three routes before the current one:

| Route | Replaced because |
|---|---|
| Light Falloff at 120 with the profile | couldn't follow Phocus's correction across apertures, or its elliptical shape |
| A colour LCC per lens plus Light Falloff 120 (Findings 7, 10) | one LCC per lens can't follow aperture, focal length or focus distance |
| Pre-processing: a corrected copy of each raw (Findings 22, 24, 25, 28) | the settings-file route (Findings 39 to 43) comes within about 0.01 ΔE00 of it overall, without copies |

The plan written before any fitting is in [original-design.md](original-design.md), and the E1 to E4
scores in [results.md](results.md).

## E1 to E4: profiles fitted on real photos

### Capturing the two renders

**Phocus 4.2.2** (by hand, per frame): the Standard preset, HDR off, lens corrections off, white
balance As Shot. Export as 16-bit TIFF in ProPhoto RGB. The XCD 28P frames were exported at 100%, and
the XCD 35-100 frames at 50% to save time and disk.

**Capture One 16.9** (scripted with AppleScript, on a clone of each variant): reset adjustments,
probe profile, film curve Linear Response, sharpening and noise reduction 0, Light Falloff,
distortion and sharpness falloff 0. Export 16-bit TIFF in ROMM RGB at the same scale as the Phocus
export.

**The frames.**
- The owner's: 10 frames from the XCD 28P and 19 from the XCD 35-100 (35–100 mm, f/8–f/16), mostly
  daylight outdoor scenes, the 35-100 ones picked from a larger shoot to cover as many hues as
  possible. One more was left out because Phocus exported it with its in-camera 65:24 crop.
- From [DPReview's X2D II sample gallery](https://www.dpreview.com/sample-galleries/4239298554/hasselblad-x2d-ii-100c-sample-gallery):
  33 raws, all XCD 35-100, ISO 50–25600, about 18 of them portraits across a wide range of skin
  tones, plus saturated reds, neon, sunsets and warm indoor light. Exported from Phocus at 50%.
  The ISO 25600 frame was dropped as an outlier.

### Pairing

`pairs.py` lines up each Capture One render with its Phocus export (phase correlation, then checked
on 25 tiles; every frame aligned with zero shift) and cuts both into blocks: 32 × 32 px at full size,
or 16 × 16 at half size.

- For Capture One, each pixel's camera RGB is turned into its tetrahedral weights on the 33³ grid,
  and the weights are averaged over the block. A block then says exactly how the table's nodes
  combine to produce the block's average, so averaging doesn't blur the fit.
- For Phocus, each pixel is converted to Lab and averaged over the block.
- Blocks are dropped if any Capture One channel is near clipping, if Phocus clipped or crushed black,
  if L* is under 2, or if they sit more than 50% of the half-diagonal from the centre.

That leaves about 34,000–41,000 blocks per frame. E3 and E4 picked the smoothness weight by
cross-validation, leaving one frame out at a time; both chose 1.

### Edge brightening (E1 to E2)

Even with lens corrections off, Phocus brightens the image toward the edges. E1 absorbed this as an
error that grew with distance from the centre. E2:

1. Fit a first table, then compare its predictions with Phocus as a function of distance from the
   centre. Convert the lightness gap to stops using the table's own tone slope.
2. Fit lift(r) = c2·r² + c4·r⁴ per lens (r = distance / half-diagonal).
3. Apply that gain to the Capture One camera RGB during pairing (`pairs.py --lift`), so the table
   describes the centre of the frame and isn't biased by the edges.

| Lens | c2 | c4 | lift at r = 0.6 |
|---|---|---|---|
| XCD 28P | 0.619 | 0.300 | 0.26 stop |
| XCD 35-100 (35–100 mm, about the same throughout) | 0.201 | −0.032 | 0.07 stop |

E5 measures the same thing directly, with a synthetic flat field per lens (`flat_gain.py`).

### Mixing sources (E4)

On near-grey blocks, where scene content can't matter, Phocus and the fitted profile disagreed by a
different, steady amount for each source: about +0.2 b* on the owner's 35-100, −0.8 on the 28P, +1.0 b*
(and −0.6 a*) on the DPReview frames. The DPReview raws turned out to differ by a factory calibration
record in the maker note (Findings 1, 2, 13, 16), which is now corrected per body.

A plain fit on everything split the difference. So `fit_anchored.py` gave the DPReview source its own
offset, modelled like a white-balance difference (k · (L* + 16) / 116 per Lab channel, so it vanishes at
black), and solved for the table and the offset together. E4 trained on 44 frames (7 from the 28P, 14
from the 35-100, 23 from DPReview) and was scored on 17 it never saw. The frames and settings are in
`fit/configs/e4.json`.

### The real-photo pipeline, step by step

| Step | What | Tool |
|---|---|---|
| 1 | **Phocus targets.** For each raw: apply the Standard preset, HDR off, lens corrections off, white balance As Shot. Export TIFF 16-bit in ProPhoto RGB. The factory TIFF-16 preset is locked to Adobe RGB, so duplicate it and change the colour space. Batch changes through the Modify dialog copy white balance unless you untick it. | Phocus UI |
| 2 | **Check the sidecars.** Diff the active settings across frames; only white balance, lens correction, crop and output size should differ. | `phos_diff.py RAW_DIR [RAW_DIR …]` |
| 3 | **Name the exports.** Each sidecar's `ExportName` says which export it made. Without sidecars, match by content. | `match_exports.py PHOCUS_DIR C1_PROBE_DIR` |
| 4 | **Capture One sources.** Render each raw through the probe profile with everything but colour and tone off. | `applescript/render_probe_all.applescript 50 Probe [temp tint]` |
| 5 | **Pair.** `--block 32` for full size, `--block 16` for half size, `--lift c2,c4` to remove edge brightening. | `pair_session.py RAW_DIR PROBE_DIR PHOCUS_DIR OUT --block 16 --lift c2,c4` |
| 6 | **Edge lift (new lens).** Pair without `--lift`, measure against a centre-calibrated table, re-pair. | `edge_lift.py LUT.npz PAIRS_DIR RAW_DIR FRAME …` |
| 7 | **Fit.** `fit_multi.py` cross-validates the smoothness; `fit_anchored.py` adds per-source offsets (E4); `fit_e3.py` is E3. | `fit_anchored.py fit/configs/e4.json OUT.npz` |
| 8 | **Write profile and style.** | `write_profile.py LUT.npz NAME OUTDIR` |
| 9 | **Validate.** Render held-out frames in Capture One and score against Phocus. | `applescript/render_closed_loop.applescript`, `score_closed_loop.py` |
| 10 | **Light Falloff.** Score Capture One at several Light Falloff values against Phocus with lens corrections on. | `save_phocus_lab.py`, `applescript/render_light_falloff.applescript`, `score_light_falloff.py` |

`fit/configs/e4.json` expects `data/pairs_28p_lifted`, `data/pairs_35100_lifted` and
`data/pairs_e4_lifted`, which aren't committed.

## Pre-processing (Findings 22 to 28)

Before the settings-file route, `preprocess_folder.py` wrote a corrected copy of each raw: Phocus's lens
correction and the body's factory gains multiplied into the raw values, and a settings file so the copy
opened with its E5 profile and Light Falloff 0. On 28 unseen photos it scored a median 0.464 ΔE00 against
the settings-file route's 0.473 (Finding 43). It cost a full-size copy per raw and used some highlight
headroom in brightened corners, so it was removed. Its tools and the "(pre-processed)" and LCC styles are
in the git history before Finding 42.
