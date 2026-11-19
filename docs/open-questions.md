# Open questions

What's still unresolved, with what's known and how to test it. The measurements behind each item are in
[research-log.md](research-log.md); answered questions are listed at the end.

## Work list

**Accuracy**
- [ ] **About ±0.2 L\* per photo** remains after Phocus's per-lens-setting brightness (Finding 27). One
  candidate is the maker-note entries that can't be swapped in place.
- [ ] **Very saturated colours** above C\* 130 still run 9–13 C\* short of Phocus (Finding 38), because of
  the profile encoding's limits.

**White balance**
- [ ] **Real shade photos** for the 38V, 25V, 55V, 90V, 120 Macro and 135, whose shade profiles are checked
  on synthetic grids only (Finding 45), and more for the 28P, checked on one photo.
- [ ] **Real tungsten photos** for every lens but the 35-100 (the others are checked on synthetic grids).
  `auto_lens_profile.py --light tungsten` builds them (Finding 46).
- [ ] **Between daylight and tungsten** (about 4200–4700 K), and mixed light: untested.

- [ ] **Several cameras at once.** Profiles can carry one camera's factory-gain correction
  (`bake_lcc_colour.py --body`, Finding 48); photos from any other camera still carry theirs in the white
  balance, so a preset or As Shot drops it there.

**Coverage**
- [ ] **More bodies.** The body correction has been checked on three bodies (Findings 13, 35). Raws from
  other X2D II bodies would test it further.
- [ ] **More lens settings** for the 25V, 55V, 90V, 120 Macro and 135: each was tested at one setting only.
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
| Can Capture One reproduce Phocus's lens correction across the frame? | Yes: an LCC per lens setting, calibrated over the frame, in a settings file per raw | 39, 40, 41, 42, 43 |
| Why were some photos brighter or darker with the LCC route? | Each LCC was calibrated at a centre spot where it differs from the rest of the frame | 43 |
| Does Phocus handle highlights better? | It keeps colour where one channel clips, and Highlight Recovery rebuilds clipped channels; Capture One can't | 23, 25 |
| Tungsten light? | Separate tungsten profiles, picked automatically below 4400 K | 21, 42 |
| Shade and overcast light? | Separate shade profiles, picked automatically above 6200 K | 33, 44, 45 |
| Tungsten profiles for every lens? | `auto_lens_profile.py --light tungsten` | 46 |
| Does changing white balance in Capture One lose the lens correction's colour? | Not any more: each lens's LCC colour is built into its profiles | 47 |
| Can the profiles carry my camera's own correction? | Yes: `bake_lcc_colour.py --body RAW` | 48 |
| Do settings files work in catalogs? | Yes, imported referenced or copied, with Include existing adjustments (on by default) | 50 |
| Is the 38V darker than Phocus? | By a constant 0.2 L\*, now corrected in its profiles | 32, 49 |
| Bright yellows and saturated colours? | Kept, after fixing how the profiles fade and compress colour | 34, 37, 38 |
| Profiles for lenses not owned? | Built from Phocus renders alone, from any raw of the lens | 26, 32, 35 |
