> **Historical note.** This is the plan written before any fitting was done. Most of it held; where it did not, [methodology.md](methodology.md) describes what was actually built and measured. Experiment names E0–E3 in the other docs follow the build order in section 9.

# HNCS in Capture One — design

Goal: make Capture One 16.9 render X2D II 100C raws the way Phocus 4.2 renders them (Standard response).

Claim tags: **[V]** verified here (file/source given), **[S]** stated by a cited source, not re-verified, **[I]** inferred, **[?]** open — with the test that settles it.

---

## 1. Decision

**Build a custom ICC input profile (33³ Lab LUT) fitted to Phocus renders, with the Phocus tone curve baked in, selected by a `.costyle` that also sets Film Curve = Linear Response.** One profile for daylight-range WB first; add a tungsten profile only if measurement demands it. Per-lens add-on presets handle light falloff. A style-only version is a by-product (fallback and portable variant), not the main route.

Why:

| Route | What it can reach | Verdict |
|---|---|---|
| (a) Style only on ProStandard: Exposure + luma curve + Color Editor | Fixes the half-stop midtone gap and the neutral tone curve exactly; pulls blue/violet chroma down and rotates cyan by hue sector. Cannot express hue/saturation changes that vary with lightness and saturation together, has a limited number of hue zones, and its curve acts after C1's own film curve and profile. Expected to cut the blogger's "typical 4.0 ΔE" substantially but not to ~1; **no measurement exists** — the number is unknown until fitted. | Fallback / quick win |
| (b) One fitted ICC + style | A 33³ RGB→Lab LUT is strictly more expressive than the blogger's DCP (matrix + HSV table + 1 curve), which reached 0.94 median ΔE00 [S]. If C1 hands the ICC a single-valued function of the raw, the same or better is reachable [I]. | **Chosen** |
| (c) Per-illuminant ICCs | Needed only if Phocus's post-WB transform changes with WB. Blogger: one fixed transform tracks within ~0.3 ΔE from 4500–8000 K [S]; below 4500 K untested. C1 cannot switch profile by WB automatically, so each extra profile is a manual style choice. | Conditional on §6 test |
| (d) 3D LUT import | C1 has no LUT import; LUT→ICC is route (b) anyway. | — |

