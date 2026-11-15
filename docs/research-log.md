# Research log: reverse-engineering Phocus with synthetic raws

Working notes for a later write-up. Dated entries, newest last. Numbers are ΔE00 (CIEDE2000) unless
stated; "greys" means near-neutral patches or blocks. Camera: Hasselblad X2D II 100C; Phocus 4.2.2 (Mac);
Capture One 16.9.

**In plain terms:** Phocus can't be scripted and doesn't document its colour science (HNCS). So the
approach was to feed it raw files whose content is known exactly, and measure what comes out. X2D II
raws store the sensor data uncompressed, so a real raw can be copied and its picture replaced with
patches of known colour. That answered questions real photos couldn't: why two cameras render
differently in Phocus, what Phocus does at the edges of the frame, and how its colour changes with
white balance. It also produced better Capture One profiles than fitting to real photos did.

## Background (before 2026-11-15)

**In plain terms:** Before this, profiles were fitted by rendering real photos in both apps and
matching them. That got within about 0.7 ΔE00 (hard to see), but left puzzles: frames from another
camera rendered slightly differently, and the edges of the frame never quite matched.

- E1–E3: Capture One camera profiles (33³ RGB→Lab LUT) fitted to Phocus renders of real frames, owner's
  XCD 28P and XCD 35-100. E3 held-out ≈ 0.7–0.8.
- E4 (2026-11-15): added 33 sample raws from DPReview's X2D II gallery (portraits, saturated colours).
  Phocus rendered DPReview greys about +1.0 b*, −0.6 a* differently from the owner's frames (relative to
  the same Capture One input). E4 fitted a per-source offset so the owner's frames set the balance.
- Found along the way:
  - Phocus colour depends on white balance: one transform holds ~4800–6500 K; tungsten (~3400 K) is
    1.6–2.1 off.
  - BaselineExposure (IFD0 50730, 0/+1/+2 EV on DPReview raws) is applied by both apps.
  - Phocus 4.2.x Modify dialog starts with all boxes ticked, so batch-applying a preset copies white
    balance (this produced a Daylight-WB export of 25 frames by accident; it was used as a second data set).

## 2026-11-15: synthetic raws

### Raw format facts (X2D II 3FR, firmware 1.1.6.3 and 1.3.16.2)

**In plain terms:** An X2D II raw is a TIFF file holding a small preview and the full sensor readout as
plain, uncompressed 16-bit numbers. So new sensor data can be written into a copy of a real file while
everything else (camera, lens, white balance) stays as it was.

- TIFF container, little-endian. IFD0 holds a 3888×2918 JPEG preview plus DNG-style tags:
  AsShotNeutral, ColorMatrix1, BaselineExposure, BaselineExposureOffset (−0.02), CameraSerialNumber,
  UniqueCameraModel, RawDataUniqueID.
- One SubIFD holds the raw: 11904 × 8842, uint16, **uncompressed** (Compression 1, CFA photometric 32803),
  a single strip at file offset 32768 (210,510,336 bytes).
- BlackLevel 4096, WhiteLevel 64762/64763, DefaultCropOrigin (128, 96), DefaultCropSize 11656 × 8742,
  MaskedAreas present (optical black borders).
- CFA **RGGB** from the raw origin (red at even row, even column). First attempt assumed GBRG from a
  sample window that started on an odd row; Capture One's render showed swapped channels, which caught it.
- ColorMatrix1 is identical across the two bodies examined.

### Method

**In plain terms:** Each test file is a real raw with its picture replaced by a grid of flat colour
squares. Capture One shows exactly what camera colour it reads for each square, and Phocus shows what it
turns that colour into. Phocus has no scripting, but its "hot folder" exports any raw dropped into a
watched folder, and it can be switched on from the command line, so the loop runs unattended.

- `tools/make_synthetic_raw.py HOST.3fr OUT.3fr`: copies a real raw and overwrites the active area with
  flat 32 px patches of chosen white-balanced camera RGB (using the host's AsShotNeutral to set raw
  values), on an L* 50 grey background. Masked borders and all metadata kept; RawDataUniqueID changed.
  Patch values spaced evenly in L* per channel (22 or 33 levels). Patches placed in a central square,
  shuffled, within ~0.32–0.34 of the half-diagonal.
- Capture One renders it through the probe profile (device RGB = ROMM) → exact camera RGB per patch.
  Check: channel correlation 0.999 with intended values, greys exactly neutral, patches flat to ~0.15%.
  Capture One's Linear Response maps raw linearly with a gain ≈ 0.75 above the shadows and lower gain in
  deep shadows; raw white ≈ device 0.89 (γ1.8 encoded).
- Phocus renders it via its **hot folder**, driven without the GUI:
  - preferences domain `dk.hasselblad.phocus`: `AutoExport = 1`, `exportDirectory = <folder>`,
    `lastOutputPreset` = the ProPhoto 16-bit preset; quit Phocus, write prefs, relaunch;
  - Phocus watches the folder its browser last showed;
  - drop `<name>.3fr.phos` (sidecar with the wanted settings) first, then the raw; export appears in
    ~10 s (in a `Previews` subfolder, renamed with a counter; the sidecar's `ExportName` records it);
  - minimal sidecar: one `ImageSettings` entry from a real sidecar (Standard, HDR off, LensCorrection 0,
    ColorTemperature 0 = As Shot), new GUID, `ImageParameterCache` dropped, XML plist.
  - Phocus renders the patches perfectly flat (std ~1/65535): no local processing interferes.
- Scripting Phocus with AppleEvents triggers a macOS Automation prompt; avoided entirely.

### Finding 1: the DPReview offset comes from file metadata, not scene content

**In plain terms:** The same synthetic picture renders slightly differently in Phocus depending on which
camera's file it sits in: a small, even colour shift. So it comes from the file's metadata, not from
what was photographed. Capture One renders both identically.

Same synthetic patches written into a DPReview raw and into the owner's 35-100 raw (white balance nearly
identical, AsShotNeutral within 0.4%):

| Phocus output, same pixels | median ΔE00 | greys dL / da / db |
|---|---|---|
| owner's 35-100 host − DPReview 35-100 host | 0.34 | +0.38 / −0.66 / +0.74 |

Capture One's input was identical (|Δdevice| < 0.0001): Capture One ignores whatever differs.

### Finding 2: it's one factory calibration value in the maker note

**In plain terms:** Swapping metadata between files one piece at a time narrowed the cause to a single
4-byte value: two numbers in a factory calibration record that each camera writes into every raw.
Phocus uses them to make every body render alike; Capture One ignores them. So a Capture One profile is
tied to the camera it was made on, and other X2D IIs may differ slightly.

Fields differing between the hosts: Software (firmware), CameraSerialNumber, MakerNote (29,840 vs 23,188
bytes), trivially AsShotNeutral and WhiteLevel. Transplants into an otherwise identical file:

- firmware string: no effect (byte-identical output); serial: no effect.
- MakerNote: a TIFF IFD (59/62 entries) with absolute offsets. Same-size entries swapped in place:
  - all swappable entries: reproduces the colour shift (greys a*/b* within 0.03), lightness half way;
  - first group (0x0005, 0x000f, 0x0017, 0x0019, 0x0042, 0x0047, 0x004b, 0x0060, 0x0061, 0x0063): same;
  - second group (0x0064–0x007e, large blocks): no effect;
  - ID strings 0x0060/0x0061 (sensor/lens IDs?): no effect; numeric fields: no effect;
  - **0x0019 alone: full colour shift.** 0x0017, 0x0042, 0x004b: no effect.
