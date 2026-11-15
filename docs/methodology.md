# Methodology

How HNCS E4 was built and tested. The plan written before any of this is in
[original-design.md](original-design.md); the numbers are in [results.md](results.md); the step-by-step
for re-running it is in [../tools/README.md](../tools/README.md).

## The idea

Phocus renders Hasselblad raws with Hasselblad Natural Colour Solution (HNCS). Capture One's own
X2D II profiles look different: on the test frames the default render was 3.3–4.5 ΔE00 from Phocus,
mostly from darker midtones and shifted hues. Capture One
can't run HNCS, but it can use any camera ICC profile you give it. So the approach is to measure what
Phocus does to each camera colour and store that as a Capture One camera profile.

1. Render the same raws in both apps, with everything that isn't colour or tone switched off.
2. From Capture One, get the exact camera RGB that its camera profile would receive.
3. From Phocus, get the final colour (Lab) of the same pixels.
4. Fit a 33 × 33 × 33 lookup table from the first to the second, and write it as a profile.
5. Render through the new profile in Capture One and compare with Phocus again ("closed loop").

The profile includes Phocus's tone curve, so the style that goes with it sets Capture One's film
curve to Linear Response so tone isn't applied twice.

## What Capture One does with a camera profile

Established by taking apart Capture One 16.9's bundled X2D II profiles and rendering test profiles
(experiment "E0"):

- Camera profiles are ICC v2.4, class `scnr`, RGB → Lab. The table is an `mft2` A2B0 tag: 1025-entry
  input curves, a 33³ grid, and Lab in the legacy 16-bit encoding.
- The neutral axis of the bundled ProStandard profile is a pure gamma-1.8 decode. So the profile
  receives white-balanced camera RGB, gamma-1.8 encoded, and contains no tone curve; tone lives in the
  separate film curve (`.fcrv`).
- Capture One interpolates the table **tetrahedrally**. The fit models it the same way.
- A profile named `HasselbladX2DII100C-<Name>.icm` in `~/Library/ColorSync/Profiles` lists under the
  camera as "Hasselblad X2D II 100C <Name>" after a restart. A byte-for-byte copy of ProStandard renders
  pixel-identical, so user profiles are treated like bundled ones.
- ProStandard carries a private `P100` tag. It only changes the render with the Film Standard curve,
  so the fitted profile leaves it out.
- Light Falloff (lens correction) is applied before the profile.

**The probe profile.** To see exactly what the camera profile receives, `build_probe.py` writes a
profile that treats the camera RGB as ROMM RGB. Render through it, export to ROMM RGB 16-bit, and the
TIFF holds the camera RGB itself. It matches the expected values to about 0.07 ΔE00 from L* 30 up.

## Capturing the two renders

**Phocus 4.2.2** (by hand, per frame): the Standard preset, HDR off, lens corrections off, white
balance As Shot. Export as 16-bit TIFF in ProPhoto RGB. The XCD 28P frames were exported at 100%, and
the XCD 35-100 frames at 50% to save time and disk.

**Capture One 16.9** (scripted with AppleScript, on a clone of each variant): reset adjustments,
probe profile, film curve Linear Response, sharpening and noise reduction 0, Light Falloff,
distortion and sharpness falloff 0. Export 16-bit TIFF in ROMM RGB at the same scale as the Phocus
export.

**The frames.**
- Your own: 10 frames from the XCD 28P and 19 from the XCD 35-100 (35–100 mm, f/8–f/16), mostly
  daylight outdoor scenes, the 35-100 ones picked from a larger shoot to cover as many hues as
  possible. One more was left out because Phocus exported it with its in-camera 65:24 crop.
