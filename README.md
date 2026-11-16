# HNCS for Capture One

Camera profiles, styles and tools that make Capture One render **Hasselblad X2D II 100C** raws the way
Hasselblad's Phocus does with its Natural Colour Solution (HNCS). Everything was fitted to Phocus's own
output and checked against real Capture One renders. The closest route lands a median of about 0.5 ΔE00
from Phocus over the whole frame, corners included, on photos never used in fitting (CIEDE2000 colour
difference; around 1 is about the smallest difference you can see side by side).

![Phocus vs Capture One with HNCS vs Capture One default](docs/images/contact-sheet.jpg)

*Left: Phocus (Standard preset, lens corrections on). Middle: Capture One rendering a pre-processed copy
of the raw with HNCS E5. Right: Capture One's default rendering. Numbers are the median colour difference
from Phocus over the whole frame (ΔE00). None of these frames were used in fitting E5.*

This is a personal project. It's not affiliated with Hasselblad or Capture One.

## Three ways to use it

| | **Pre-processed + HNCS E5** (closest) | HNCS E5 + LCC | HNCS E4 (simplest) |
|---|---|---|---|
| What | a corrected copy of each raw, rendered with a per-lens profile | a per-lens profile plus a colour LCC per lens | one profile for every lens |
| Whole frame vs Phocus with corrections on, 23 unseen photos (28P / 35-100) | **0.65 / 0.49** | 1.38 / 0.64 | 2.07 / 0.65 |
| Needs | Python, and Phocus for lens settings not yet measured | an LCC reference per lens | nothing extra |
| Lenses | 28P, 35-100 and 38V built in; others built automatically from your raws | 28P and 35-100 | any |

Pre-processing writes Phocus's lens correction, colour shading and per-lens-setting brightness (lens,
focal length, aperture and focus distance) into a copy of the raw, so Capture One needs no LCC and no
Light Falloff. The 28P's corners, which the profile-only routes can't match at f/5.6 and narrower, come
out right. Your originals are only read. Details and numbers: [docs/results.md](docs/results.md).

All three have daylight profiles (about 4700–6300 K); E5 also has **tungsten** versions (about
3100–4200 K) for the 28P and 35-100.

## Install

Tested with Capture One 16.9 and Phocus 4.2.2 on macOS.

1. Copy the files in `profiles/` to `~/Library/ColorSync/Profiles/`.
2. Copy the files in `styles/` to `~/Library/Application Support/Capture One/Styles/`.
3. Restart Capture One. New profiles and styles only appear after a restart.
4. For pre-processing or LCC references, set up the tools once:
   `python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt`

## Use: pre-processed raws + HNCS E5

```sh
.venv/bin/python tools/preprocess_folder.py ~/Pictures/MySession/Capture ~/Pictures/MySession/Corrected --make-maps --make-profiles
```

- Writes a corrected copy of every raw into `Corrected` (same file names). Import or browse that folder.
- Each copy gets a Capture One settings file, so it opens with the right profile (**HNCS E5 28P**,
  **HNCS E5 35-100** or **HNCS E5 38V**), Linear Response and Light Falloff 0. For files Capture One
  has seen before, apply the **HNCS E5 … (pre-processed)** style instead.
- `--make-maps` measures any combination of lens, focal length, aperture and focus distance it hasn't
  seen (`fit/preprocess_maps/` has 52 for the 28P, 35-100 and 38V; without `--make-maps` a missing focus
  distance uses the nearest one measured). `--make-profiles` builds an E5 profile and
  styles for any other lens, from Phocus renders alone, and installs them (restart Capture One). Both run
  Phocus unattended, so don't use it meanwhile.
- Costs: a full-size copy of each raw, and brightened corners use some highlight headroom (about 2% of
  photosites clipped on a few frames with bright sky in the corners; those areas render near white in
  HNCS anyway).

## Use: HNCS E5 with an LCC

Phocus shades colour across the frame (less blue toward the edges) by an amount that depends on the lens,
even with lens corrections off. A Capture One LCC can reproduce that.

**Once per lens**, make an LCC reference from any raw you shot with that lens (its pixels are replaced;
only its metadata is used), then put it in your session or catalog and choose **Create LCC**:

```sh
.venv/bin/python tools/make_lcc_raw.py ANY_28P_RAW.3fr "HNCS LCC 28P.3fr" --colour fit/lcc/colour_28P.npz
.venv/bin/python tools/make_lcc_raw.py ANY_35-100_RAW.3fr "HNCS LCC 35-100.3fr" --colour fit/lcc/colour_35-100.npz
```

**Per image:** apply **HNCS E5 28P LCC + Light Falloff 120** (or the 35-100 or **… Tungsten** version),
then copy the LCC from the matching reference with **Color Cast on** and **Uniform Light off**. The "LCC"
profiles correct for the overall colour shift an LCC introduces, so use them only with the LCC.

