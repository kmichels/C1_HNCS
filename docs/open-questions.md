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
- [x] Response options: the menu is `ColorModel` 0 / 1 / 4 / 5 = Standard / Reproduction / Reproduction
  Low Gain / Negative (Finding 19).
- [x] `ColorModel` 1: a separate rendering (Standard's colour stage + more exposure and saturation + a much
  lighter shadow curve; ignores `FilmCurve`) (Finding 18).
- [x] `ColorWorkingSpace`: 0 Hasselblad RGB (default), 1 Hasselblad L\* RGB (both in the menu); 2–5 are
  hidden L\* variants with ProPhoto or XYZ primaries (Finding 20).
- [x] Factory gains: a green and a blue gain; no lens dependence, slight white-balance dependence;
  the two combine; zero acts like ~2.1 (Finding 16).
- [x] Focus distance: Phocus reads a focus code from byte 6 of 0x0018. Close focus lowers the 28P's
  corner correction by up to 0.07 stop and darkens the 55V's centre by 0.3 L\*; the 35-100 barely
  changes. Maps are made per focus code (Finding 31).
- [x] Highlight recovery: measured on synthetic clipping (Finding 23). Phocus keeps colour where one
  channel clips, and its Highlight Recovery rebuilds clipped channels; Capture One's slider only
  compresses.
- [x] Highlight recovery on a real frame with clipped sky (Finding 25).
- [ ] Could the pre-processing step reconstruct clipped channels in the raw the way Phocus does? (It
  would need values above the white level, which a 3FR can't hold, so probably only as a darker
  rendering of the reconstructed range; not obviously possible.)
- [x] Focus distance on the XCD 55V, where blog.tonalphoto.com saw it: measured from four f/2.5 raws at
  different distances (Finding 31).
- [ ] 90V focus: a 90V raw is now available (`data/tonal/B0038945`). Sweep byte 6 of 0x0018 on a synthetic
  flat, as Finding 31 did for the other lenses. blog.tonalphoto.com saw a focus effect on the 90V.
- [x] 38V E5 profile and maps, from the owner's X2D II raws (Finding 32).
- [x] 25V, 55V, 90V, 120 Macro and 135 E5 profiles, from blog.tonalphoto.com's X2D II raws (Finding 35).
  Each was tested at one lens setting only.
- [ ] The 38V profile renders about 0.2 L\* darker than Phocus on every frame (Finding 32). Worth checking
  on more scenes; a lightness offset in the table would fix it if it holds.
- [x] Question 4, per-frame lightness: mostly Phocus's per-lens-setting brightness, now in the maps
  (Finding 27). About ±0.2 L\* per frame remains.
- [x] Question 5, shading mechanism: Phocus looks the lens up by a 34-byte identity in the raw and uses
  its own built-in lens data (Finding 29).
- [ ] Question 1 (28P edges at f/5.6+) for the LCC route; pre-processing already handles it.

**Building**
- [x] Tungsten profiles (Finding 21). Still to check: the 28P one on real tungsten frames.
- [x] Pre-processing step: prototype works, 0.3–0.8 ΔE00 over the whole frame (Finding 22).
- [x] Pre-processing: automatic maps (`tools/auto_maps.py`); validated on 23 unseen photos (Finding 24).
- [x] Pre-processing batch workflow (`tools/preprocess_folder.py`, Finding 25).
- [x] Headroom for bright corners: tried and dropped (it breaks Capture One's clipped-highlight
  handling; the clipped corners render white either way) (Finding 25).
- [x] Corrected copies open with the right settings: the batch tool writes Capture One sidecars
  (Finding 28).
- [x] README contact sheet: pre-processed + E5 vs Phocus vs Capture One default.
- [x] E5 profiles for other lenses, automatically (`tools/auto_lens_profile.py`, Finding 26). Checked on
  the 38V: 0.35–0.53 ΔE00 with pre-processing (Finding 32).
- [ ] Profiles for Phocus's Reproduction responses, if wanted: synthetic grids rendered with `ColorModel`
  1 or 4, fitted like E5.
