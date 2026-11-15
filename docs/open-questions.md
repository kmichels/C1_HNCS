# Open questions

Things measured but not resolved, with what's known and how to test each. Numbers are from
[results.md](results.md); method in [methodology.md](methodology.md).

## 1. Your two lenses render greys about 1 b* apart

**What's measured.** Near-grey blocks, E3's prediction minus Phocus, same body and firmware (1.3.16.2):

| Lens | Offset on greys |
|---|---|
| XCD 35-100 | about +0.2 b* |
| XCD 28P | −0.5 to −1.4 b* (−0.8 typical) |

It doesn't follow white balance (4700–6300 K on the 28P frames). HNCS E4 averages the two, so on
the 28P greys sit a little warm/yellow of Phocus and on the 35-100 a little cool, each by roughly
half the gap.

**Possible causes.**
- Phocus applies a per-lens colour correction even with lens corrections off. The camera firmware
  carries per-lens files including "blue-corner shading" (reported by blog.tonalphoto.com), but
  nobody has shown whether Phocus uses them with corrections off, or whether they act on greys away
  from the corners.
- Capture One applies something lens-specific that Phocus doesn't. Its probe renders here had Light
  Falloff, distortion and sharpness falloff at 0, so this would have to be something else.
- The glass itself differs in colour and Phocus compensates using lens metadata.

**How to test.** Shoot a grey card or white wall with both lenses, same light, same settings, then
compare the Phocus renders of the two (not Capture One): if Phocus greys differ while the camera RGB
matches, Phocus is correcting per lens. Then fit per-lens offsets the same way the DPReview offset
is fitted (`tools/fit_anchored.py` with each lens as its own set) and write two profiles,
"HNCS E4 28P" and "HNCS E4 35-100", each with its own style.

## 2. Tungsten white balance needs its own profile

**What's measured.** Three held-out tungsten-lit frames (As Shot about 3400 K) score 1.6–2.1 ΔE00
with a profile trained on As Shot frames, against 0.5–0.7 for the same frames rendered at Daylight
white balance. Frames between about 4800 and 6500 K score the same at As Shot and at Daylight. So one
profile covers daylight-range white balance; at tungsten Phocus renders colour differently.

Hasselblad told blog.tonalphoto.com that HNCS is "strongly linked to white balance parameters", and
community analysis suggests Phocus picks from several illuminant-specific matrices. The blog measured
one fixed transform holding within about 0.3 ΔE from 4500 to 8000 K, and nothing below.

**How to test / build.** Shoot 10–20 tungsten-lit frames (people and a colour chart help), export
from Phocus at As Shot, fit a separate table on those, and write it as "HNCS E4 Tungsten" with its
own style. Capture One can't switch profiles by white balance, so it would be a manual choice.
Worth checking where the switch happens (4000 K? 4500 K?) with a Kelvin sweep of one raw in Phocus.

## 3. The DPReview frames render greys about 1 b* off from yours

**What's measured.** The 33 DPReview sample raws (XCD 35-100, firmware 1.1.6.3, August 2025) sit at
+1.01 b*, about −0.6 a* on greys relative to your 35-100 frames (firmware 1.3.16.2), steady across
frames (±0.18) and unrelated to white balance. HNCS E4 handles this by fitting a separate offset for
that source, so your frames set the overall balance.

**Possible causes,** most to least likely:
- Firmware: 1.1.6.3 is pre-release. A change in what the camera writes (calibration data, white-balance
  coefficients) between versions would do this.
- Per-body variation. HNCS is generally described as per sensor model, and nothing here proves
  per-body calibration.
- Lens copy differences (same model).

**Why it matters.** If it's firmware, anyone on current firmware should see what your camera sees.
If it's per body, the profile could be up to ~1 b* off on other bodies. **How to test:** raws from
another X2D II on current firmware, or the same DPReview-era body updated.

## 4. Phocus brightens frame edges with lens corrections off

Measured on the 28P (0.26 stop at 60% of the half-diagonal) and the 35-100 (0.07 stop); the blog
measured the 55V and 90V. The cause is unknown, and its colour hasn't been measured. The fit removes
it per lens before fitting. Unknown: dependence on aperture and focus distance.

## 5. Some frames are 0.5–1 L* darker than Phocus overall

Frame to frame, not systematic. Not caused by the BaselineExposure tag (both apps apply it; frames
tagged +1 or +2 EV fit as well as untagged ones). The blog also measured Capture One defaults
landing darker by a scene-dependent amount, cause unknown.

## 6. XCD 28P corners

With Phocus lens corrections on, Capture One at Light Falloff 120 (its maximum) still leaves the 28P
corners about half a stop darker. A flat-field (LCC) calibration would close it. The 35-100 matches
to about 1 L* at 120.