- From [DPReview's X2D II sample gallery](https://www.dpreview.com/sample-galleries/4239298554/hasselblad-x2d-ii-100c-sample-gallery):
  33 raws, all XCD 35-100, ISO 50–25600, about 18 of them portraits across a wide range of skin
  tones, plus saturated reds, neon, sunsets and warm indoor light. Exported from Phocus at 50%.
  The ISO 25600 frame was dropped as an outlier.

## Pairing

`pairs.py` lines up each Capture One render with its Phocus export (phase correlation, then checked
on 25 tiles; every frame aligned with zero shift) and cuts both into blocks: 32 × 32 px at full size,
or 16 × 16 at half size.

- For Capture One, each pixel's camera RGB is turned into its tetrahedral weights on the 33³ grid,
  and the weights are averaged over the block. A block then says exactly how the table's nodes
  combine to produce the block's average, so averaging doesn't blur the fit.
- For Phocus, each pixel is converted to Lab and averaged over the block.
- Blocks are dropped if any Capture One channel is near clipping, if Phocus clipped or crushed black,
  if L* is under 2, or if they sit more than 50% of the half-diagonal from the centre.

That leaves about 34,000–41,000 blocks per frame.

## The fit

`fit.py` solves for the table L (35,937 nodes × Lab) by sparse least squares:

(WᵀW + λs·DᵀD + λr·I) L = Wᵀ·Lab + λr·Base

- **W**: the block weights. **Lab**: Phocus's block means.
- **D**: second differences along each grid axis, so the table stays smooth where the data is
  thin. λs is picked by cross-validation, leaving one frame out at a time (E3 and E4 both chose 1).
- **Base**: a smooth parametric model (3 × 3 matrix → ProPhoto → a shared monotone tone curve), fitted
  to the same data. A tiny ridge (λr = 0.001) pulls nodes with no data toward it, so colours that
  never appeared in the training frames still get something sensible.
- **Storable range**: Lab in the profile must sit in L* 0–100 and chroma within the encoding. Nodes
  outside are pinned to clipped values (chroma soft-compressed above 90, fading to neutral above
  Phocus's white at L* 95) and the fit is re-solved around them, so the clipping doesn't put kinks
  next to real data.

`write_profile.py` writes the table using the ProStandard header and the same L*-spaced input curves
as the probe, plus a style that sets only the profile and the Linear Response film curve.

E4 trained on 44 frames (7 from your 28P, 14 from your 35-100, 23 from DPReview) and was scored on
17 it never saw (3, 5 and 9). The frames and settings are in `fit/configs/e4.json`.

## Mixing sources

On near-grey blocks, where scene content can't matter, Phocus and the fitted profile disagree by a
different, steady amount for each source: about +0.2 b* on your 35-100, −0.8 on your 28P, +1.0 b*
(and −0.6 a*) on the DPReview frames. Within a source it doesn't follow white balance. The DPReview
raws come from pre-release firmware (1.1.6.3, against 1.3.16.2 on yours), which may be the reason;
see [open-questions.md](open-questions.md).

A plain fit on everything splits the difference and pulls your frames off. So `fit_anchored.py`
gives the DPReview source its own offset, modelled like a white-balance difference
(k · (L* + 16) / 116 per Lab channel, so it vanishes at black), and solves for the table and the offset
together. Your frames set the overall balance; the DPReview frames contribute only where colours sit
relative to grey, which is what adds skin tones and saturated colours. Your two lenses are averaged.

## White balance

Phocus's rendering depends on white balance: Hasselblad told blog.tonalphoto.com that HNCS is
"strongly linked to white balance parameters". Measured here by exporting the DPReview raws twice,
at As Shot and at Daylight: frames between about 4800 and 6500 K score the same, but the three
tungsten-lit frames (about 3400 K) are 1.6–2.1 ΔE00 off at As Shot against 0.5–0.7 at Daylight. So the
profile is for daylight-range white balance.

To pair a Phocus export made at fixed white-balance numbers, Capture One needs the same white
balance. The camera's Daylight preset shows as 5500 K / −0.0033 in Phocus and 5463 K / +2.69 in
Capture One; renders at those settings match the frames whose As Shot is that preset (channel ratio
1.000). `render_probe_all.applescript` takes a temperature and tint for this.

## Edge brightening

Even with lens corrections off, Phocus brightens the image toward the edges. The first profile (E1)
absorbed this as an error that grew with distance from the centre. The fix (E2):

1. Fit a first table, then compare its predictions with Phocus as a function of distance from the
   centre. Convert the lightness gap to stops using the table's own tone slope.
2. Fit lift(r) = c2·r² + c4·r⁴ per lens (r = distance / half-diagonal). It's 0.26 stop at r = 0.6
   for the 28P, but only 0.07 for the 35-100.
3. Apply that gain to the Capture One camera RGB during pairing (`pairs.py --lift`), so the table
   describes the centre of the frame and isn't biased by the edges.

## Matching Phocus with lens corrections on

Most people use Phocus with lens corrections on, which adds a strong vignetting correction. Capture
One's equivalent is Light Falloff, applied before the profile. It was matched empirically: export a
few frames from Phocus with corrections on, render them in Capture One with the fitted profile (E2/E3) at Light Falloff
0, 60, 80, 100 and 120, and score the whole frame including the corners. 120, the maximum, is best for
both lenses (see results). Since it's the same for both, the `+ Light Falloff 120` style sets it. The style leaves the lens curve blank and sets only the amount, so Capture One keeps using the
right lens, focal length and aperture curve.

## Gotchas found along the way

**Phocus**

- The factory TIFF-16 output preset is locked to Adobe RGB. Duplicate it to pick ProPhoto.
- HDR mode produces a PQ-encoded TIFF. Turn it off.
- Modify → Current copies one image's white-balance numbers to every selected image. The Modify
  dialog also starts with every box ticked, so applying a preset to a batch through it copies white
  balance too. Afterwards, check each sidecar's `ColorTemperature`: 0 means As Shot.
- Picking As Shot stores the image's own numbers, and the menu then shows "Custom". That renders the
  same as As Shot (checked: 0.13 ΔE00 between the two).
- Settings live in `<raw>.phos` sidecars (plists). `CurrentIx` picks the active entry, and they're
  only written when you export. `ReferenceSettingName` shows the preset ("Standard+").
- Exports get renamed with a counter (`B_0004_prv.tif`) and may land in a `Previews` subfolder. Each
  sidecar's `ExportName` records which export came from it; `pair_session.py` uses that.
- Raws can carry a BaselineExposure tag (IFD0 50730; 0, +1 or +2 EV on the DPReview frames). Phocus
  and Capture One both apply it, so it needs no handling.

**Capture One**

- New profiles and styles need a restart to appear.
- Reset adjustments turns distortion correction back on. Leave it on for a pixel-level comparison
  against a Phocus export that only corrected vignetting, and fine texture shows up as large ΔE.
- See [../tools/README.md](../tools/README.md) for AppleScript quirks.

## Limits

- **One camera.** The profile only applies to the X2D II 100C.
- **Scenes.** Your frames are daylight outdoor scenes; the DPReview frames add portraits, saturated
  and artificial colours and warm light, but from another body, so their overall balance is
  offset to yours. Colours in neither set follow the smooth base model and are untested.
- **White balance.** Daylight range only (about 4800–6500 K). Tungsten needs its own profile.
- **Lenses.** Phocus renders greys about 1 b* differently on the 28P and the 35-100; the profile
  averages them.
- **Per-frame exposure.** Some frames come out 0.5–1 L* darker than Phocus overall. The cause is
  unknown and a profile can't fix it.
- **Highlights.** Above Phocus's white (L* 95+) the table fades to neutral, and Capture One's
  highlight recovery differs from Phocus's.
- **28P corners.** With lens corrections on, they stay about half a stop darker than Phocus even at
  Light Falloff 120. A flat-field (LCC) shot would fix this.
- **Not modelled.** Phocus HDR mode.

## Ideas for next steps

See [open-questions.md](open-questions.md): per-lens profiles, a tungsten profile, the source offset,
the 28P corners. For each new lens, measure its edge lift (step 6 in the tools README) and run a
Light Falloff check.