What a profile (any route) cannot carry: anything that depends on pixel position (Phocus's lens edge brightening), on neighbours (clipped-channel reconstruction, NR, sharpening, demosaic), or on a per-image switch (Phocus HDR mode). Those are handled in §7.

---

## 2. Facts established locally

- **[V]** C1's X2D II profiles (`…/ImageProcessing.framework/…/Profiles/Input/HasselbladX2DII100C-{ProStandard,Generic}.icm`): ICC v2.4, class `scnr`, RGB→Lab, tags `desc`, `cprt`, `wtpt` (D50), `A2B0` (`mft2`, 33³, 1025-entry input curves, 2-entry identity output curves, identity matrix). The `desc` string equals the file stem.
- **[V]** Lab is stored in the legacy 16-bit encoding (L = v/65280·100, a,b = v/256 − 128): decoding this way gives exactly L=100 at white and a=b=0.00 along the whole neutral diagonal.
- **[V]** **The neutral axis of ProStandard is a pure gamma-1.8 decode**: input curve ∘ grid gives Y = x^1.800–1.802 from x = 0.05 to 0.9. So the ICC receives **white-balanced camera RGB, gamma-1/1.8 encoded**, and the bundled profile contains **no tone curve** — tone lives entirely in the `.fcrv`. (Parsed in this session.)
- **[V]** ProStandard and Generic share the same input curves and neutral axis; they differ only in chroma (e.g. red corner a* 102 vs 107) and in ProStandard's private `P100` tag (20 bytes). Meaning of `P100` is **[?]** — plausibly switches the hue-preserving "ProStandard" curve handling [I]. Test in E0.
- **[V]** LUT corners clip at a/b = ±128 (green, blue corners), so C1 tolerates clipped Lab at extreme nodes.
- **[V]** Film curves for the camera exist as `HasselbladX2DII100C-{Auto,Film Standard,Film High Contrast,Film Extra Shadow,Linear Response}.fcrv` (binary, obfuscated; not worth reversing).
- **[V]** `.costyle` keys seen in installed styles: `ICCProfile` (value = profile file name with extension, e.g. `Phase One Effects - No color correction.icm`), `FilmCurve` (camera-specific file name, e.g. `PhaseOneP45+-Film High Contrast.fcrv`), `Exposure`, `GradationCurveY`, `ColorCorrections`, `LensLightFallOff`, `WhiteBalanceTemperature/Tint`. Newest installed styles are `Engine="1300"`; the engine number 16.9 writes is **[?]** — save one style from the 16.9 UI and copy its header.
- **[V]** C1 AppleScript (`CaptureOne.sdef`): `adjustment settings` exposes `color profile`, `film curve`, `white balance preset`, `temperature`, `tint`, `exposure`, sharpening/NR/clarity/levels/curves/HDR sliders; `lens correction settings` exposes `light falloff`, `distortion`, `sharpness falloff`, `chromatic aberration`, `diffraction correction`; `recipe` exposes `output format`, `bits`, `color profile`, scaling, `sharpening` (`disable all`), `ignore crop`; `process <variant> recipe "<name>"`; `apply style <layer> named "<x>"`. The whole C1 side is scriptable.
- **[V]** Phocus has no scripting dictionary (no `.sdef`, no `NSAppleScriptEnabled`). Its binary has a per-image `hdrMode` / "Set HDR Mode" / `isCapturedInHdrMode` and a Reproduction tool with a Response menu. Factory output presets include `TIFF-16` and colour-space choices including `Source`, `Adobe RGB (1998)`, `sRGB`, `Hasselblad Rec.709`; the string `ProPhoto` is present in the binary.
- **[V]** `Hasselblad RGB.icc`, `HasselbladLStarRGB.icc`, `Hasselblad Rec2100PQ.icc` are installed in `~/Library/ColorSync/Profiles`.
- **[V]** This Mac's `python3` (3.12.6) has no numpy/scipy/tifffile; Homebrew exists. A venv is needed.
- **[S]** DCamProf docs (Torger): C1 profiling export = ICC "Phase One Effects: No Color Correction" + curve "Linear Response" + 16-bit TIFF + output "Embed camera profile"; C1 applies a curve **before** the ICC; C1 curves work in gamma 1.8; with older bundled profiles part of the curve sat in the LUT (not the case for the X2D II profile, per the parse above).
- **[S]** Custom camera profiles on macOS go in `~/Library/ColorSync/Profiles`, C1 must be restarted; a profile not matching the camera naming appears under "Other" (C1 support article + forum; the article returned 403 today, so wording unconfirmed). That `HasselbladX2DII100C-<Name>.icm` lists under the camera is **[I]** from the bundled naming — test in E0. Settle it definitively by using Color Editor → "Save as ICC profile" once and looking at where C1 writes the file and what it names it.

---

## 3. The model of C1's pipeline, and what must be tested

Assumed order **[I]** (consistent with [S] DCamProf and the [V] gamma-1.8 neutral axis):

`raw → demosaic → WB gains → exposure / highlight recovery → film curve (.fcrv, RGB, in γ1.8) → ICC A2B0 → Lab → working space → Levels/Curves/Color Editor/… → output profile`

Consequences:
- The ICC sees WB'd, exposed, film-curved device RGB. With Linear Response and everything else neutral, that is (nearly) linear camera RGB in γ1.8.
- Anything the profile learns is valid only for the film curve it was fitted under. The style must pin the film curve.
- C1's Exposure and WB act before the profile, as Phocus's exposure and WB act before HNCS/tone [I]; so pushed frames and WB changes should track Phocus better than the blogger's Lightroom profile did — test, don't assume.

Tests that settle the assumptions (all in E0, §9):
1. **What does the ICC actually receive?** Write a probe profile whose LUT is exactly "device RGB is ProPhoto RGB (γ1.8, D50)": node (r,g,b) → Lab(ProPhoto(r,g,b)). Process with recipe profile ProPhoto, 16-bit. The TIFF then *is* the ICC input (except where ProPhoto primaries exceed the ±128 Lab range — pure green/blue corners only). Compare with the DCamProf-style export (No color correction + Embed camera profile). If they agree, either can be the source; the probe is preferred because its math is ours.
2. **Is Linear Response linear?** Shutter-speed bracket of a grey card: device values should scale by 2^(1/1.8) per stop. Not required for the fit (the LUT is empirical), but it tells us where highlight headroom sits.
3. **Does `P100` matter, and does C1 treat a user profile like a bundled one?** Byte-copy ProStandard under a new name, with and without `P100`; render the same frame with Film Standard through original, copy, and copy-without-P100; diff the TIFFs.
4. **Is anything colour-changing left after the ICC with all tools neutral?** Closed loop: render through the fitted profile, compare to the fit's own prediction. Should agree to < 0.3 ΔE00; if not, a second pass fits the residual on the closed-loop render.

---

## 4. Fitting pipeline

### 4.1 Source render (Capture One) — scripted
Per frame, on a **clone variant**:
- `color profile` = probe profile; `film curve` = `HasselbladX2DII100C-Linear Response` (exact text form C1 expects: read it back from a variant set in the UI **[?]**).
- WB: per §6 (As Shot, or picker on the grey patch for chart frames).
- Zero/neutral: exposure, contrast, brightness, saturation, highlight/shadow/white/black recovery, levels, all curves, clarity, dehaze, vignetting, grain, colour balance, colour editor; sharpening amount 0; NR luminance/colour/details/single pixel 0; no LCC.
- Lens: `light falloff` 0 (defaults to 100 and stays on with corrections off [S]), `sharpness falloff` 0, CA off, diffraction off, distortion 0. Whether distortion can be fully disabled for XCD lenses is **[?]** — check output dimensions/alignment against Phocus.
- Recipe (always named): TIFF, 16 bit, uncompressed, `color profile` ProPhoto RGB, scale 100 %, `sharpening` = `disable all`, `ignore crop` true.

A second scripted pass with the *fitted* profile (same settings) produces the validation renders. A third with ProStandard + Auto gives the "before" baseline.

### 4.2 Target render (Phocus) — user in the UI
- Import with a known state: apply the **Standard** preset explicitly to every frame (the Mac default import can skip the preset when "Use embedded if available" is ticked [S]).
- **HDR mode off** (SDR render). The switch exists [V]; whether X2D II frames default to HDR in Phocus desktop is **[?]** — check the Reproduction tool on one frame. An HDR target would be a different rendering.
- Response: Standard. Exposure, recovery, shadow fill, clarity, curves, saturation: neutral. Sharpening and noise filter as low as they go.
- Lens corrections (distortion, CA, vignetting) off for the *training* exports. Phocus still brightens edges per lens [S] — handled by sampling the centre only.
- WB: same rule as the C1 side (§6).
- Export: TIFF-16, full size, uncompressed. Colour space: the widest Phocus offers. **[?]** which is unclipped — export one saturated frame as `Source`, Hasselblad RGB, Hasselblad L* RGB and ProPhoto (if offered), convert each to Lab, and pick the widest whose in-gamut colours agree with the others. All are matrix/TRC profiles, so conversion to Lab D50 is a few lines of numpy reading `rXYZ/gXYZ/bXYZ/TRC` from the embedded profile — no CMM needed.

### 4.3 Pairing and sampling
- Decode both TIFFs; C1 → device RGB (γ1.8), Phocus → Lab D50.
- Align: sizes may differ by a few pixels (Phocus uncropped = 11656×8742 [S]). Estimate integer translation by phase correlation on 1/8-scale luminance; verify no scale/rotation by checking the residual shift in the four quadrants; fall back to per-block shift estimates if distortion handling differs.
- Tile into 64×64 px blocks; block mean of device RGB (C1, averaged in linear light) and of XYZ (Phocus), then to Lab.
- Reject a block if: any channel in either render > ~0.98 or the C1 block contains pixels at the device ceiling (clipped raw); mean L* < 2; within-block std or gradient above a threshold (texture, edges, misalignment-sensitive); outside the central ~35 % radius (vignetting differences); known dust/specular.
- De-duplicate: bin device RGB at 64³, cap samples per bin per frame, weight bins by √count so skies and greys do not swamp the fit.
- **Diagnostic that can kill the approach:** the spread of Phocus Lab inside one tight device-RGB bin *across different frames* is the floor any single profile can reach. If that intrinsic scatter is ≳ 2 ΔE00, Phocus's render is not a function of WB'd raw RGB (spatial, adaptive, or WB-dependent) and route (b) tops out there.

### 4.4 Model
Custom Python (numpy + scipy.sparse + tifffile), two stages:

1. **Parametric base** (defines behaviour everywhere, including where there is no data): device RGB → linear (^1.8) → 3×3 matrix → per-channel monotone tone curve (PCHIP, ~16 knots) → XYZ → Lab. Fit by nonlinear least squares on Lab, then refine on ΔE00. Also jointly fit per-frame nuisance parameters (§6): two WB gains and one exposure scalar, anchored at 1 on chart frames, ridge-regularised toward 1 elsewhere.
2. **Residual LUT**: Lab residual on the 33³ grid in *shaped* device space (reuse ProStandard's 1025-entry input curve as the shaper — it concentrates nodes in the shadows [V]). Each sample is a trilinear combination of 8 nodes → sparse least squares (`lsqr`) with (i) second-difference smoothness on all three axes, (ii) ridge toward zero so unsampled nodes fall back to the base, (iii) a strong penalty tying neutral-diagonal nodes to a*=b*=const (whatever Phocus's neutral is — expected 0) so greys cannot pick up a cast. Regularisation weights chosen by cross-validation on held-out *frames*.

Final LUT node = base(node) + residual(node), clipped to L 0–100, a/b −128…+127.99.

QA before writing: L* monotone along the neutral axis and along each primary ramp; Jacobian determinant positive at every node (no folds); white node = (100,0,0), black = (0,0,0); max node-to-node ΔE below a bound; visual check on synthetic hue/saturation ramps and a Granger rainbow rendered through the LUT.

Alternatives considered: ArgyllCMS `colprof -al` from a `.ti3` of the same pairs is a legitimate cross-check (its rspl is the same idea), but gives less control over extrapolation and table layout. DCamProf is the wrong tool: it builds from target spectra toward its own rendering model, not toward arbitrary Lab pairs with a baked look.

### 4.5 Tone curve: baked, with Linear Response
- Chosen: Film Curve = Linear Response, Phocus tone curve inside the LUT. Removes the unknown interaction between C1's film curve, `P100`, and the profile; keeps one artefact; exposure changes then pass through the Phocus-shaped curve the way they do in Phocus [I].
- Cost: the LUT carries a strong tone curve at 33 nodes. Mitigated by the shadow-weighted shaper; check interpolation error on a dense neutral ramp (target < 0.2 L*). If highlight roll-off or banding is worse than acceptable, refit against **Film Standard** as source — identical pipeline, only the scripted C1 source pass changes, the Phocus targets are reused. Build both and let held-out ΔE and a highlight-ramp check decide.

### 4.6 Writing the ICC
- Clone the ProStandard container: same header fields (v2.4, `scnr`, RGB, Lab, D50 illuminant), tags `desc`/`cprt`/`wtpt`/`A2B0`, `mft2` 33³ with 1025-entry input and 2-entry output tables, legacy Lab encoding. Own copyright string. `P100` kept or dropped per the E0 result.
- `desc` = file stem = `HasselbladX2DII100C-HNCS Standard`; file `HasselbladX2DII100C-HNCS Standard.icm`. Install: `~/Library/ColorSync/Profiles` (user copies it; C1 restart) [S]/[?].
- Round-trip test: re-parse the written file with the same parser used on ProStandard and compare node values.

### 4.7 The style
`HNCS Standard.costyle` — `FilmCurve` = `HasselbladX2DII100C-Linear Response.fcrv`, `ICCProfile` = `HasselbladX2DII100C-HNCS Standard.icm`, plus `Name`, `UUID`, `StyleSource`. Nothing else, so it stacks with the user's own edits. Header copied from a style saved by 16.9. Optional: make it the camera default in Base Characteristics so imports start there.

---

## 5. Training and validation data

Because the target is "what Phocus does", not colorimetry, **every smooth pixel of every scene is a valid training pair**; a chart is useful for WB anchoring and repeatable reporting, not essential.

Shoot (ISO 50–400, any lens, any aperture — only the frame centre is sampled):
- ColorChecker (Classic or SG) in daylight, shade, overcast; fill the centre third of the frame; ±1, ±2 EV brackets.
- Skin (several tones), foliage and grass, blue sky from zenith to horizon, sunset, water, earth/stone/wood.
- High-saturation: flowers (red, magenta, violet, yellow, orange), fabrics, plastics, painted metal, fruit.
- **Gamut filler:** slightly defocused frames of a wide-gamut display showing hue × saturation × brightness sweeps, with a fixed manual WB, bracketed ±3 EV. Fills the device-RGB cube far beyond natural scenes. Valid only if the render is a function of WB'd RGB — the §4.3 scatter diagnostic checks that; keep these frames in a separate group so they can be excluded if they disagree with natural frames.
- Exposure brackets (−3…+2 EV) of a few ordinary scenes to cover the tone axis up to just below clip.
- Tungsten/warm LED (2700–3200 K) and deep shade (>8000 K): chart + two scenes each. Used for §6, not for the first fit.

Counts: ~40–60 training frames, 20–30 held-out frames **from different sessions/subjects** (hold out by frame, never by pixel). High-ISO check set: 800 / 3200 / 12800, a chart and a scene each. Pushed set: 6–10 frames at +2 EV in both apps.

Reporting (same shape as the blogger's so numbers are comparable): per held-out frame, ΔE00 over accepted centre blocks; then median and 10th–90th percentile across frames; plus mean ΔL*, ΔC*, Δh by hue sector and by L* band, P95 and worst blocks, and the same table for the baseline (ProStandard + Auto, and ProStandard + Auto + best single exposure offset). Targets: held-out median ≤ 1.0, P90 ≤ 2.0 (blogger's DCP: 0.94, 0.55–1.19 [S]).

Overfitting guards: frame-level CV for regularisation; residual LUT shrinks to the parametric base where data is sparse; report train vs held-out gap; coverage map of the device cube so sparse regions are known rather than discovered.

---

## 6. White balance

- HNCS is "strongly linked to white balance parameters" [S]. In C1 the profile is fixed and applied after WB. If Phocus's post-WB transform is constant, one profile is exact at every WB; if Phocus selects/interpolates transforms by WB, one profile matches only the WB range it was fitted on.
- Evidence: one fixed (matrix) transform tracked within ~0.3 ΔE across 4500–8000 K on one chart frame [S]. So **one profile for 4500–8000 K is the working assumption**; < 4500 K and > 8000 K are open.
- **Kelvin/tint numbers are not comparable between apps** [I — each converter has its own camera-neutral↔CCT model]. Do not copy numbers across. Make WB comparable by one of:
  1. *Picker on the same grey patch* in both apps (chart frames) — the anchor.
  2. *As Shot in both* — plausible that both read the same camera multipliers, but **[?]**: check that a grey patch lands at the same a*, b* in both renders.
  3. *Fitted nuisance gains*: the per-frame WB gains of §4.4. If they come out within ~±0.5 % of 1 for As Shot frames, As Shot is equivalent and the nuisance terms are dropped.
- Tests:
  - **Sweep** (reproduces the blogger's, extended down): one daylight chart frame, Phocus Kelvin at 2800, 3200, 3800, 4500, 5500, 6500, 8000, 10000. For each, C1 source render with WB gains matched via the grey patches (nuisance fit on neutrals only), then score the colour patches through the daylight profile. A rise in ΔE with distance from daylight means Phocus's transform is WB-dependent.
  - **Real illuminants**: tungsten and shade chart frames, picker WB in both, scored through the daylight profile.
- If either shows a trend (say median > 1.5): fit a second profile on warm-light frames → `HNCS Standard Tungsten` (+ style), and if needed a shade one. Selection is manual; a small script could set the profile from each variant's `temperature`, but that is a later convenience.

---

## 7. Known gaps and mitigations

| Gap | Why a profile can't fix it | Mitigation in C1 |
|---|---|---|
| Phocus brightens toward edges per lens even with correction off (+0.67 EV at XCD 55V edge [S]); C1 Light Falloff 100 removes nearly all vignetting, Phocus about a third [S] | Position-dependent | Per-lens add-on presets setting `LensLightFallOff` only. Calibrate per lens from flat-field frames (evenly lit wall or diffuser, wide open / f/5.6 / f/11): compute radial luminance ratio Phocus÷C1 and choose the slider value that flattens it. Whether one value holds across apertures is **[?]**; if not, an LCC per lens/aperture is the heavier option. Keep the colour style lens-agnostic. |
| Near-white / highlight roll-off | Fit-able up to clip; beyond, reconstruction is neighbourhood-dependent | Baked curve learns Phocus's shoulder from bracketed frames; force the LUT to converge monotonically to white. Clipped-channel areas will differ and are excluded from scoring; report them separately. |
| Near-clip saturated colours (10–12 ΔE in the blogger's LR profile [S]) | Sparse data + gamut limits | Gamut-filler and bracketed saturated frames; report by saturation band. Expect to be better than a DCP, not perfect. |
| High ISO | Colour map should not depend on ISO [I]; shadow clipping and NR do | Validate at 800/3200/12800. C1's midtone gap is roughly constant across ISO (5.4–6.8 L* [S]); if a per-ISO offset remains, ship ISO-range exposure presets. Leave C1's NR to taste — it is not part of "colour". |
| Pushed exposures | Depends on where each app's exposure sits relative to the curve | Test set at +2 EV; if C1 diverges, document rather than fix. |
| C1's tools after the profile (Contrast, HDR, Clarity, Color Editor) | They are C1's, not Phocus's | Out of scope: the match is for the neutral render. |
| C1 or Phocus updates | Engine or bundled-curve changes invalidate the fit | Keep the scripts and the held-out set; re-score after each update, refit only if it moves. |

---

## 8. Automation split

- **Scripted (AppleScript via `osascript`, no `activate`):** clone variants, set profile/film curve/WB/zeroed adjustments/lens settings, create the named recipe, process, wait for the queue. All properties exist in the sdef [V]. Quirks carried from earlier work: always pass the recipe name; edit clone variants, never the originals.
- **Python:** ICC writer/parser, TIFF→RGB/Lab, alignment, sampling, fitting, QA, report, style file generation.
- **User in the UI:** all Phocus work (apply Standard, HDR off, lens corrections off, WB, export with a TIFF-16 preset — the Phocus hot folder may batch this [S, untested]); copying the ICC into `~/Library/ColorSync/Profiles` and the style into C1's Styles folder; restarting C1; one-off "Save as ICC profile" and "save a style" to capture C1's own naming and style header; WB picker clicks on chart frames.
- Disk: a 100 MP 16-bit TIFF is ~600 MB. After E1 confirms that block statistics are unchanged at reduced size, export both apps at 25–50 % for the bulk set.

---

## 9. Build order

**E0 — plumbing (an hour of user time, no shooting).** Venv outside the repo. Write three profiles: probe (ProPhoto identity), ProStandard byte-copy, ProStandard copy without `P100`. User installs, restarts C1. Check: listed under X2D II? Script renders one existing frame (`B0000912.3FR`) through each. Answers §3 tests 1–3 and confirms C1 accepts a Python-written `mft2` profile. *Kill:* C1 refuses or ignores user profiles for this camera → fall back to route (a).

**E1 — cheap proof on the 15 existing raws.** User exports them from Phocus (Standard, HDR off, corrections off, As Shot, TIFF-16). Script renders C1 sources. Fit base + LUT on 11, hold out 4. Look at: intrinsic scatter floor (§4.3), held-out ΔE00 vs the ProStandard baseline, closed-loop agreement (§3 test 4). *Pass:* floor < ~1, held-out median clearly under the baseline and trending to ≤ 1.5 on such thin data, closed loop < 0.3. *Kill/redirect:* large floor → investigate WB/HDR/spatial dependence before anything else.

**E2 — WB.** Chart frame Kelvin sweep + As Shot equivalence check (§6). Decides one profile vs several, and how the training set must set WB.

**E3 — shoot the training and held-out sets (§5); fit v1;** build Linear-Response and Film-Standard variants; pick one; write the ICC and style; full report.

**E4 — gaps:** per-lens falloff presets, high-ISO and pushed checks, tungsten/shade profile if E2 says so.

**E5 — optional style-only variant:** fit Exposure + luma curve + Color Editor zones to the same pairs, on top of ProStandard, for machines without the custom ICC; report its ΔE honestly next to the profile's.

---

## Sources
- Local: C1 profiles, film curves, `CaptureOne.sdef`, installed `.costyle` files; Phocus 4.2.2 binary strings and factory output presets; `~/Library/ColorSync/Profiles`.
- DCamProf documentation (Capture One workflow): https://torger.se/anders/dcamprof.html
- Capture One support, "Installing custom camera profiles": https://support.captureone.com/hc/en-us/articles/360002409057 (403 on fetch; cited via search summary)
- Tonal Photo: https://blog.tonalphoto.com/what-hncs-actually-is/ , https://blog.tonalphoto.com/phocus-optional-hasselblad-workflow/ , https://blog.tonalphoto.com/lightroom-camera-profile-phocus-color/ , https://blog.tonalphoto.com/phocus-capture-one-lightroom-hasselblad-measured/ (last two taken from the team lead's summary, not re-read)
