# HNCS for Capture One

A camera profile and two styles that make Capture One render **Hasselblad X2D II 100C** raws the way
Hasselblad's Phocus does with its Natural Colour Solution (HNCS). The profile was fitted to Phocus's
own output, then checked against real Capture One renders. On frames it never saw, it lands a median
of 0.5–1.0 ΔE00 from Phocus (CIEDE2000 colour difference; around 1 is about the smallest difference
you can see side by side).

![Phocus vs Capture One with HNCS E3 vs Capture One default](docs/images/contact-sheet.jpg)

*Left: Phocus (Standard preset, lens corrections on). Middle: Capture One with the
`HNCS E3 + Light Falloff 120` style. Right: Capture One's default rendering. Numbers are the median
colour difference from Phocus over the whole frame. Details in [docs/results.md](docs/results.md).*

This is a personal project. It's not affiliated with Hasselblad or Capture One.

## Install

Tested with Capture One 16.9 and Phocus 4.2.2 on macOS.

1. Copy `profiles/HasselbladX2DII100C-HNCS E3.icm` to `~/Library/ColorSync/Profiles/`.
2. Copy both files in `styles/` to `~/Library/Application Support/Capture One/Styles/`.
3. Restart Capture One. New profiles and styles only appear after a restart.

The profile then shows up under the camera as **Hasselblad X2D II 100C HNCS E3**.

## Use

Apply a style to your X2D II images:

| Style | Sets | Use when |
|---|---|---|
| **HNCS E3 + Light Falloff 120** | the profile, the Linear Response film curve, Light Falloff 120 | You want what Phocus gives with lens corrections on (the usual case). |
| **HNCS E3** | the profile and the Linear Response film curve | You want to set lens correction yourself. |

- Keep the film curve on **Linear Response**. Phocus's tone curve is built into the profile, so
  Capture One's other film curves would apply tone twice.
- Use **As Shot** white balance, as you would in Phocus.
- Edit as usual afterwards. The match was measured with every other adjustment at its default.

## How well it matches

| | Median ΔE00 from Phocus |
|---|---|
| Capture One default (ProStandard, Auto curve), centre of frame | 3.3–4.5 |
| **HNCS E3**, centre of frame, 8 held-out frames, both lenses | **0.54–0.99** |
| HNCS E3 + Light Falloff 120 vs Phocus with lens corrections on, XCD 35-100, whole frame | 0.95 |
| Same, XCD 28P, whole frame | about 2: the corners stay about half a stop darker |

For scale: the same camera colour in two different Phocus frames already differs by a median of about
1.6 ΔE00 at this block size. The Lightroom profile by blog.tonalphoto.com that inspired this project
reached 0.94.

Known limits: one camera; trained on 29 mostly daylight outdoor frames from the XCD 28P and XCD 35-100
(no skin tones, tungsten light or saturated artificial colours yet); some frames come out 0.5–1 L*
darker than Phocus overall. More in [docs/methodology.md](docs/methodology.md#limits).

## How it was made

Each raw was rendered twice. Phocus rendered it with everything except colour and tone switched off.
Capture One rendered it through a "probe" profile that exposes the exact camera RGB a camera profile
receives. Both renders were cut into small blocks, and a 33 × 33 × 33 lookup table from camera RGB to
Phocus's Lab was fitted to them by least squares, kept smooth, and evaluated tetrahedrally the way
Capture One evaluates it. That table became the camera profile, which was then rendered for real and
compared with Phocus again.

One complication: Phocus brightens frame edges by a lens-specific amount even with corrections off.
That was measured and removed before fitting. With corrections on, Light Falloff 120 brings Capture
One close to Phocus's vignetting correction.

The full story is in [docs/methodology.md](docs/methodology.md). The original plan is in
[docs/original-design.md](docs/original-design.md).

## Repository layout

```
profiles/   HasselbladX2DII100C-HNCS E3.icm    the camera profile
styles/     HNCS E3.costyle, HNCS E3 + Light Falloff 120.costyle
fit/        lut_e3c.npz                        the fitted 33³ table before ICC encoding
docs/       methodology, results, original design, contact sheet
tools/      Python and AppleScript used to capture, pair, fit, write and validate
```

## Experimenting

- **Edit the table and re-export.** `fit/lut_e3c.npz` holds the fitted table (`lut`, 33³ × Lab).
  Change it and write a new profile and style:
  `python tools/write_profile.py fit/lut_e3c.npz "HNCS Mine" out/`
- **Refit, or add frames or lenses.** Follow [tools/README.md](tools/README.md). You need Phocus,
  Capture One, the raws, and a Phocus export of every frame.

## Status

Paused after E3 (November 2026). Next ideas: a flat-field (LCC) calibration for the 28P corners, more
varied scenes and light, and more lenses. See
[docs/methodology.md](docs/methodology.md#ideas-for-next-steps).