- [x] Keep bright yellows and oranges saturated (Finding 34). The colour fade now starts at L\* 100, and
  near-white greys fade from L\* 95. The profile writer no longer runs the fade twice. All seven E5
  profiles were rebuilt. Bright yellows and oranges went from about 19 to 2.4 ΔE00 in Capture One; real
  held-out frames didn't change. Still to do: whole real photos rendered in Capture One. (E4, built
  by `fit_anchored.py` with the old rule, was removed instead.)
- [ ] Very saturated colours above C\* 90 (strong yellow, magenta) still lose 10–20 C\* to the profiles' soft
  chroma compression (`finalize`'s knee at 90, cap 127). The Lab encoding allows more along most hues;
  a knee keyed to the encodable a\*/b\* range would keep more of it.
- [ ] Shade profiles, like the tungsten ones: E5 fitted on 7000–8000 K grids ("HNCS E5 … Shade"). Worth
  it if shade frames matter; synthetic colours drift to about 2 ΔE00 at 8000 K (Finding 33).

**Validation and writing**
- [x] Check on photos not used in fitting: 23 frames (Finding 24). Still worth a look: new photos in
  varied light, especially tungsten and mixed light.
- [x] Exposure pushes (Finding 33). In both apps, a push renders the same as more light on the sensor
  (within 0.10 ΔE00), so a push adds no difference of its own. Pushed patches differ between the apps
  only where the push makes saturated colours bright (next item): +2 EV costs 11.9 C\* at saturation
  0.9, against 0.30–0.52 ΔE00 at saturation 0.3–0.6. Not yet checked on real pushed frames.
- [x] Bright saturated colours near clipping (Finding 33). Cyan matches at every level. Yellows, oranges
  and yellow-greens fade to grey in Capture One once Phocus's L\* passes 95 (16–25 ΔE00 at level 0.59 and
  up). Reds and pinks go white sooner in Phocus. Magenta at saturation 0.9 has about 10–22 C\* less.
- [x] White balance above 6500 K (Finding 33). Greys hold everywhere. Colours (C\* 20–60) are best at
  5500 K (0.5) and drift to 1.3 at 6500 K and 2.1–2.4 at 8000 K. Three real shade frames scored 0.58–0.78,
  against 0.26–0.61 for Finding 24's frames. The daylight profiles don't hold down to 4500 K (1.3–2.0).
- [ ] Phocus 4.2.3. Everything here was fitted and checked on Phocus 4.2.2; blog.tonalphoto.com's latest
  numbers are on 4.2.3. After updating, re-render a few synthetic grids and flats to see whether HNCS or
  the lens processing changed.
- [x] Write up the findings for blog.tonalphoto.com's author: [writeup.md](writeup.md).

## 1. XCD 28P edge brightness at f/5.6 and narrower

Solved by pre-processing (Finding 22) for lens states with a map; still open for the LCC route.

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

## 2. Tungsten white balance (largely done)

Phocus's colour depends on white balance. E5 averages over about 4700–6300 K. Tungsten-lit frames
rendered at their As Shot white balance (about 3400 K) are 1.6–2.1 ΔE00 off with E5, and 1.0–1.7 with
the E5 Tungsten profiles (Finding 21). Above about 6000 K the daylight profiles drift as well: about 1.3
ΔE00 on colourful patches at 6500 K and 2.2 at 8000 K (Finding 33). Open: the 28P tungsten profile on
real frames; a shade profile; mixed light and
the range between the daylight and tungsten profiles (about 4200–4700 K).

The notes below are how it was built.

**How to build a tungsten profile.** Make synthetic grids with tungsten white balances (write a
tungsten frame's AsShotNeutral into the grid raws; `make_synthetic_raw.py --neutral-from`), fit
them on their own, and write "HNCS E5 … Tungsten". Capture One can't switch profiles by white balance,
so it would be a manual choice. A Kelvin sweep would show where Phocus's behaviour changes.

Shortcut: within daylight, white balance changes Phocus's colour matrix in a steady way (Finding 14), so
E5 plus an extrapolated matrix may get most of the way before refining on tungsten grids.

## 3. A pre-processing step before Capture One

Prototype done and measured (Finding 22): `tools/preprocess_3fr.py`. Open: automatic maps for new lens
states, a headroom option, Capture One sidecars. The original plan:

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
- the ~0.2 L* left in the maker-note entries that can't be swapped in place (0x0081–0x0083 turned out
  not to be focus fields: Finding 30);
