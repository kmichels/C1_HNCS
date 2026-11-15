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
