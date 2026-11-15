# Open questions

What's still unresolved, with what's known and how to test it. Resolved questions are listed at the end.
Numbers are from [results.md](results.md) and [research-log.md](research-log.md).

## Work list

Everything still open, in one place. Details for the numbered questions are below.

**Research gaps**
- [x] HNCS structure: tone after colour, one curve per channel in Hasselblad RGB (Finding 14).
- [x] HNCS structure: a 3D hue/saturation/lightness table explains the rest (Finding 14).
- [x] HNCS structure: white balance changes the colour matrix; saturated colours change a bit more
  (Finding 14).
- [x] HNCS structure: the 28P's is the same as the 35-100's (Finding 14).
- [ ] Response options: `FilmCurve` 0 and `ColorModel` 1 change the rendering (Finding 15). Which menu item
  sets which? Choose each response in Phocus's Reproduction tool and read the sidecar (needs the app).
- [x] `ColorModel` 1: a separate rendering (Standard's colour stage + more exposure and saturation + a much
  lighter shadow curve; ignores `FilmCurve`) (Finding 18).
- [ ] `ColorWorkingSpace` 1–3 change the colour stage, not only where the curve runs (Finding 18). Which
  spaces are they? (Check the Working Space menu against the sidecar; needs the app.)
- [x] Factory gains: a green and a blue gain; no lens dependence, slight white-balance dependence;
  the two combine; zero acts like ~2.1 (Finding 16).
- [x] Focus distance on the 35-100, and the 28P at f/5.6 and f/8: none (Finding 17).
- [ ] Focus distance on the XCD 55V and 90V, where blog.tonalphoto.com saw it (needs raws), and close
  focus on the 35-100 (nearest matched frame was 1.9 m).
- [ ] Question 1 (28P edges at f/5.6+), question 4 (per-frame lightness), question 5 (shading mechanism).

**Building**
- [ ] Tungsten profile (question 2).
- [ ] Pre-processing step for 3FRs before Capture One (question 3).
- [ ] Automate per-image settings by writing Capture One's sidecar, if its format can be worked out.
- [ ] Refresh the README contact sheet with E5.
- [ ] Profiles for Phocus's brighter response (`FilmCurve` 0): it only swaps the tone curve in Hasselblad
  RGB (Finding 14), so E5 with that curve swapped in.

**Validation and writing**
- [ ] Check E5 on new real photos (owner's camera, varied light).
- [ ] Write up the findings for blog.tonalphoto.com's author.

## 1. XCD 28P edge brightness at f/5.6 and narrower

With lens corrections on, Phocus's vignetting correction and Capture One's Light Falloff scale with
aperture differently. On synthetic flat fields, Light Falloff 120 minus Phocus at r 0.8–0.9:
- 28P at f/4: −0.05 to −0.14 stop;
- 28P at f/8: −0.30 to −0.40 stop;
- 35-100: within ±0.05 at 35, 45 and 100 mm.

In real photos this is the 28P's largest remaining error (dL −3 to −7 at the edges at f/5.6–f/16).

**Options.** A brightness LCC (Uniform Light) built from the residual, applied at an aperture-dependent
strength ("LCC uniform light amount"), or one LCC per aperture. Capture One normalises an LCC's
brightness to its mean too, so the overall exposure shift would need compensating, like the colour
shift is.

## 2. Tungsten white balance

Phocus's colour depends on white balance. E5 averages over about 4700–6300 K. Tungsten-lit frames
rendered at their As Shot white balance (about 3400 K) are 1.6–2.1 ΔE00 off.

**How to build a tungsten profile.** Make synthetic grids with tungsten white balances (write a
tungsten frame's AsShotNeutral into the grid raws; `make_synthetic_raw.py --neutral-from`), fit
them on their own, and write "HNCS E5 … Tungsten". Capture One can't switch profiles by white balance,
so it would be a manual choice. A Kelvin sweep would show where Phocus's behaviour changes.

Shortcut: within daylight, white balance changes Phocus's colour matrix in a steady way (Finding 14), so
E5 plus an extrapolated matrix may get most of the way before refining on tungsten grids.

## 3. A pre-processing step before Capture One

X2D II raws are uncompressed and both apps accept edited copies, so a converter could write corrected
copies of 3FRs before import:
- Apply Phocus's spatial processing (colour shading, plus vignetting correction by lens, aperture and
  focal length) directly to the sensor data. Capture One would then run with Light Falloff 0 and no
  LCC. That would fix question 1 exactly and remove the LCC compensation.
- Normalise the body with its factory gains (Finding 13), so one profile fits any X2D II.
- Possibly pre-select per-file settings (the lens's profile, a tungsten profile by white balance) by
  writing Capture One's settings sidecar, if its format can be worked out.

Costs: an extra copy step (never touching originals); brightening corners in the raw uses up
highlight headroom there (up to ~2 stops in the 28P's corners with corrections on). The
white-balance dependence would still be averaged unless profiles are chosen per white balance.

## 4. Remaining per-frame lightness differences

Some real frames are 0.5–1 L* darker in Capture One than in Phocus overall. It isn't BaselineExposure
(both apps apply it), and it isn't the factory gains (colour, not lightness). Candidates:
- the ~0.2 L* left in the maker-note entries that can't be swapped in place (newer focus-distance
  fields 0x0081–0x0083);
- (Focus distance is ruled out for the 28P: Finding 12.)

## 5. Mechanism of Phocus's spatial colour shading

Measured precisely, but its source isn't confirmed. The likely source is the per-lens "blue-corner
shading" files in the camera firmware's lens database (reported by blog.tonalphoto.com). It is
applied whether lens corrections are on or off, and the brightness lift it brings with corrections off
is the "edge brightening" earlier versions removed by hand. No focus dependence on the 28P or the 35-100
(Findings 12 and 17). The 28P shows slightly more colour at f/4 than at f/8 in the extreme corners.

## Resolved

- **Other bodies.** The two factory gains are a green and a blue gain on camera RGB (Findings 13 and 16).
  `tools/body_gains.py` reads any raw's record and prints the profile input gain for that body.
  Validated on 32 raws from another body.
- **What HNCS is made of.** A colour stage (matrix + 3D table, the matrix shifting with white balance),
  then one tone curve per channel in Hasselblad RGB; the response setting swaps the curve (Finding 14).
- **Focus distance (28P, 35-100).** An apparent focus effect was BaselineExposure. With exposure
  equalised, near and far focus give identical correction on both lenses, corners included (Findings 12
  and 17).
- **"The two lenses render greys about 1 b* apart."** It's mostly Phocus's radial colour shading,
  which real-photo fits averaged over the frame. At the centre the only lens effect is 0.8 L* of
  brightness. E5 handles both: a per-lens table, and an LCC for the shading.
- **"The DPReview frames render greys about 1 b* off."** It's the factory calibration record (Findings 2
  and 13), not firmware, serial or scene content.
- **"The 28P corners stay half a stop dark."** That's question 1: it depends on aperture.