- focus distance, now in the maps (Finding 31).

## 5. Mechanism of Phocus's spatial colour shading

Measured precisely, but its source isn't confirmed. The likely source is the per-lens "blue-corner
shading" files in the camera firmware's lens database (reported by blog.tonalphoto.com). It is
applied whether lens corrections are on or off, and the brightness lift it brings with corrections off
is the "edge brightening" earlier versions removed by hand. The shading doesn't change with focus; the
vignetting correction and brightness do, a little (Finding 31). The 28P shows slightly more colour at f/4
than at f/8 in the extreme corners.

## 6. Highlight recovery (measured: Finding 23)

People often say Phocus handles highlights better than other raw converters. Measured on a synthetic
exposure ladder through clipping: at defaults both apps reach white about a quarter stop before the sensor
clips, but where one channel has clipped Phocus keeps some colour (chroma 17 vs 0), and its Highlight
Recovery rebuilds the clipped channel, keeping tone up to about 1.5 stops past clipping. Capture One's
Highlight slider only compresses tones below clipping. Still open: a real frame with clipped sky, and
whether a pre-processing step could reconstruct clipped channels in the raw. The notes below were written
before the test:
- **The tone curve's shoulder.** HNCS's curve is applied to each channel in Hasselblad RGB (Finding 14)
  and rolls off slowly: L\* 90 at +1.2 EV over middle grey, 97 at +1.7, 99 at +2.0. A per-channel
  curve on a fairly small space eases bright colours toward white rather than clipping them to a hue.
  The profiles carry this curve, so Capture One with HNCS gets the same shoulder up to the raw's clip
  point.
- **Not compression after lens correction.** Phocus's vignetting gain looked smaller in brighter images
  (Finding 12), but that was Capture One's raw response (Finding 22): Phocus's gain is a fixed raw
  multiplier.
- **A highlight stage in the sidecar.** Phocus's settings include `HighlightDesaturation` (default 50),
  `HighlightRecovery` and `AutoHighlight` (default 0), so there is a separate step for near-white
  colours.
- **Not measured.** Every synthetic patch so far stayed below about 92% of the raw's white level, and
  fits excluded near-clipped data. What Phocus does when one or two raw channels clip (reconstructing
  them from the others, which is usually what "highlight recovery" means) is untested, in both apps.

**How to test.** Synthetic patches with one or two channels pushed past the white level, across hues, and
gradients that run through clipping; render in Phocus at the defaults and with `HighlightRecovery` and
`HighlightDesaturation` varied; render the same files in Capture One (Highlight slider 0 and its
recovery). Then compare on real frames with clipped skies or speculars.

## Resolved

- **Other bodies.** The two factory gains are a green and a blue gain on camera RGB (Findings 13 and 16).
  `tools/body_gains.py` reads any raw's record and prints the profile input gain for that body.
  Validated on 32 raws from a second body, and on a third body whose green gain sits well outside both
  (Finding 35). There the correction takes five real frames from 1.33–1.98 to 0.16–0.51 ΔE00.
- **What HNCS is made of.** A colour stage (matrix + 3D table, the matrix shifting with white balance),
  then one tone curve per channel in Hasselblad RGB; the response setting swaps the curve (Finding 14).
- **Focus distance.** Phocus reads a focus code from byte 6 of maker-note 0x0018 (0 at infinity). It
  changes the vignetting correction and centre brightness, most on the 55V, up to 0.07 stop in the 28P's
  corners, barely on the 35-100; colour shading doesn't change. EXIF SubjectDistance doesn't record where
  these lenses were focused, which is why Finding 17 found nothing (Finding 31).
- **"The two lenses render greys about 1 b* apart."** It's mostly Phocus's radial colour shading,
  which real-photo fits averaged over the frame. At the centre the only lens effect is 0.8 L* of
  brightness. E5 handles both: a per-lens table, and an LCC for the shading.
- **"The DPReview frames render greys about 1 b* off."** It's the factory calibration record (Findings 2
  and 13), not firmware, serial or scene content.
- **"The 28P corners stay half a stop dark."** That's question 1: it depends on aperture.
