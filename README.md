# HNCS for Capture One

Camera profiles and styles that make Capture One render **Hasselblad X2D II 100C** raws the way
Hasselblad's Phocus does with its Natural Colour Solution (HNCS). They were fitted to Phocus's own
output and checked against real Capture One renders. At the frame centre they land a median of about
0.5–0.6 ΔE00 from Phocus on frames never used in fitting (CIEDE2000 colour difference; around 1 is about
the smallest difference you can see side by side).

![Phocus vs Capture One with HNCS vs Capture One default](docs/images/contact-sheet.jpg)

*Left: Phocus (Standard preset, lens corrections on). Middle: Capture One rendering a pre-processed copy
of the raw with HNCS E5. Right: Capture One's default rendering. Numbers are the median colour difference
from Phocus over the whole frame (ΔE00). None of these frames were used in fitting E5.*

This is a personal project. It's not affiliated with Hasselblad or Capture One.

## Two ways to use it

| | Simple: **HNCS E4** | Best: **HNCS E5** + LCC |
|---|---|---|
| What | one profile for every lens | a profile per lens, plus a colour LCC per lens |
| Frame centre, held-out frames (28P / 35-100) | 0.69 / 0.72 | **0.50 / 0.52** |
| Whole frame vs Phocus with corrections on (28P / 35-100) | 2.23 / 0.94 | **1.51 / 0.73** |
| Setup | copy two files, restart | the same, plus one LCC per lens |

