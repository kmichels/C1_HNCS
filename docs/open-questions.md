# Open questions

What's still unresolved, with what's known and how to test it. Resolved questions are listed at the end.
Numbers are from [results.md](results.md) and [research-log.md](research-log.md).

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

## 3. Other bodies

Phocus normalises each body with two channel gains from a factory calibration record in the maker note
(entry 0x0019, bytes 84–87, two half-floats). Capture One ignores them. So the profiles match the body
they were fitted on, and another X2D II can differ by about 1 b*.

**Possible fix.** Measure how Phocus maps those two gains to its correction (a synthetic sweep of
sensible values). Then read any body's record and derive a per-body input-gain variant of the profile.

## 4. Remaining per-frame lightness differences

Some real frames are 0.5–1 L* darker in Capture One than in Phocus overall. It isn't BaselineExposure
(both apps apply it), and it isn't the factory gains (colour, not lightness). Candidates:
- the ~0.2 L* left in the maker-note entries that can't be swapped in place (newer focus-distance
  fields 0x0081–0x0083);
- focus-distance-dependent lens processing, which the blog reports Phocus does with lens corrections
  on.

## 5. Mechanism of Phocus's spatial colour shading

Measured precisely, but its source isn't confirmed. The likely source is the per-lens "blue-corner
shading" files in the camera firmware's lens database (reported by blog.tonalphoto.com). It is
applied whether lens corrections are on or off, and the brightness lift it brings with corrections off
is the "edge brightening" earlier versions removed by hand. Unknown: dependence on focus distance; the
28P shows slightly more colour at f/4 than at f/8 in the extreme corners.

## Resolved

- **"The two lenses render greys about 1 b* apart."** It's mostly Phocus's radial colour shading,
  which real-photo fits averaged over the frame. At the centre the only lens effect is 0.8 L* of
  brightness. E5 handles both: a per-lens table, and an LCC for the shading.
- **"The DPReview frames render greys about 1 b* off."** It's the factory calibration record (question 3),
  not firmware, serial or scene content.
- **"The 28P corners stay half a stop dark."** That's question 1: it depends on aperture.