- **0x0019** (512 bytes) is a factory calibration record: starts with ASCII `GAIN`; contains a date
  (DPReview body 2025-05-05, owner's 2025-11-21), tool string `isctool 4.0.50` / `4.0.51`, a sensor ID string, and a trailing checksum-like block. It is identical across every
  owner frame (two lenses, Sep–Oct 2026), so per body, not per shot.
- Byte-level: only bytes 84–87 matter (copying date, ID and checksum alone: no effect; Phocus doesn't
  validate). Those 4 bytes are **two IEEE half-floats**: owner (2.600, 2.260), DPReview (2.363, 2.518).
  Sweep: 0 → mild shift (likely "no calibration" fallback); arbitrary floats decoding to garbage halves →
  huge green cast. Reading: per-body channel sensitivity gains (probably R/G and B/G at a reference
  illuminant) that Phocus uses to normalise every body to a reference. Capture One ignores them, so a
  Capture One profile is inherently per body.
- Unexplained remainder: ~0.2 L* of lightness between the two hosts, in maker-note entries that can't be
  swapped in place (pre-release-only 0x0072/0x0073; newer focus fields 0x0081–0x0083).

### Finding 3: lens metadata changes Phocus's rendering (lens corrections off)

**In plain terms:** The same picture tagged as shot with the XCD 28P comes out slightly darker in Phocus
than when tagged as the XCD 35-100, even with lens corrections turned off. Phocus applies some
lens-specific processing whatever that setting says.

Same patches, owner's body, XCD 28P host vs XCD 35-100 host; then the 28P host with its AsShotNeutral
set equal to the 35-100 host's:

| Phocus − E4 on greys | dL | da | db |
|---|---|---|---|
| 35-100 host | +0.52 | −0.11 | −0.20 |
| 28P host, own WB | −0.27 | −0.05 | +0.26 |
| 28P host, 35-100's WB | −0.27 | −0.12 | +0.02 |

So at the frame centre the lens changes brightness by about −0.8 L* (28P darker), with little colour.

### Finding 4: E5, a profile fitted on synthetic patches only

**In plain terms:** A profile fitted only on synthetic squares, with no real photos at all, matched real
photos as well as the previous best profile on the 35-100. On the 28P it did worse, which led to the
next finding.

33³ colours per lens, 3 files each, hosted in the owner's raws (35-100: B0000727; 28P: B0000931); ~33,000
usable patches per lens; edge lift removed per patch with each lens's measured lift.

| Owner's real frames (none used in E5) | E5 synthetic only | E4 |
|---|---|---|
| 35-100 held-out (623, 679, 703, 829, 863) | 0.71 | 0.71 |
| 28P held-out (912, 929, 939) | 1.08 | 0.82 |

Synthetic fit residual median 1.0, p90 7.1, dominated by extremely saturated patches beyond what the
legacy Lab encoding and the storable range allow.

### Finding 5: Phocus applies radial colour shading even with lens corrections off

**In plain terms:** Phocus warms the image toward the edges of the frame, strongly with the 28P and
mildly with the 35-100, even with lens corrections off. A camera profile treats every part of the
frame the same, so it can't do this. This explains most of the "colour difference between the two
lenses" seen earlier.

E5 minus Phocus on the owner's real frames, by distance from the centre (fraction of the half-diagonal):

| r | 28P dL / da / db | 35-100 dL / da / db |
|---|---|---|
| 0.0–0.1 | −0.09 / −0.25 / +0.07 | +0.14 / −0.13 / +0.27 |
| 0.2–0.3 | −0.10 / −0.30 / −0.59 | +0.15 / +0.02 / −0.04 |
| 0.4–0.5 | −0.30 / −0.49 / −1.76 | +0.24 / +0.20 / −0.44 |
| 0.5–0.6 | −0.42 / −0.56 / −2.44 | +0.29 / +0.28 / −0.72 |

At the centre E5 matches real photos within ~0.25 per channel; outward, Phocus adds yellow (and a little
red): +2.4 b* by r 0.55 on the 28P, ~+1 on the 35-100. Likely the per-lens "blue-corner shading" data in
the camera's lens files (reported by blog.tonalphoto.com in firmware 1.3.16.1/1.3.18.1), applied even
with lens corrections off. This is most of the "1 b* grey difference between the two lenses" seen in
real-image fits, which average over the frame. Scene-cast options in the sidecar are all off
(ApplySceneCastCorrection, ApplySceneEqualization, ApplySceneCalibration = False), so it isn't
scene-adaptive.

### Next

- Measure Phocus's spatial shading directly with synthetic flat fields per lens / aperture / focus,
  lens corrections off and on.
- Encode it as a Capture One LCC (flat-field) made from a synthetic raw, so Capture One reproduces
  Phocus's spatial behaviour; per-lens E5 profiles then only need to describe the centre.

### Finding 6: Phocus's spatial processing, measured with synthetic flat fields

**In plain terms:** Rendering a perfectly even grey file shows exactly what Phocus does across the frame.
It brightens the edges a little with corrections off and a lot with them on, and either way it reduces
blue toward the edges. The colour part barely changes with aperture; the brightness part (with
corrections on) depends on aperture and focal length.

Uniform L* 45 grey written into six host raws (35-100 at 35 mm f/11, 100 mm f/11, 45 mm f/8; 28P f/8 ∞,
f/4 ∞, f/4 0.3 m), each exported twice: sidecar `LensCorrection` 0 (off) and 4 (vignetting on). Phocus's
output inverted per 64 px block through the centre-accurate E5 LUT gives its per-channel gain map
(`tools/flat_gain.py`). Inversion residual 0.000 except a few clipped corners in the f/4 "on" renders.

At r = 0.6 (fraction of the half-diagonal):

| | 28P f/8 | 28P f/4 | 35-100 @35 | 35-100 @45 | 35-100 @100 |
|---|---|---|---|---|---|
| off: green gain (stops) | +0.245 | +0.191 | +0.056 | +0.050 | +0.007 |
| off: B−G (stops) | −0.104 | −0.102 | −0.034 | −0.028 | −0.022 |
| on: green gain | +0.910 | +1.182 | +0.333 | +0.253 | +0.095 |
| on: B−G | −0.101 | −0.096 | −0.033 | −0.027 | −0.021 |

At r = 0.9: 28P off +0.76 st (B−G −0.19), on +2.02 st at f/8 / +2.29 at f/4; 35-100 @35 on +0.84 st.

- Colour shading (blue reduced toward the edges, red slightly raised) is the same with corrections
  on or off, nearly aperture- and focus-independent on the 28P (B−G at r 0.9: −0.16 f/8, −0.22 f/4),
  and eases with focal length on the 35-100. On L* 45 grey it is +5 b* at r 0.6 on the 28P.
- With corrections off, Phocus still lifts brightness (28P +0.25 st at r 0.6; 35-100 +0.06 at 35 mm):
  matches the lift estimated from real frames (0.26 / 0.07).
- With corrections on, the brightness correction depends on aperture and focal length.
- Mild left/right and top/bottom asymmetries (~0.1 stop at the edges of the 28P map).

### Finding 7: Capture One's Light Falloff vs Phocus, and a synthetic LCC

**In plain terms:** Capture One's Light Falloff changes brightness only. At its maximum it matches Phocus
on the 35-100 and on the 28P at f/4, but not on the 28P at smaller apertures. The colour part can be
reproduced with an LCC (Capture One's flat-field correction): a synthetic LCC reference built from
Phocus's measurements does it, once its strength is corrected.

Capture One renders of the same flat fields through the probe profile (`tools/compare_gain_maps.py`):

- Light Falloff is brightness only (B−G exactly 0).
- vs Phocus corrections on, at LF 120, brightness difference at r 0.6 / 0.8 / 0.9:
  - 35-100 @35: +0.015 / −0.045 / −0.042; @45: +0.003 / −0.037 / −0.026; @100: +0.013 / −0.028 / +0.004.
  - 28P f/8: −0.12 / −0.30 / −0.40; f/4 ∞: +0.03 / −0.05 / −0.07; f/4 0.3 m: −0.01 / −0.12 / −0.14.
  So LF 120 matches the 35-100 and the 28P at f/4; the 28P at f/8 needs ~0.4 stop more at the corners.
  Phocus and Capture One scale vignetting correction with aperture differently.
- Synthetic LCC (`tools/make_lcc_raw.py`): reference raw = host metadata with pixel values set to the
  inverse of the wanted per-channel gain (2-D degree-6 polynomial fit to Phocus's map, rms 0.002 stop).
  Created as an LCC in Capture One by script (`create LCC`, `apply LCC`, `LCC color cast` on,
  `LCC uniform light` off).
- Result: Capture One reproduces Phocus's colour shading in shape at every radius but ~14% too strongly
  (B−G −0.119 vs −0.104 at r 0.6 on the 28P; −0.039 vs −0.034 on the 35-100). Scale the wanted colour map
  by ~0.875.

### Finding 8: Phocus's colour depends on white balance even within daylight

**In plain terms:** Phocus's colour changes with white balance even between ordinary daylight settings. A
profile fitted at one white balance is excellent near it and less good on warmer or cooler shots.

E5b (synthetic grid at one host white balance, Phocus gain maps applied to the patches) scored at the
frame centre (r < 0.2, per-pixel tetrahedral weights) on every owner frame: 0.25–0.65 on most, but
0.8–1.2 on the warmest-balanced frames. Across frames, centre error vs |log(B/R neutral ratio relative
to the host)|: correlation +0.74 (da, db also correlate, +0.63 / +0.59). A ~25% change in the B/R
balance (e.g. B/R 1.32 vs 1.74 on the 28P) costs ~0.5–1 ΔE00. HNCS is "strongly linked to white balance
parameters" (Hasselblad, via blog.tonalphoto.com), and that holds inside 4700–6300 K too.

White balance can be set synthetically: write another frame's AsShotNeutral into IFD0 and the maker-note
copy (0xc628). Capture One reads it (As Shot 4667 K … 6306 K for the five chosen neutrals); Phocus does
too (its grey patches stay at a* −1.3, b* +0.4–0.5 across all five, i.e. consistently white-balanced; HNCS
renders neutral grey slightly green).

### Finding 9: E5c, synthetic only, at six white balances

**In plain terms:** Fitting across six white balances, still from synthetic data only, gives the best
profiles so far. They beat the profile fitted to real photos on photos neither ever saw.

Per lens: the 33³ grid at the host white balance plus 22³ grids at five owner frames' neutrals (926, 939,
701, 746, 901: B/R from 1.32 to 1.86); ~82,000 patches; Phocus gain map (corrections off, same host)
applied per patch; one LUT. No real photos used.

| Frame centre (r < 0.2), median ΔE00 | E5c | E5b | E4 |
|---|---|---|---|
| 35-100, all 19 frames | 0.52 | 0.56 | 0.55 (mostly its training frames) |
| 35-100, E4's held-out 5 | 0.52 | — | 0.72 |
| 28P, all 10 frames | 0.59 | 0.68 | 0.69 |
| 28P, E4's held-out 3 | 0.50 | — | 0.69 |
| warmest frames 917 / 926 / 939 | 0.92 / 0.92 / 0.57 | 1.11 / 1.17 / 0.80 | — |

Synthetic fit residual median rises to ~1.5 because one LUT can't follow the white-balance dependence
exactly; it settles on the average, which is what a single Capture One profile can do.

### Finding 10: how Capture One's LCC colour correction works, and the full chain on real photos

**In plain terms:** Capture One's LCC shifts the colour of the whole image, not just the edges, because
it corrects relative to the reference's average colour. Building the opposite shift into the profile
cancels it. With that, the combination of a per-lens profile, Light Falloff 120 and a colour LCC
matches Phocus better than before across the whole frame. What remains on the 28P is edge brightness at
f/5.6 and narrower.

- Capture One's LCC colour correction, measured on synthetic references:
  correction_c(x) = (mean of reference_c / reference_c(x))^1.14, per channel relative to green.
  Check: 28P reference blue mean/centre 1.0675 → predicted centre gain 1.0773, measured 1.0774;
  red 0.9665 → 0.9619 predicted, 0.9616 measured. So beyond the 14% overshoot, the LCC also shifts the
  whole image by the reference's mean colour (a white-balance-like shift), which no reference pattern can
  avoid (scaling the reference cancels).
- Compensation: profile variants for use with the LCC ("HNCS E5 28P LCC", "HNCS E5 35-100 LCC") with the
  exact inverse per-channel gain in the ICC input curves (`write_profile.py --input-gain`):
  28P R 1.0365, B 0.9380; 35-100 R 1.0028, B 0.9830. The LUT itself is unchanged.
- Final colour LCC references: mean of the landscape-host corrections-off maps (28P: f/8 and f/4;
  35-100: 35 mm and 100 mm), colour part only, scaled by 0.875; written into a host raw of the same lens.
- Full chain vs Phocus with lens corrections ON, real photos, whole frame (r < 0.95), median ΔE00:

| frame | E4 + LF 120 | E5 (LCC variant) + LF 120 + colour LCC |
|---|---|---|
| 28P B0000901 (f/16) | 2.19 | 1.56 |
| 28P B0000917 (f/5.6) | 2.11 | 1.56 |
| 28P B0000931 (f/8) | 2.37 | 1.43 |
| 35-100 B0000623 (35 mm f/11) | 1.08 | 0.76 |
| 35-100 B0000679 (35 mm f/11) | 1.10 | 0.69 |
| 35-100 B0000702 (50 mm f/8) | 0.65 | 0.73 |
| mean 28P / 35-100 | 2.23 / 0.94 | 1.51 / 0.73 |

  By radius, 35-100 corners (r 0.8–1.0) went from 1.2–1.6 to 0.7–0.9; 28P edge colour error (db) from
  −6/−7 to −0.2/−2.8. The 28P's remaining error is brightness at the edges (dL −3 to −7 at r 0.6–1.0)
  at f/5.6–f/16, where Light Falloff 120 under-corrects (Finding 7).
- First attempt without the compensating input gain was worse than E4 (28P 3.40): the LCC's global shift
  made the centre −3.5 b* too blue. The flat-field test had hidden it by normalising to the centre.

### Finding 11: what HNCS is made of

**In plain terms:** For everyday colours, HNCS behaves mostly like a classic camera profile: a colour
matrix followed by a tone curve applied to each channel separately (not a "hue-preserving" curve). That
alone gets within about 1 ΔE00. The rest is genuinely three-dimensional, so colour adjustments depend
on brightness too, and saturated colours are reshaped in ways no simple model follows. Phocus's
film-curve setting changes only the tone curve: Standard and a brighter alternative share the same
colour. (Correction, Finding 19: that alternative isn't the Reproduction response.)

35-100, host white balance, ~33,000 synthetic patches with Phocus's spatial gain removed; simple
models fitted on camera-RGB saturation < 0.6 (s = 1 − min/max of white-balanced camera RGB), scored on
held-out patches (median ΔE00):

| model | s 0–0.3 | 0.3–0.6 | 0.6–0.85 | 0.85–1 |
|---|---|---|---|---|
| A 3×3 matrix → ProPhoto → one tone curve per channel | 1.02 | 1.05 | 2.87 | 6.94 |
| B 3×3 matrix → tone curve on luminance (hue-preserving) | 3.05 | 3.74 | 5.85 | 7.48 |
| C A + 2.5-D hue/saturation table (36 hue × 10 chroma bins) | 0.84 | 0.83 | 2.79 | 6.93 |
| D full 33³ LUT | 0.43 | 0.27 | 0.52 | 1.34 |

- Neutral tone curve (camera green linear, Capture One's scale, where 0.18 ≈ middle grey): L* 24 at
  −3 EV, 38 at −1.8, 52 at −1.0, 73 at +0.15, 90 at +1.2, 97 at +1.7, 99 at +2.0. HNCS greys sit at
  a* −0.6 to −1.8 (slightly green).
- Hue when a colour is brightened 1 and 2 stops (same camera RGB ratios): red, yellow, cyan, blue,
  magenta within ±1.5°; green −3.5°; orange and skin +6–7° as they approach the highlights.
- 6% of all synthetic patches (all extreme) come out with a ProPhoto channel clipped at 0; none at full
  scale. Output chroma reaches C* 175.
- Sidecar `FilmCurve` (Standard = 4): values 1–5 render identically; 0 renders about a stop brighter in
  the midtones with a gentler highlight roll-off (grey L* 57.9 vs 43.6; 88.0 vs 80.2), with chroma
  unchanged (median ratio 1.004). I took this for the blog's Reproduction response; Finding 19 shows
  Reproduction is `ColorModel` 1, and `FilmCurve` 0 is the film-curve menu's "As Shot".

### Finding 12: no focus-distance dependence on the 28P; an exposure tag mimics one

**In plain terms:** Two real 28P frames at f/4, one focused at infinity and one at 0.24 m, got
slightly different vignetting correction in Phocus, which looked like focus mattering. It was
the exposure tag: one file carries BaselineExposure +0.76. Swapping just that tag swaps the
correction maps exactly. Phocus's correction shrinks slightly as the image gets brighter.

Synthetic L* 45 flat fields, lens corrections on (vignetting), hosts B0000939 (28P f/4, 0.24 m,
BaselineExposure +0.764) and B0000926 (28P f/4, ∞, BaselineExposure 0); green gain at r 0.4 / 0.6 / 0.7:

| file | gain (stops) |
|---|---|
| near focus, own BE (+0.764) | +0.562 / +1.126 / +1.484 |
| far focus, own BE (0) | +0.590 / +1.184 / +1.569 |
| near focus, BE set to 0 | +0.591 / +1.184 / +1.569 |
| far focus, BE set to +0.764 | +0.561 / +1.126 / +1.483 |

- No effect at all (byte-identical output) from: maker-note focus fields 0x0081–0x0083 transplanted
  from the far file; EXIF SubjectDistance set to infinity. This confirms blog.tonalphoto.com's finding
  that Phocus ignores these.
- Transplanting every same-size maker-note entry from the far file: no change within r ≤ 0.6 (corners
  of the near file clip at +0.76 EV, so not comparable there).
- The correction's effective gain is ~0.06 stop smaller at r 0.6 when the image is 0.76 EV brighter.
  (Correction, Finding 22: that's Capture One's raw response, which the gain map is measured through;
  as raw gains the two are identical.)
- The blog's focus-distance dependence was measured on the XCD 55V and 90V. This doesn't contradict it,
  but exposure differences between frames (BaselineExposure) can look like a focus effect.

### Finding 13: how Phocus uses the factory gains, and per-body profiles

**In plain terms:** The two calibration numbers each camera stores (Finding 2) act like small
adjustments to how strongly Phocus reads the blue and green channels. A sweep of synthetic files with
different values gave a simple formula. With it, a profile made on one camera can be adjusted for any
other X2D II from a single raw of that camera, and tested on 32 photos from another body it removes
that body's colour offset.

Owner's 35-100 synthetic grid (host white balance) with the two half-floats changed one at a time.
For each, the camera-RGB multipliers (G fixed at 1) that make the E5 table reproduce Phocus's new
output:

| gains (g1, g2) | greys Δa* / Δb* | kR | kB | residual after fit |
|---|---|---|---|---|
| 2.200, 2.260 | +0.91 / −0.63 | 1.0118 | 1.0147 | 0.66 → 0.23 |
| 2.400, 2.260 | +0.45 / −0.31 | 1.0058 | 1.0072 | 0.33 → 0.11 |
| 2.800, 2.260 | −0.45 / +0.32 | 0.9942 | 0.9928 | 0.33 → 0.12 |
| 3.000, 2.260 | −0.90 / +0.63 | 0.9884 | 0.9859 | 0.65 → 0.23 |
| 2.600, 1.960 | −0.25 / +0.64 | 1.0000 | 0.9890 | 0.35 → 0.03 |
| 2.600, 2.460 | +0.15 / −0.38 | 1.0000 | 1.0064 | 0.20 → 0.02 |
| 2.600, 2.660 | +0.30 / −0.74 | 0.9999 | 1.0128 | 0.40 → 0.03 |

- Second value: a pure blue multiplier, ln kB = 0.0775 · ln(g2 / 2.260).
- First value: mostly an inverse green multiplier (red and blue together), ln kR = −0.0705 · ln(g1 / 2.600),
  ln kB = −0.0875 · ln(g1 / 2.600).
- The effect is weak (a 15% change in a stored value moves a channel ~1%), so the stored numbers aren't
  used as raw sensitivity ratios directly.
- Prediction for the DPReview body (2.363, 2.518): kR 1.0068, kB 1.0169. Applied to E5 on 32 DPReview
  photos (frame centre): grey offset a*/b* −0.52/+0.53 → −0.08/−0.03; median 1.23 → 1.02 (held-out 9:
  1.02 → 0.95).
- `tools/body_gains.py RAW` reads a raw's record and prints the profile input gain for that body.

## 2026-11-15 (round 3): closing the gaps

Scripts: `tools/round3/` (they read the saved measurements in the local `data/synth/r3/`),
`tools/hncs_structure.py`, `tools/hncs_wb_structure.py`. Logs: `data/logs/r3_*.txt`,
`data/logs/hncs_structure_*.txt`, `data/logs/hncs_wb_structure_*.txt`.

### Finding 14: HNCS is a colour stage, then a tone curve per channel in "Hasselblad RGB"

**In plain terms:** Phocus first converts the camera's colour, then applies its tone curve to each
channel separately in an RGB space of Hasselblad's own, whose definition ships inside Phocus as
`Hasselblad RGB.icc`. Knowing the space, a colour matrix plus that tone curve explains saturated colours
far better than before; what's left is a 3D colour table that also depends on lightness. Those are the
building blocks of a Lightroom (DNG) profile, except Lightroom applies its tone curve in a different
space and in a different way. White balance changes the colour matrix, like a DNG profile with two
calibration illuminants. The 28P and the 35-100 behave the same.

**Stage order.** The owner's 35-100 grid rendered with sidecar `FilmCurve` 0 (a brighter response) and 4
(Standard). Each model tries to produce the FilmCurve 0 render from the Standard render; median ΔE00 on
moderate | saturated colours (camera-RGB saturation < 0.6 | ≥ 0.6):

| model | host WB | tungsten WB |
|---|---|---|
| no change | 7.01 \| 6.42 | |
| tone first: one curve on camera RGB, then the Standard colour transform | 1.72 \| 2.31 | |
| tone last: one curve on each channel, ProPhoto | 1.02 \| 2.17 | 0.99 \| 2.14 |
| tone last: one curve on each channel, Hasselblad L\* RGB (wider primaries) | 1.87 \| 2.98 | 1.60 \| 2.74 |
| **tone last: one curve on each channel, Hasselblad RGB** | **0.31 \| 0.19** (p90 0.39) | **0.32 \| 0.17** |
| tone last: lightness only (a\*, b\* kept) | 5.00 \| 4.12 | |
| tone last: luminance, RGB ratios kept | 6.23 \| 4.19 | |

- Hasselblad RGB (`HBImageProcessing.framework/…/Profiles/Hasselblad RGB.icc`): D50 primaries R (0.6491,
  0.2989, 0.0046), G (0.1886, 0.6575, 0.0430), B (0.1265, 0.0437, 0.7772); γ 2.2. Phocus also ships
  "Hasselblad L\* RGB v1" (ProPhoto primaries with an L\* curve) and "Hasselblad L\* RGB" (wider
  primaries); neither fits.
- This resolves Finding 11's puzzle (a per-channel curve, yet unchanged chroma across responses): the
  median chroma ratio 1.004 hid opposite shifts; hue moves a median 3.0° (p90 8.8°), as a per-channel
  curve predicts.
- Phocus's library symbols agree: a "gradation manager" keyed on the film-curve type, separate from the
  colour-correction filter (which takes sensor type, IR filter type, film-curve type and colour model).

**Structure with the right space.** Held-out patches, models fitted on saturation < 0.6 unless noted,
median ΔE00 by camera-RGB saturation (35-100 | 28P):

| model | 0–0.3 | 0.3–0.6 | 0.6–0.85 | 0.85–1 |
|---|---|---|---|---|
| A matrix → ProPhoto → per-channel curve (Finding 11) | 1.02 \| 1.25 | 1.05 \| 1.03 | 2.87 \| 2.69 | 6.94 \| 6.78 |
| A3 matrix → Hasselblad RGB → per-channel curve | 0.86 \| 1.02 | 1.01 \| 0.96 | 1.74 \| 1.71 | 2.22 \| 2.52 |
| A2 matrix → ProPhoto → Adobe-style curve (max/min channel, hue kept) | 1.05 \| 1.06 | 1.83 \| 1.82 | 4.54 \| 4.29 | 7.07 \| 6.94 |
| C A3 + 2.5-D hue/saturation table | 0.73 \| 0.66 | 0.68 \| 0.62 | 1.67 \| 1.64 | 2.18 \| 2.48 |
| E A3 + 3-D hue × chroma × lightness table (36 × 9 × 8), fitted on all | 0.63 \| 0.59 | 0.37 \| 0.37 | 0.74 \| 0.73 | 0.87 \| 0.82 |
| D full 33³ table (the profile) | 0.43 \| 0.49 | 0.27 \| 0.25 | 0.52 \| 0.48 | 1.34 \| 1.31 |

- With the curve in Hasselblad RGB, a matrix and a curve fitted only on moderate colours predict the most
  saturated ones at 2.2–2.5 instead of 6.8–6.9. Most of what looked like "3D reshaping of saturated
  colours" is the tone curve acting in a smaller space.
- Moderate colours still need lightness-dependent corrections: a value-independent table (C) leaves
  0.6–0.7; adding 8 lightness levels (E) brings it to 0.37, as good as the full table. So HNCS fits a
  DNG-style matrix + 3D LookTable + tone curve, but a DNG profile's tone curve runs in ProPhoto with
  Adobe's hue-holding method (A2), which fits worst; its LookTable has to absorb the difference.

**White balance.** Grids rendered at other As Shot white balances, against the table fitted at the host
white balance, after a correction fitted on moderate colours (near-whites above L\* 93 left out); median
ΔE00, moderate | all:

| lens, R/B of AsShotNeutral | no correction | WB gains (diagonal) | 3×3 matrix before the table | 3×3 after (XYZ) |
|---|---|---|---|---|
| 35-100, host 0.625 (reference) | 0.22 \| 0.92 | 0.24 \| 0.89 | 0.21 \| 0.88 | 0.20 \| 1.02 |
| 35-100, 0.759 (warmest) | 1.06 \| 2.25 | 1.10 \| 2.18 | **0.37 \| 1.57** | 0.43 \| 2.33 |
| 35-100, 0.691 | 0.66 \| 1.62 | 0.65 \| 1.52 | 0.30 \| 1.21 | 0.32 \| 1.59 |
| 35-100, 0.538 (coolest) | 0.62 \| 1.48 | 0.63 \| 1.46 | 0.34 \| 1.37 | 0.31 \| 1.45 |
| 28P, 0.759 | 1.32 \| 2.56 | 1.40 \| 2.50 | **0.43 \| 1.74** | 0.51 \| 2.69 |

- For moderate colours, the white-balance dependence is a change of colour matrix: off-diagonal terms
  grow steadily with white balance (±0.02–0.05 between R/B 0.54 and 0.76), with opposite signs on either
  side of the host. Plain white-balance gains do nothing.
- Saturated colours change by more than a matrix (1.57 vs the reference 0.88), so the table or the
  matrix's effect on saturated colours also moves.
- Practical consequence: a tungsten profile (open question 2) could start from E5 plus a matrix
  extrapolated along this trend, then be refined on tungsten grids.

### Finding 15: the sidecar keys behind Phocus's response options

**In plain terms:** Two settings in Phocus's sidecar change the rendering of X2D II files. `FilmCurve` 0
gives a brighter tone curve with the same colour stage; `ColorModel` 1 changes colour as well as tone.
The other values of those keys, and the `Mode` key, do nothing. Phocus's Reproduction tool offers four
responses (Standard, Reproduction, Reproduction Low Gain, Negative); Finding 19 maps them to
`ColorModel` values.

Same grid, one key changed from the Standard sidecar (`FilmCurve` 4, `ColorModel` 0, `Mode` 0):

| setting | median ΔE00 vs Standard | grey L\* at camera 0.05 / 0.18 / 0.45 | chroma ratio | median \|Δhue\| |
|---|---|---|---|---|
| Standard | — | 29.4 / 57.5 / 84.9 | | |
| `FilmCurve` 0 | 6.10 | 42.3 / 70.8 / 91.3 | 1.004 | 3.0° |
| `FilmCurve` 5 (1–3 earlier) | 0.00 | same | | |
| `ColorModel` 1 | 3.63 | 36.9 / 59.6 / 87.6 | 1.058 | 1.9° |
| `ColorModel` 2, 3; `Mode` 1, 2 | 0.00 | same | | |

- `FilmCurve` 0 is a pure tone change (Finding 14: one Hasselblad RGB curve explains it to 0.31).
  `ColorModel` 1 isn't: no per-channel curve in any of the three spaces explains it (best 2.5), so it
  selects a different colour transform.
- Phocus's menu strings for `FilmCurve` are As Shot, Standard, Low Contrast, High Contrast, Old Standard,
  Linear (0–5), yet 1–5 render identically for X2D II files and real sidecars carry 4. Those names
  probably belong to older backs.

### Finding 16: the factory gains are a green gain and a blue gain

**In plain terms:** The two calibration numbers each X2D II stores (Finding 2) act as a green gain and a
blue gain on the camera's raw colour, with no effect on red. The effect is the same for both lenses and
nearly the same at tungsten, and changing both numbers combines the two effects. A file with the numbers
zeroed renders as if they were about 2.1. Adding the green gain to the per-body tool made the check
against another camera's photos slightly better, including lightness.

Camera-RGB gains (all three free) that make the E5 table reproduce Phocus's change, and the median ΔE00
left over:

| grid | gains (g1, g2) | kR | kG | kB | left over |
|---|---|---|---|---|---|
| 35-100, host WB | 2.20, 2.26 | 1.0009 | 0.9881 | 1.0013 | 0.05 |
| | 3.00, 2.26 | 0.9991 | 1.0118 | 0.9987 | 0.05 |
| | 2.20, 2.66 (both) | 0.9996 | 0.9871 | 1.0129 | 0.06 |
| | 0, 0 | 1.0015 | 0.9825 | 0.9940 | 0.07 |
| 28P | 2.20, 2.26 | 1.0014 | 0.9888 | 1.0020 | 0.06 |
| | 2.60, 2.66 | 1.0000 | 1.0001 | 1.0129 | 0.03 |
| 35-100, tungsten WB (R/B 1.28) | 2.20, 2.26 | 1.0005 | 0.9911 | 1.0052 | 0.08 |
| | 2.60, 2.66 | 1.0003 | 1.0026 | 1.0145 | 0.07 |

- Rule: **kG = (g1 / 2.600)^0.077, kB = (g2 / 2.260)^0.078**, kR = 1 (owner's body as reference).
  Finding 13's formula (red and blue, green fixed) gave the same colour but missed the brightness change
  (grey L\* −0.28 when g1 drops to 2.2); that was its 0.23 left over.
- Lens: none (28P matches the 35-100 to 0.001). White balance: at tungsten the green effect is about a
  quarter weaker and brings a small blue change; the same rule still leaves only 0.24 vs 0.21.
- Both changed: the effects multiply (kG 0.9871 vs 0.9881 alone; kB 1.0129 vs 1.0128 alone).
- Zero: equivalent to g1 ≈ 2.07, g2 ≈ 2.09 under the rule, so probably a default near 2.1.
- Check on 32 DPReview photos (body gains 2.363, 2.518), frame centre, E5 35-100:

| per-body correction | median ΔE00 | median ΔL\* | greys Δa\* / Δb\* |
|---|---|---|---|
| none | 1.23 | +0.71 | −0.52 / +0.53 |
| Finding 13 formula (1.0068, 1, 1.0169) | 1.02 | +0.70 | −0.08 / −0.03 |
| green/blue rule (1, 0.9927, 1.0085) | **0.96** | **+0.56** | −0.08 / +0.01 |

- `tools/body_gains.py` now prints `--input-gain 1,kG,kB`.

### Finding 17: no focus-distance dependence on the 35-100, or on the 28P at f/5.6 and f/8

**In plain terms:** Changing where the lens was focused doesn't change Phocus's corrections for either
lens, from the centre to the corners, with lens corrections on or off. The blog's focus effect was on the
XCD 55V and 90V, which remain untested here.

Synthetic L\* 40 flat fields in matched pairs of the owner's raws (same focal length and aperture,
BaselineExposure set to 0 in all); green gain near − far, in stops, at r 0.6 / 0.8 / 0.95, and the largest
colour (B/G, R/G) difference:

| pair | corrections | green difference | colour |
|---|---|---|---|
| 35-100 100 mm f/8, 5.7 m vs ∞ | on | −0.000 / −0.002 / +0.013 | ≤ 0.001 |
| | off | −0.000 / −0.001 / −0.001 | ≤ 0.001 |
| 35-100 40 mm f/8, 1.9 m vs 5.7 m | on, off | ≤ 0.000 everywhere | ≤ 0.001 |
| 28P f/8, 0.75 m vs ∞ | on | +0.002 / +0.003 / −0.001 | ≤ 0.001 |
| 28P f/5.6, 0.75 m vs 7.9 m | on | +0.004 / +0.004 / −0.000 | ≤ 0.005 |

- The closest matched 35-100 frame was 1.9 m, so close focus on the zoom isn't covered.
- Side note: the 28P's correction at r 0.95 is +2.46 stops at f/5.6 and +2.29 at f/8 (+0.84 for the
  35-100 at 40 mm f/8).

### Finding 18: ColorModel 1 is a separate rendering, and the working space changes colour too

**In plain terms:** `ColorModel` 1 is a complete alternative rendering. It starts from the same colour
stage as Standard, then adds a little exposure and saturation and a much lighter shadow curve, and treats
saturated dark colours differently. When it's on, `FilmCurve` is ignored. Phocus's "working space"
setting (`ColorWorkingSpace`) also changes the rendering, by more than moving the tone curve to another
space would. All of the owner's real sidecars use the defaults that the profiles match.

`ColorModel` 1 against Standard (`tools/round3/colormodel.py`), held-out median ΔE00 by camera-RGB
saturation (0–0.3 / 0.3–0.6 / 0.6–0.85 / 0.85–1):

| model of the ColorModel 1 render | | | | |
|---|---|---|---|---|
| Standard as is | 4.57 | 2.92 | 3.01 | 3.61 |
| Standard with a different camera matrix in front | 4.79 | 2.97 | 3.00 | 3.79 |
| the raw's own DNG ColorMatrix1 + a Hasselblad RGB curve | 2.37 | 2.01 | 2.64 | 3.03 |
| Standard with a new Hasselblad RGB curve | 1.78 | 1.79 | 2.19 | 2.80 |
| **Standard's colour stage, then a new 3×3 and a new curve in linear Hasselblad RGB** | **0.57** | **0.49** | **0.77** | **1.09** |

- Greys at camera level 0.011 / 0.028 / 0.165 / 0.50: L\* 14.1 / 25.4 / 59.6 / 93.4, against Standard's
  4.7 / 15.8 / 57.5 / 88.8. Grey tint about the same.
- The 3×3 is about 1.11 on the diagonal and −0.01 to −0.04 off it: roughly +7% exposure and +5%
  saturation. What's left is in saturated dark and mid colours (L\* < 70: median 1.8–2.6; lighter: 0.5).
- Not colorimetric: the raw's DNG matrix fits it worse than it fits Standard (2.0–2.4 vs 1.4–1.7).
- `ColorModel` 1 + `FilmCurve` 0 renders identically to `ColorModel` 1 alone (0.00).

`ColorWorkingSpace` (`tools/round3/working_space.py`, `colormodel_combos.py`):

| value | median ΔE00 vs Standard | grey L\* at camera 0.028 / 0.165 / 0.428 | chroma ratio | median \|Δhue\| |
|---|---|---|---|---|
| 0 (default) | — | 15.8 / 57.5 / 84.9 | 1.000 | — |
| 1 | 6.55 | 14.0 / 61.3 / 86.9 | 0.883 | 5.2° |
| 2 | 4.58 | 14.0 / 61.3 / 86.9 | 0.920 | 3.3° |
| 3 | 2.93 | 14.0 / 61.3 / 86.9 | 1.047 | 1.7° |

- Values 1–3 share one grey curve (more midtone contrast than 0) and differ in saturation and hue.
- Undoing Standard's curve and applying a curve in another space (Hasselblad L\* RGB, ProPhoto, Rec.2020,
  Display P3, Adobe RGB, sRGB) doesn't explain them (best 2.6–3.3 on moderate colours), so the working
  space selects a different colour stage, as the library's colour-correction filter signature suggests.
  The same test on the Standard render returns it exactly (0.00), which checks the method.
- Rec.2020 comes close to Hasselblad RGB in that check (0.18): the two spaces' primaries are similar.
- The owner's real sidecars (33) all use `ColorWorkingSpace` 0, `ColorModel` 0, `FilmCurve` 4.
- Finding 20 names the working spaces.

### Finding 19: the Response menu is the ColorModel key

**In plain terms:** Phocus's Response menu (Standard, Reproduction, Reproduction Low Gain, Negative) is
stored as the sidecar's `ColorModel` value: 0, 1, 4 and 5. This came from reading Phocus's own code and
was confirmed by rendering each value: 5 inverts the picture, as a Negative response should. The
brighter `FilmCurve` 0 is a different, older setting, not Reproduction.

**From the code.** The Reproduction tool's menu is bound to an `imageProperties.responseIx` property in
the Phocus app. Its accessors (found through the Objective-C method lists of the arm64 binary and
disassembled with `otool`) read and write one integer in the image's correction settings:
- `responseIx` getter: stored value v → v − 2 if v > 1, else v;
- `setResponseIx:`: menu index i → stores i + 2 if i > 1, else i;
- `reproductionMode` getter: stored value == 1; `setReproductionMode:` stores 0 or 1.

So menu items 0, 1, 2, 3 store 0, 1, 4, 5, and stored values 2 and 3 are skipped. Of the sidecar keys,
only `ColorModel` behaves like that: 1 changes the rendering, and 2 and 3 render as Standard (Finding 15).

**Confirmed by rendering** (`tools/round3/responses_all.py`):

| `ColorModel` | menu item | median ΔE00 vs Standard | chroma ratio | grey L\* at camera 0.011 / 0.057 / 0.165 / 0.428 / 0.6 |
|---|---|---|---|---|
| 0 | Standard | — | 1.000 | 4.7 / 29.4 / 57.5 / 84.9 / 91.9 |
| 1 | Reproduction | 3.63 | 1.058 | 14.1 / 36.9 / 59.6 / 87.6 / 98.7 |
| 4 | Reproduction Low Gain | 6.86 | 0.964 | 9.2 / 28.4 / 47.4 / 70.8 / 80.1 |
| 5 | Negative | 98.5 | 1.034 | 89.2 / 76.1 / 60.0 / 35.1 / 23.1 (inverted) |
| 2, 3, 6 | not in the menu | 0.00 | 1.000 | as Standard |

- Reproduction (Finding 18): Standard's colour stage, then about +7% exposure, +5% saturation and a much
  lighter shadow curve. Low Gain is darker throughout, with slightly less chroma.
- `FilmCurve`'s menu strings are As Shot, Standard, Low Contrast, High Contrast, Old Standard, Linear
  (0–5); the brighter rendering is "As Shot", which may not be offered for X2D II files.

### Finding 20: Phocus's working spaces

**In plain terms:** Phocus's Working Space menu offers Hasselblad RGB (the default) and Hasselblad L\*
RGB, stored as `ColorWorkingSpace` 0 and 1. The code knows four more values that aren't in the menu. All
but the default use an L\* encoding instead of a gamma curve, which changes the tone curve, and each one
also changes saturation. The default is the space where Finding 14 found the tone curve.

**From the code.** The menu (`imageProperties.workingSpaceIx` in the Reproduction tool) stores its index
unchanged; its items are "Hasselblad RGB" and "Hasselblad L\* RGB". In `HBRawCorrections`:
- `IsLStarWorkingSpace(ws)`: true for 1–5; `DeduceCompanding(ws)`: L\* companding for 1–5, otherwise gamma;
- `GetColorSpaceChangeMatrix(ws)`: identity for 0; for the others, a stored matrix (inverted where it
  holds primaries) times `kMHasselbladRGB`, except value 3, which skips the Hasselblad RGB step. The stored
  matrices are Hasselblad L\* RGB's primaries (1), XYZ → ProPhoto (2), the D50 white as a diagonal (3, 4)
  and ProPhoto's primaries (5).

**Rendered** (`tools/round3/working_spaces_all.py`):

| value | space | in the menu | median ΔE00 vs 0 | chroma ratio | grey L\* at camera 0.028 / 0.165 / 0.428 |
|---|---|---|---|---|---|
| 0 | Hasselblad RGB, gamma | yes (default) | — | 1.000 | 15.8 / 57.5 / 84.9 |
| 1 | Hasselblad L\* RGB, L\* | yes | 5.80 | 0.884 | 14.0 / 61.3 / 86.9 |
| 2 | ProPhoto primaries, L\* | no | 4.15 | 0.921 | 14.0 / 61.3 / 86.9 |
| 3 | XYZ (D50), L\*, no Hasselblad RGB step | no | 2.62 | 1.047 | 14.0 / 61.3 / 86.9 |
| 4 | XYZ (D50), L\*, via Hasselblad RGB | no | 11.16 | 0.747 | 13.9 / 61.2 / 86.8 |
| 5 | ProPhoto primaries, L\* | no | 4.15 | 0.921 | as 2 |

- Values 2 and 5 render identically (0.00), as the code predicts: two routes to the same matrix.
- All L\* spaces share one grey curve, different from the default's (more midtone contrast).
- Moving Standard's curve into these spaces doesn't reproduce them (Finding 18), so the colour stage also
  depends on the working space, as the colour-correction filter's signature (which takes it) suggests.

## 2026-11-15 (round 4): building on the findings

### Finding 21: tungsten profiles

**In plain terms:** Profiles for tungsten light, fitted the same way as E5 but on synthetic grids at
four tungsten white balances (about 3100–4200 K). On three real tungsten-lit photos they halve the
error of the daylight profiles. Use them by hand for tungsten-lit frames; Capture One can't switch
profiles by white balance.

- Grids: the E5 hosts (35-100 and 28P, owner's body), 22-level grids, As Shot neutral set with
  `make_synthetic_raw.py --neutral r,g,b` along the log-neutral line from the host's daylight neutral
  (0.368, 1, 0.589) through a DPReview tungsten frame's (0.569, 1, 0.445) at t = 0.5, 0.75, 1.0, 1.25.
  Capture One reads them as 4175 K, 3747 K, 3395 K and 3105 K (tints −3 to −12).
- Pairs saved with `tools/save_synth_pairs.py`; fitted with `fit_synthetic.py --pairs` (new option: fit
  from saved pairs). Refitting E5c from its saved pairs reproduces the shipped table exactly, which
  checks the path.
- Synthetic grids, 35-100, median ΔE00 moderate | all colours:

| grid (Capture One reading) | E5 (daylight) | E5 tungsten |
|---|---|---|
| warmest daylight grid (R/B 0.76) | 1.00 \| 2.13 | 2.05 \| 3.64 |
| 4175 K | 1.81 \| 3.32 | 1.26 \| 2.51 |
| 3747 K | 2.48 \| 4.42 | 0.53 \| 1.52 |
| 3395 K | 3.05 \| 5.42 | 0.49 \| 1.38 |
| 3105 K | 3.92 \| 6.81 | 1.24 \| 2.69 |

- Real tungsten-lit photos (DPReview, 35-100, As Shot, other body with its factory gains applied),
  median ΔE00 at the frame centre (r < 0.2):

| frame | E5 (daylight) | E5 tungsten (4 WBs) | tungsten fit on 2 WBs (3400–3750 K) |
|---|---|---|---|
| 2462814331 | 1.95 | **1.71** | 1.76 |
| 5727340084 | 2.77 | **1.07** | 1.21 |
| 8671272247 | 2.75 | **1.03** | 1.13 |
| mean | 2.49 | **1.27** | 1.37 |

- The fit's own error is larger than E5's (2.1 vs about 1.5 for all colours) because Phocus changes
  colour across the 1000 K range more than within daylight; a narrower fit did worse on real photos.
- The 28P tungsten profile is validated only on synthetic grids (no real 28P tungsten frames).
- Files: `profiles/… E5 28P LCC Tungsten.icm`, `… E5 35-100 LCC Tungsten.icm` (with the same LCC input
  gains as E5), four styles, `fit/lut_e5_*_tungsten.npz`, pairs in `fit/synthetic/pairs/HNCStung*.npz`.

### Finding 22: pre-processed raws match Phocus across the whole frame

**In plain terms:** Writing Phocus's lens correction and colour shading straight into a copy of the raw,
then rendering it in Capture One with the plain E5 profile and no Light Falloff or LCC, matches Phocus
(lens corrections on) to 0.3–0.8 ΔE00 over the whole frame, corners included: about twice as close as
the LCC route, and the 28P's aperture problem disappears. The catch that made the first try fail:
Capture One's raw response isn't proportional in the shadows, so a gain measured in its colour scale
has to be converted before it's written into the raw. The same effect explains Finding 12's
"correction shrinks for brighter images": Phocus's vignetting correction is a fixed multiplier on the
raw values.

**Method.**
1. For each test frame, a synthetic L\* 30 flat with the frame's own metadata (`make_synthetic_raw.py
   --flat 30`), rendered by Phocus with `LensCorrection` 4; `flat_gain.py` gives the per-channel gain
   map in Capture One's camera-RGB scale.
2. `make_preprocess_map.py` converts it to raw gains through Capture One's response
   (`fit/c1_response.npz`, measured from the E5 grids' nominal vs probe values) at the flat's level and
   BaselineExposure, and saves it by lens state (`fit/preprocess_maps/XCD28P_28mm_f8.0.npz` …).
3. `preprocess_3fr.py IN OUT --maps fit/preprocess_maps` multiplies each raw channel by its gain
   (interpolated per photosite) in a copy.
4. Capture One: style "HNCS E5 … (pre-processed)" = plain E5 profile (no LCC compensation), Linear
   Response, Light Falloff 0. Capture One's default Light Falloff for these lenses is 100, so the style
   has to set 0.

**Capture One's response** (white-balanced raw, as a fraction of 0.92 × white − black, to the camera RGB
a profile receives): ratio 0.17 at 0.01, 0.64 at 0.1, 0.74 at 0.4, 0.75 from 0.6 up (affine above 0.05:
0.761 × raw − 0.0096). Applying the map to raw values directly overshot (corrected flat L\* 49.8 vs
Phocus 45.6 at r 0.6; real frames dL +4 to +6 at the edges).

**Check on flats.** Corrected flat in Capture One vs Phocus's corrections-on flat, dL\* from centre to
r 0.9: +0.02 to +0.07 (28P f/8, BaselineExposure 0) and −0.04 to −0.10 (28P f/5.6, BaselineExposure
+0.458).

**Real photos**, whole frame (r < 0.95) vs Phocus with lens corrections on, median ΔE00:

| frame | E4 + LF 120 | E5 LCC + LF 120 + colour LCC (Finding 10) | **pre-processed + plain E5** |
|---|---|---|---|
| 28P B0000901 (f/16) | 2.19 | 1.56 | **0.72** |
| 28P B0000917 (f/5.6) | 2.11 | 1.56 | **0.80** |
| 28P B0000931 (f/8) | 2.37 | 1.43 | **0.48** |
| 35-100 B0000623 (35 mm f/11) | 1.08 | 0.76 | **0.43** |
| 35-100 B0000679 (35 mm f/11) | 1.10 | 0.69 | **0.31** |
| 35-100 B0000702 (50 mm f/8) | 0.65 | 0.73 | **0.65** |
| mean 28P / 35-100 | 2.23 / 0.94 | 1.51 / 0.73 | **0.67 / 0.47** |

- By radius the error is flat: 28P 0.4–0.9 and dL within ±0.3 from centre to r 0.8–1.0 (was dL −3 to −7).
  B0000702's remaining 0.65 is a uniform +0.5 L\*, the per-frame lightness offset of open question 4.
- Raw gains (green, stops) at r 0.4 / 0.6 / 0.8 / 0.9: 28P f/5.6 +0.37 / +0.84 / +1.64 / +2.08; f/8
  +0.38 / +0.84 / +1.50 / +1.91; f/16 +0.39 / +0.84 / +1.50 / +1.89; 35-100 35 mm f/11 +0.12 / +0.30 /
  +0.61 / +0.76; 50 mm f/8 +0.09 / +0.20 / +0.41 / +0.49.
- Highlight headroom: clipped photosites 0.0% on most frames, 0.1% on B0000702, 2.3% on B0000901 (bright
  sky in the f/16 corners, up to 5.4× gain).
- Finding 12 revisited: converted to raw gains, near/far focus and BaselineExposure 0/+0.764 give the
  same correction to within 0.002 stop at r 0.4–0.6 (0.015 at r 0.7). The 0.06-stop difference reported
  there was Capture One's response, not Phocus compressing its gain.