**Closest of all (experimental):** pre-processed copies of the raws, with Phocus's lens correction
written into the raw, rendered with plain E5. On 23 photos not used in fitting, whole frame: 0.65 (28P)
/ 0.49 (35-100), against 1.38 / 0.64 for E5 + LCC and 2.07 / 0.65 for E4. See
[Pre-processed raws](#experimental-pre-processed-raws).

E5 exists for the XCD 28P and XCD 35-100, in a daylight and a tungsten version. For other lenses use
E4.

## Install

Tested with Capture One 16.9 and Phocus 4.2.2 on macOS.

1. Copy the files in `profiles/` to `~/Library/ColorSync/Profiles/`.
2. Copy the files in `styles/` to `~/Library/Application Support/Capture One/Styles/`.
3. Restart Capture One. New profiles and styles only appear after a restart.

## Use: HNCS E4

Apply **HNCS E4 + Light Falloff 120** (what Phocus gives with lens corrections on), or **HNCS E4** to
set lens correction yourself.

## Use: HNCS E5 with an LCC

Phocus shades colour across the frame, warmer toward the edges, by an amount that depends on the
lens, even with lens corrections off. A camera profile can't vary across the frame, but a Capture One
LCC (lens cast calibration) can. So E5 is a centre-accurate profile per lens plus a colour LCC per lens.

**Once per lens**, make an LCC reference from any raw you shot with that lens (its pixels are replaced;
only its metadata is used):

```sh
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
.venv/bin/python tools/make_lcc_raw.py ANY_28P_RAW.3fr "HNCS LCC 28P.3fr" --colour fit/lcc/colour_28P.npz
.venv/bin/python tools/make_lcc_raw.py ANY_35-100_RAW.3fr "HNCS LCC 35-100.3fr" --colour fit/lcc/colour_35-100.npz
```

Put the reference in your session or catalog, select it, and choose **Create LCC** in the Lens Cast
Calibration tool.

**Per image:**
1. Apply **HNCS E5 28P LCC + Light Falloff 120** (or the 35-100 one). For tungsten light, use the
   **… LCC Tungsten** version.
2. Copy the LCC from the matching reference to your images (Copy/Apply Adjustments, LCC), with
   **Color Cast on** and **Uniform Light off**.

The E5 "LCC" profiles include a correction for the overall colour shift an LCC introduces, so use them
only together with the LCC. Without it they render slightly warm.

**In all cases:**
- Keep the film curve on **Linear Response**. Phocus's tone curve is built into the profiles.
- Use **As Shot** white balance, as you would in Phocus.
- Edit as usual afterwards. The match was measured with every other adjustment at its default.

## Experimental: pre-processed raws

`tools/preprocess_3fr.py` writes a corrected copy of a 3FR with Phocus's vignetting correction and colour
shading built into the sensor data. Your original is only read. Render the copy with **HNCS E5 28P
(pre-processed)** or **HNCS E5 35-100 (pre-processed)**: plain E5 profile, Light Falloff 0, no LCC.

```sh
.venv/bin/python tools/preprocess_folder.py ~/Pictures/MySession/Capture ~/Pictures/MySession/Corrected --make-maps --make-profiles
```

`--make-maps` measures any lens setting it hasn't seen; `--make-profiles` builds an E5 profile and styles
for any lens other than the 28P and 35-100 (about five minutes, Phocus only) and installs them; restart
Capture One afterwards. Both drive Phocus unattended, so don't use it while they run. Each copy gets a
Capture One settings file, so it opens with the right profile, Linear Response and Light Falloff 0 the
first time Capture One sees it; for files Capture One already knows, apply the "(pre-processed)" style.

Import the `Corrected` folder (same file names), or run `tools/preprocess_3fr.py` on single files.

It needs a map for the lens, focal length and aperture; `fit/preprocess_maps/` has a few dozen for the
28P and 35-100. `tools/auto_maps.py YOUR_RAWS…` makes the missing ones with Phocus, unattended (see
[tools/README.md](tools/README.md#pre-processing)). Costs: a full-size copy of each raw, and brightening
the corners uses highlight headroom there (2.3% of photosites clipped on an f/16 frame with bright sky in
the corners).

## Known limits

- **One camera.** Each X2D II carries a factory calibration record that Phocus uses to normalise the
  body and Capture One ignores. The profiles match the body they were made on; another body can differ
  by about 1 b*. `tools/body_gains.py YOUR_RAW.3fr` prints the input gain that adapts a profile to your
  body (pass it to `tools/write_profile.py --input-gain`).
- **White balance.** Phocus's colour shifts with white balance. The main profiles are an average over
  about 4700–6300 K. For tungsten-lit frames (about 3100–4200 K) use the **E5 … LCC Tungsten** styles
  instead: on real tungsten photos they're 1.0–1.7 ΔE00 from Phocus, against 2.0–2.8 with the daylight
  ones. The 28P tungsten profile is checked only on synthetic data.
- **XCD 28P at f/5.6 and narrower.** Phocus corrects vignetting more strongly than Capture One's Light
  Falloff 120, so the edges stay darker than Phocus (it matches at f/4).
- **Variation between frames.** Phocus adjusts brightness slightly by lens setting; pre-processing
  includes that, the profile-only routes don't (up to about ±0.5 L\* on the 35-100 between 45 and 75 mm).
  About ±0.2 L\* per frame remains unexplained.
- **Phocus defaults only.** The match is to Phocus's Standard response in its default working space.
  Other responses or working spaces render 3–7 ΔE00 differently.

More in [docs/open-questions.md](docs/open-questions.md).

## How it was made

**E1–E4** were fitted to real photographs rendered in both apps. Each raw was rendered by Phocus (with
everything but colour and tone switched off) and by Capture One through a "probe" profile that exposes
the exact camera RGB a profile receives. A smooth 33 × 33 × 33 lookup table from camera RGB to
Phocus's Lab was fitted to the pairs.

**E5** was fitted without any real photos. X2D II raws store uncompressed sensor data, so a copy of a
real raw can be filled with colour patches of exactly known camera RGB. Phocus's hot folder renders
them without the GUI. That made it possible to:
- measure Phocus across the whole colour range at several white balances;
- map its spatial shading with synthetic flat fields;
- find which file metadata changes its output: one maker-note entry holding two calibration gains.

The step-by-step notes are in [docs/research-log.md](docs/research-log.md); the overview is in
[docs/methodology.md](docs/methodology.md).

## Repository layout

```
profiles/   HNCS E4 (all lenses); HNCS E5 28P LCC, HNCS E5 35-100 LCC, and a Tungsten version of each;
            plain HNCS E5 28P / 35-100 for pre-processed raws
styles/     a plain and a "+ Light Falloff 120" style for each profile
fit/        lut_e4.npz, lut_e5_*.npz (daylight and tungsten)   fitted 33³ tables before ICC encoding
            lcc/          colour shading maps for the LCC references, and the profiles' input gains
            preprocess_maps/  raw-gain maps by lens state for preprocess_3fr.py; c1_response.npz
            synthetic/    Phocus's renders of the synthetic patches (camera RGB → Lab) and flat-field maps
            configs/      frames and settings of the E4 fit
docs/       results, methodology, research log, open questions, original design, contact sheet
tools/      Python and AppleScript: synthetic raws, pairing, fitting, profiles, LCCs, validation
```

Earlier versions (E1–E3) are in the git history.

## Experimenting

- **Edit a table and re-export.** Each `fit/lut_*.npz` holds a fitted table (`lut`, 33³ × Lab):
  `python tools/write_profile.py fit/lut_e5_28p.npz "HNCS Mine" out/`
- **Refit from the synthetic data** in `fit/synthetic/`, no Phocus needed:
  `python tools/fit_synthetic.py out.npz --gainmap fit/synthetic/flat_maps/F35aoff.npz --pairs fit/synthetic/pairs/HNCSgridA0.npz …`
- **Measure your own camera or another lens** with synthetic raws: see [tools/README.md](tools/README.md).

## Credits

[blog.tonalphoto.com](https://blog.tonalphoto.com/) for the Lightroom profile that inspired this, and
for its measurements of Phocus (HNCS and white balance, edge brightening, BaselineExposure, lens files
in the firmware, the Phocus hot folder).

## License

[MIT](LICENSE) for the profiles, styles, tables, data, tools and docs. The example photographs in
`docs/images/` are © Scott Walker, all rights reserved.