## Use: HNCS E4

Apply **HNCS E4 + Light Falloff 120** (what Phocus gives with lens corrections on), or **HNCS E4** to set
lens correction yourself.

**In all cases:** keep the film curve on **Linear Response** (Phocus's tone curve is built into the
profiles), use **As Shot** white balance, and edit as usual afterwards.

## Known limits

- **One camera model.** Each X2D II carries a factory calibration record that Phocus uses to normalise
  the body and Capture One ignores; the profiles match the body they were made on. `tools/body_gains.py
  YOUR_RAW.3fr` prints the correction for another body (pre-processing can apply it: `--body-gains`).
- **White balance.** Phocus's colour shifts with white balance. Use the tungsten profiles for tungsten
  light (1.0–1.7 ΔE00 on real tungsten photos, against 2.0–2.8 with the daylight ones); mixed light is
  untested.
- **Profile-only routes.** Without pre-processing, the 28P's corners at f/5.6 and narrower stay darker
  than Phocus, and Phocus's per-lens-setting brightness (up to about ±0.5 L\* on the 35-100 between 45
  and 75 mm) isn't included. About ±0.2 L\* per frame remains unexplained in every route.
- **Highlights.** Where a sensor channel clips, Phocus keeps some colour and its Highlight Recovery can
  rebuild the clipped channel; Capture One can't, and no profile can change that.
- **Phocus defaults only.** The match is to Phocus's Standard response in its default working space.

More in [docs/open-questions.md](docs/open-questions.md).

## How it was made

**E1–E4** were fitted to real photographs rendered in both apps: Phocus with everything but colour and tone
switched off, and Capture One through a "probe" profile that exposes the exact camera RGB a profile
receives. A smooth 33 × 33 × 33 table from camera RGB to Phocus's Lab was fitted to the pairs.

**E5** was fitted without any real photos. X2D II raws store uncompressed sensor data, so a copy of a real
raw can be filled with colour patches of exactly known camera RGB, and Phocus's hot folder renders them
without its GUI. That made it possible to measure Phocus across the whole colour range at many white
balances, map its spatial processing with synthetic flat fields, and find which metadata drives it: two
factory calibration gains per body, and a 34-byte lens identity that Phocus uses to look up its own lens
data.

**Pre-processing** applies that measured spatial processing to the raw itself, through Capture One's raw
response curve.

The step-by-step notes are in [docs/research-log.md](docs/research-log.md); the overview is in
[docs/methodology.md](docs/methodology.md). A write-up for blog.tonalphoto.com's author is in
[docs/writeup.md](docs/writeup.md).

## Repository layout

```
profiles/   HNCS E5 28P / 35-100 / 38V (plain, for pre-processed raws); E5 … LCC and LCC Tungsten; HNCS E4
styles/     "(pre-processed)", plain and "+ Light Falloff 120" styles for each profile
fit/        lut_e4.npz, lut_e5_*.npz            fitted 33³ tables before ICC encoding
            preprocess_maps/  Phocus's spatial processing by lens, focal length, aperture and focus, as raw gains
            lens_references.json, c1_response.npz, c1_patch_lookup.npz   pre-processing and new-lens data
            lcc/          colour shading maps for the LCC references, and the profiles' input gains
            synthetic/    Phocus's renders of the synthetic patches (camera RGB → Lab) and flat-field maps
docs/       results, methodology, research log, open questions, write-up, contact sheet
tools/      Python and AppleScript: pre-processing, synthetic raws, driving Phocus, fitting, profiles, scoring
```

Earlier versions (E1–E3) are in the git history.

## Experimenting

- **Edit a table and re-export.** Each `fit/lut_*.npz` holds a fitted table (`lut`, 33³ × Lab):
  `python tools/write_profile.py fit/lut_e5_28p.npz "HNCS Mine" out/`
- **Refit from the synthetic data** in `fit/synthetic/`, no Phocus needed:
  `python tools/fit_synthetic.py out.npz --gainmap fit/synthetic/flat_maps/F35aoff.npz --pairs fit/synthetic/pairs/HNCSgridA0.npz …`
- **Another lens:** `python tools/auto_lens_profile.py YOUR_RAWS… --install`. More in
  [tools/README.md](tools/README.md).

## Credits

[blog.tonalphoto.com](https://blog.tonalphoto.com/) for the Lightroom profile that inspired this, and
for its measurements of Phocus (HNCS and white balance, edge brightening, BaselineExposure, lens files
in the firmware, the Phocus hot folder).

## License

[MIT](LICENSE) for the profiles, styles, tables, data, tools and docs. The example photographs in
`docs/images/` are © Scott Walker, all rights reserved.
