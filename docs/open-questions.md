# Open questions

What's still unresolved, with what's known and how to test it. The measurements behind each item are in
[research-log.md](research-log.md); answered questions are listed at the end.

## Work list

**Accuracy**
- [ ] **Overall brightness with the LCC route** (Finding 42). Some photos come out uniformly brighter or
  darker than with a corrected copy of the raw: up to ±0.4 L\* on the 28P, and −0.85 L\* on the 38V frame
  B0001059 (0.82 ΔE00, against 0.35 with a corrected copy). It doesn't follow orientation,
  BaselineExposure or focus code. Things to test: whether the LCC calibration, measured on L\* 60 flats,
  holds at the photo's own brightness; and whether the offset is the same for every photo of one lens
  setting.
- [ ] **About ±0.2 L\* per photo** remains after Phocus's per-lens-setting brightness (Finding 27). One
  candidate is the maker-note entries that can't be swapped in place.
- [ ] **The 38V renders about 0.2 L\* darker** than Phocus on every frame (Finding 32). A lightness offset
  in its table would fix it if it holds on more scenes.
- [ ] **Very saturated colours** above C\* 130 still run 9–13 C\* short of Phocus (Finding 38), because of
  the profile encoding's limits.

**White balance**
- [ ] **Shade profiles**, like the tungsten ones: fitted on 7000–8000 K grids ("HNCS E5 … Shade"), and
  picked automatically like the tungsten ones. Colourful synthetic patches drift to about 1.3 ΔE00 at
  6500 K and 2.2 at 8000 K (Finding 33); three real shade photos scored 0.58–0.78.
- [ ] **The 28P tungsten profile** on real tungsten photos (only the 35-100's has been checked).
- [ ] **Between daylight and tungsten** (about 4200–4700 K), and mixed light: untested.
- [ ] **Changing white balance in Capture One** replaces the small LCC colour correction carried in the
  white balance. Worth measuring how much that costs, and whether a style could restore it.

**Coverage**
- [ ] **More bodies.** The body correction has been checked on three bodies (Findings 13, 35). Raws from
  other X2D II bodies would test it further.
- [ ] **More lens settings** for the 25V, 55V, 90V, 120 Macro and 135: each was tested at one setting only.
- [ ] **Catalogs.** Settings files have only been tested in Capture One sessions.
- [ ] **Real pushed photos.** On synthetic patches a push renders the same as more light in both apps
  (Finding 33); not yet checked on real pushed frames.
- [ ] **Phocus 4.2.3.** Everything was fitted and checked on Phocus 4.2.2; blog.tonalphoto.com's latest
  numbers are on 4.2.3. Re-render a few synthetic grids and flats after updating to see whether HNCS or
  the lens processing changed.
- [ ] **Reproduction responses**, if wanted: synthetic grids rendered with `ColorModel` 1 or 4, fitted
  like the Standard profiles.

## Answered

| Question | Answer | Findings |
|---|---|---|
| What is HNCS made of? | A colour stage (matrix + 3-D table, the matrix shifting with white balance), then one tone curve per channel in Hasselblad RGB | 11, 14 |
| What do Phocus's Response and Working Space menus do? | `ColorModel` 0 / 1 / 4 / 5 = Standard / Reproduction / Reproduction Low Gain / Negative; `ColorWorkingSpace` 0 is Hasselblad RGB | 18, 19, 20 |
| Why do bodies render differently in Phocus? | A factory GAIN record in the maker note: a green and a blue gain | 1, 2, 13, 16, 35 |
| Does Phocus use focus distance? | Yes, from byte 6 of maker-note 0x0018. It changes vignetting correction and centre brightness, most on the 55V and 90V; colour shading doesn't change | 31, 36 |
| Where does Phocus's lens behaviour come from? | A 34-byte lens identity in the raw, looked up in data built into Phocus | 29, 30 |
| Why do some photos differ in overall lightness? | Mostly Phocus's brightness per lens setting, now in the maps | 27 |
| Can Capture One reproduce Phocus's lens correction across the frame? | Yes: an LCC per lens setting, calibrated, in a settings file per raw | 39, 40, 41, 42 |
| Does Phocus handle highlights better? | It keeps colour where one channel clips, and Highlight Recovery rebuilds clipped channels; Capture One can't | 23, 25 |
| Tungsten light? | Separate tungsten profiles, picked automatically below 4400 K | 21, 42 |
| Bright yellows and saturated colours? | Kept, after fixing how the profiles fade and compress colour | 34, 37, 38 |
| Profiles for lenses not owned? | Built from Phocus renders alone, from any raw of the lens | 26, 32, 35 |
