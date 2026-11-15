# HNCS for Capture One

A camera profile and two styles that make Capture One render **Hasselblad X2D II 100C** raws the way
Hasselblad's Phocus does with its Natural Colour Solution (HNCS). The profile was fitted to Phocus's
own output, then checked against real Capture One renders. On frames it never saw, it lands a median
of about 0.6–0.8 ΔE00 from Phocus (CIEDE2000 colour difference; around 1 is about the smallest
difference you can see side by side).

![Phocus vs Capture One with HNCS vs Capture One default](docs/images/contact-sheet.jpg)

*Left: Phocus (Standard preset, lens corrections on). Middle: Capture One with the HNCS style (this
sheet was made with the previous version, E3; E4 scores within about 0.1 of it on these frames).
Right: Capture One's default rendering. Numbers are the median colour difference from Phocus over the
whole frame. Details in [docs/results.md](docs/results.md).*

This is a personal project. It's not affiliated with Hasselblad or Capture One.

## Install

Tested with Capture One 16.9 and Phocus 4.2.2 on macOS.

1. Copy `profiles/HasselbladX2DII100C-HNCS E4.icm` to `~/Library/ColorSync/Profiles/`.
2. Copy both files in `styles/` to `~/Library/Application Support/Capture One/Styles/`.
3. Restart Capture One. New profiles and styles only appear after a restart.

The profile then shows up under the camera as **Hasselblad X2D II 100C HNCS E4**.

## Use

Apply a style to your X2D II images:

| Style | Sets | Use when |
|---|---|---|
| **HNCS E4 + Light Falloff 120** | the profile, the Linear Response film curve, Light Falloff 120 | You want what Phocus gives with lens corrections on (the usual case). |
| **HNCS E4** | the profile and the Linear Response film curve | You want to set lens correction yourself. |

- Keep the film curve on **Linear Response**. Phocus's tone curve is built into the profile, so
  Capture One's other film curves would apply tone twice.
- Use **As Shot** white balance, as you would in Phocus. The profile is for daylight-range white
  balance (about 4800–6500 K); tungsten-balanced shots drift (see below).
- Edit as usual afterwards. The match was measured with every other adjustment at its default.

## How well it matches

| | Median ΔE00 from Phocus |
|---|---|
| Capture One default (ProStandard, Auto curve), centre of frame | 3.3–4.5 |
| **HNCS E4**, held-out frames from the XCD 28P / XCD 35-100 | **0.81 / 0.71** |
| **HNCS E4**, held-out portraits and colourful scenes (DPReview raws, source offset applied) | **0.57** |
| HNCS + Light Falloff 120 vs Phocus with lens corrections on, XCD 35-100, whole frame | 0.95 |
| Same, XCD 28P, whole frame | about 2: the corners stay about half a stop darker |

For scale: the same camera colour in two different Phocus frames already differs by a median of about
1.6 ΔE00 at this block size. The Lightroom profile by blog.tonalphoto.com that inspired this project
reached 0.94.

**Known limits:**
- One camera (X2D II 100C), two lenses tested (XCD 28P, XCD 35-100).
- Daylight-range white balance only. At tungsten (about 3400 K) Phocus changes its colour rendering
  and this profile is 1.6–2.1 ΔE00 off.
- Phocus renders greys about 1 b* differently between the two lenses; the profile averages them.
- Some frames come out 0.5–1 L* darker than Phocus overall.

These are written up with what's known and how to test them in
[docs/open-questions.md](docs/open-questions.md).

## How it was made

Each raw was rendered twice. Phocus rendered it with everything except colour and tone switched off.
Capture One rendered it through a "probe" profile that exposes the exact camera RGB a camera profile
receives. Both renders were cut into small blocks, and a 33 × 33 × 33 lookup table from camera RGB to
Phocus's Lab was fitted to them by least squares, kept smooth, and evaluated tetrahedrally the way
Capture One evaluates it. That table became the camera profile, which was then rendered for real and
compared with Phocus again.

Two complications. Phocus brightens frame edges by a lens-specific amount even with corrections off;
that was measured and removed before fitting, and with corrections on, Light Falloff 120 brings
Capture One close to Phocus's vignetting correction. And Phocus renders greys slightly differently
depending on where the raws came from; the fit lets the profile owner's own frames set the overall
balance, while sample raws from another camera contribute only colour shapes such as skin tones.

The full story is in [docs/methodology.md](docs/methodology.md). The original plan is in
[docs/original-design.md](docs/original-design.md).

## Repository layout

```
profiles/   HasselbladX2DII100C-HNCS E4.icm    the camera profile
styles/     HNCS E4.costyle, HNCS E4 + Light Falloff 120.costyle
fit/        lut_e4.npz                          the fitted 33³ table before ICC encoding
            configs/e4.json                     frames and settings of the E4 fit
docs/       methodology, results, open questions, original design, contact sheet
tools/      Python and AppleScript used to capture, pair, fit, write and validate
```

Earlier versions (E1–E3) are in the git history.

## Experimenting

- **Edit the table and re-export.** `fit/lut_e4.npz` holds the fitted table (`lut`, 33³ × Lab).
  Change it and write a new profile and style:
  `python tools/write_profile.py fit/lut_e4.npz "HNCS Mine" out/`
- **Refit, or add frames or lenses.** Follow [tools/README.md](tools/README.md). You need Phocus,
  Capture One, the raws, and a Phocus export of every frame.

## Credits

- 33 sample raws from [DPReview's Hasselblad X2D II 100C sample gallery](https://www.dpreview.com/sample-galleries/4239298554/hasselblad-x2d-ii-100c-sample-gallery)
  were used for fitting. They are not redistributed here; download them from DPReview, under its
  terms.
- [blog.tonalphoto.com](https://blog.tonalphoto.com/) for the Lightroom profile that inspired this,
  and for its measurements of Phocus (HNCS and white balance, edge brightening, BaselineExposure,
  the Modify dialog's white-balance copying).

## Status

E4, November 2026. Open questions and next steps are in
[docs/open-questions.md](docs/open-questions.md).

## License

[MIT](LICENSE) for the profile, the styles, the fitted table, the tools and the docs. The example
photographs in `docs/images/` are © Scott Walker, all rights reserved.
