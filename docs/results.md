# Results

All numbers are CIEDE2000 (ΔE00) between Capture One and Phocus, computed on per-block mean Lab.
For the 28P the blocks are 32 × 32 px at full size; for the 35-100, 16 × 16 px at half size, which is
the same area of the frame. Unless stated otherwise, blocks with clipped channels are excluded, and
so is everything beyond 50–60% of the half-diagonal from the centre. "Median" is the median over blocks
in a frame.

**How close is close?** The same camera RGB, in different frames, lands a median of **1.6 ΔE00** apart in
Phocus (6,148 cross-frame pairs from the 28P frames). Blocks mix textures and Phocus does some local processing, so a
per-frame median well under 1 is near the practical floor for this measurement. For reference, the
Lightroom profile by blog.tonalphoto.com that inspired this project reached a median of 0.94.

## HNCS E3 (current)

Frames held out of the fit, rendered for real in Capture One with the HNCS E3 style and Light
Falloff 0, compared with Phocus (lens corrections off) within 30% of the half-diagonal from the centre:

| Frame | Lens | Capture One + HNCS E3 | E2 (previous profile), LUT prediction, same region |
|---|---|---|---|
| 912 | XCD 28P | 0.67 | 0.51 |
| 929 | XCD 28P | 0.72 | 1.33 |
| 939 | XCD 28P | 0.86 | 0.82 |
| 623 | XCD 35-100 @ 35 mm | 0.81 | 1.57 |
| 679 | XCD 35-100 @ 35 mm | 0.99 | 1.54 |
| 703 | XCD 35-100 @ 35 mm | 0.67 | 1.20 |
| 829 | XCD 35-100 @ 80 mm | 0.63 | 1.36 |
| 863 | XCD 35-100 @ 35 mm | 0.54 | 0.89 |

- Capture One reproduces the fitted LUT closely: on the 35-100 frames, render vs prediction differs by
  about 0.2 L* or less in every tone band, with chroma within 0.3.
- What's left is mostly frame-to-frame exposure: a few frames are 0.5–1 L* darker than Phocus
  everywhere, centre included. One profile can't absorb that, because it changes from frame to frame.
- E2 was fitted on the 28P alone and rendered the 35-100 about 1.5 b* more yellow than Phocus. E3 was
  fitted on both lenses and removes that shift without hurting the 28P.

Earlier experiments on the same three held-out 28P frames (912 / 929 / 939):

| Version | What changed | Median ΔE00 |
|---|---|---|
| Capture One default (ProStandard, Auto curve) | — | 4.50 / 3.84 / 3.27 |
| E1, real renders | First fitted profile, 28P only | 0.86 / 1.19 / 0.95 |
| E2, LUT prediction | Phocus edge brightening removed before fitting | 0.62 / 1.07 / 0.81 |
| E3, LUT prediction | Both lenses | 0.60 / 1.01 / 0.85 |

## Light Falloff vs Phocus with lens corrections ON

Phocus's vignetting correction is stronger than Capture One's at the default Light Falloff of 100.
The slider stops at 120.

**XCD 35-100** (HNCS E3; frames 623, 679 @ 35 mm and 702 @ 50 mm; whole frame out to the corners):

| Light Falloff | Mean of frame medians | Lightness gap in the corners |
|---|---|---|
| 0 | 3.43 | −7 to −13 L* |
| 60 | 1.99 | −4 to −7 L* |
| 80 | 1.57 | −3 to −5 L* |
| 100 | 1.21 | −2 to −3 L* |
| **120** | **0.95** | **about −1 L*** |

**XCD 28P** (HNCS E2; frames 901, 917, 931):

| Setting | Mean of frame medians | Lightness gap, 60–80% out → corners |
|---|---|---|
| Light Falloff 100 | 2.99 | −6 → −10 L* |
| **Light Falloff 120** | **1.93** | −3 to −4 → −6 to −7 L* |
| Light Falloff 120 + Vignetting +0.25 EV | 2.03 | right on two frames, overshoots on the third |
| Light Falloff 120 + Vignetting +0.5 EV | 2.79 | overshoots |

So Light Falloff 120 is the right setting for both lenses. The 35-100 then matches Phocus out to the
corners. The 28P's corners stay about half a stop darker than Phocus. Adding positive Vignetting
doesn't fix that reliably, because the tool brightens the middle of the frame too. An exact match for
the 28P would need a flat-field (LCC) calibration.

The `HNCS E3 + Light Falloff 120` style was checked: its render is pixel-identical to applying
`HNCS E3` and setting Light Falloff to 120 by hand.

## Contact sheet

![Phocus vs Capture One + HNCS E3 vs Capture One default](images/contact-sheet.jpg)

- Phocus: Standard preset, lens corrections ON (vignetting only).
- Capture One + HNCS E3: the `HNCS E3 + Light Falloff 120` style.
- Capture One default: reset adjustments (ProStandard, Auto curve, Light Falloff 100).
- Distortion correction is off in both apps so the pixels line up; every panel is drawn from the same
  per-block mean Lab grid that the scores use. Scores here cover the whole frame, corners included.
- Frames 623 and 679 were held out of the colour fit. Frames 901 and 917 were in it; they're shown
  because they're the 28P frames with vignetting-on Phocus exports. On the 28P the remaining
  difference is mostly the darker corners described above.

## Phocus edge brightening with corrections off

Even with lens corrections off, Phocus brightens toward the frame edges. Measured against a
centre-calibrated LUT (r = distance from the centre / half-diagonal):

| Lens | Lift (stops) | At r = 0.3 / 0.5 / 0.6 |
|---|---|---|
| XCD 28P | 0.619 r² + 0.300 r⁴ | 0.06 / 0.17 / 0.26 |
| XCD 35-100 | 0.201 r² − 0.032 r⁴ | 0.02 / 0.05 / 0.07 |

For the 35-100, single frames range from 0.02 to 0.11 stop at r = 0.6, a little less at 75–100 mm
than at 35–60 mm, across f/8 to f/16.
