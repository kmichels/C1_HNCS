# Matching Phocus in Capture One: what an X2D II taught me about HNCS

*Draft write-up for blog.tonalphoto.com's author. Numbers are from [research-log.md](research-log.md).*

I shoot a Hasselblad X2D II 100C and I like what Phocus does with its colour, but I edit in Capture
One. Your post about building a Lightroom profile that matches Phocus (and your measurements of how
Phocus treats white balance, edge brightening, BaselineExposure and the lens files in the firmware) is
what made me think the same thing could be done for Capture One. It can. Along the way I found a few
things about Phocus that I haven't seen written up anywhere, and they seemed worth sending your way. Everything is in a public repo: profiles, styles, tools, data and a long research log.

## Quickly

- **Capture One profiles that land about 0.5 ΔE00 from Phocus** at the frame centre, on frames never
  used in fitting. One per lens for the XCD 28P and 35-100, plus tungsten versions, and a lens-agnostic
  one.
- **A pre-processing step that gets the whole frame there.** It writes Phocus's lens correction and colour
  shading into a copy of the raw, and Capture One renders the copy with a plain profile. On 23 of my
  photos that no fit had seen, the whole-frame median is 0.65 on the 28P and 0.49 on the 35-100.
- **Every X2D II carries a factory calibration record** that Phocus uses to make bodies render alike.
  Capture One and Lightroom ignore it, so a profile made on one camera is slightly off on another.
- **HNCS has a recognisable structure.** A colour stage first, then one tone curve applied to each
  channel in Hasselblad's own RGB space, whose definition ships inside Phocus. That may matter for a DCP,
  because Adobe applies its tone curve differently.
- **Some smaller things:** the Response and Working Space menus decoded; vignetting correction is a plain
  multiplier on the raw values; focus distance made no difference on my two lenses; and Phocus's
  highlight recovery really does rebuild clipped channels.

## Slowly

### How I measured it

X2D II raws store the sensor data uncompressed, and that's what made this possible. A copy of a
real 3FR can be filled with flat patches of exactly known camera RGB, and both apps treat it as the
original photo, same camera, lens and white balance. So instead of fitting to photographs, I fitted to
tens of thousands of patches I designed.

Two tricks made that practical. In Capture One, a "probe" profile whose device RGB is read as ROMM RGB
gives back the exact camera RGB Capture One hands to a profile. In Phocus, the hot folder you described
renders anything dropped into the folder its browser shows. It can be driven without touching the GUI:
set `AutoExport` and `exportDirectory` in its preferences, and point the last entry of
`ThumbnailsRecent` (macOS bookmarks) at a private folder, because that's the folder Phocus reopens on
launch. A sidecar dropped in first carries the settings. (One gotcha: macOS wouldn't let Phocus read a
watch folder under `~/Documents`, so it lives under `~/Pictures`.)

The fitted result is a 33³ table from camera RGB to Lab, written as a Capture One camera profile, with
Capture One's film curve set to Linear Response so the HNCS tone curve lives inside the profile.

### Every body is calibrated differently

Frames from DPReview's X2D II gallery rendered about 0.5 a\* and 0.5 b\* off from mine on greys, with
the same profile. Swapping metadata between files one piece at a time narrowed it to maker-note entry
0x0019, a 512-byte factory record that starts with `GAIN`, carries a date and a calibration-tool
version, and holds two half-floats at bytes 84–87. Mine are 2.600 and 2.260; the DPReview body's are
2.363 and 2.518. Nothing else in the file mattered, and Phocus doesn't check the record's checksum.

Sweeping those two numbers in synthetic files showed what Phocus does with them: the first is a green
gain and the second a blue gain on the camera RGB, roughly kG = (g1/2.60)^0.077 and kB =
(g2/2.26)^0.078. The effect is small (a 15% change in the stored value moves a channel about 1%), it's
the same on both lenses, and it barely changes with white balance. Applying it to the DPReview frames
took their grey offset from −0.52/+0.53 to −0.08/+0.01.

What this means for anyone building profiles: a profile made on one body carries that body's
calibration, and Capture One and Lightroom never see the record. Unless your record happens to match mine, your
DCP probably fits your camera a little better than mine. The repo has a small script that reads any raw's record and prints the
correction.

### What HNCS is made of

Phocus has a film-curve setting in its sidecar, and one value of it renders about a stop brighter. I
used that difference to ask where the tone curve sits. A single curve applied to each channel of
**Hasselblad RGB** (the space in Phocus's bundled `Hasselblad RGB.icc`: primaries at xy 0.681/0.314,
0.212/0.740 and 0.134/0.046, D50 white, gamma 2.2) turns one rendering into the other to 0.31 ΔE00. The same curve in
ProPhoto only gets to 1.02, and lightness-only or hue-preserving curves are far worse. So HNCS converts
colour first and applies its tone curve last, per channel, in that space.

Knowing the space accounts for most of the three-dimensional behaviour too. With the tone curve in Hasselblad RGB, a plain matrix
plus that curve, fitted only on moderate colours, predicts the most saturated patches at 2.2 ΔE00, where
the same model with the curve in ProPhoto is off by 6.9. Most of what looked like HNCS reshaping
saturated colours in three dimensions is just the tone curve working in a smaller space. What's left for
moderate colours is a 3D table: hue, saturation and lightness bins together bring it to 0.37, close to the
full table's 0.27.

What does that mean for a DCP? Adobe's pipeline applies its tone curve in
ProPhoto, holding hue on the largest and smallest channels, and that model fit worst of all (1.83 ΔE00
for moderate colours, against 1.01 for a per-channel curve in Hasselblad RGB). A DCP can still get close,
because its LookTable can absorb the difference, but I suspect that's where the hard cases in a DCP fit
come from.

White balance changes the colour stage too. Within daylight it behaves like a colour matrix that shifts
steadily with temperature, much like a dual-illuminant DNG profile: a 3×3 in front of the daylight table
takes the warmest grid from 1.06 to 0.37 ΔE00. At tungsten the shift is large enough that I made separate
profiles.

### Phocus's menus, decoded

I couldn't get to Phocus's GUI while doing most of this, so I read the answers out of its code instead.
The Reproduction tool's **Response** menu is the sidecar's `ColorModel`: Standard 0, Reproduction 1,
Reproduction Low Gain 4, Negative 5. Values 2 and 3 are skipped. Rendering each confirmed it: 5 inverts
the picture. Reproduction is a separate rendering built on Standard's colour stage, with lifted shadows
and about 5% more saturation, and it ignores the film-curve setting. The **Working Space** menu is
`ColorWorkingSpace`: 0 Hasselblad RGB (the default), 1 Hasselblad L\* RGB. The code knows four more
values that aren't in the menu, all L\*-encoded with ProPhoto or XYZ primaries. The brighter film-curve
value I used above is a legacy "As Shot" curve. It's not one of the Response options.

### Lens corrections, edges and focus distance

Synthetic flat fields show exactly what Phocus does across the frame. Two things are separate. One is a
colour shading, less blue toward the edges (about +5 b\* at 60% of the half-diagonal on a mid-grey with
the 28P), which Phocus applies whether lens corrections are on or off. The other, with corrections on, is
the vignetting correction: up to about 2 stops in the 28P's corners.

My measurements first showed that correction shrinking for brighter images. That was Capture One. Its Linear Response isn't proportional to the raw values in
the shadows: it hands a profile 0.17× the raw level at 1% of white and 0.64× at 10%, settling at 0.75×
above 60%. Converted through that curve, Phocus's correction is a fixed multiplier on the raw values,
identical at different exposures.

Phocus also nudges overall brightness by lens setting, on top of its vignetting correction and whether
corrections are on or off. With the 35-100, a mid-grey renders about half an L\* darker at 50–65 mm than
at 35 mm f/11; the 28P is a touch brighter at f/4 than at f/8. Capture One doesn't do this, and it turned
out to be most of the frame-to-frame lightness differences I couldn't explain.

On focus distance I can only add a partial answer to yours. On my 28P (0.24 m and 0.75 m against far
focus, f/4 to f/8) and my 35-100 (1.9 m against 5.7 m, 5.7 m against infinity), near and far focus gave
the same correction to within about 0.01 stop out to the corners. One 28P pair first looked different,
until I noticed one file carried BaselineExposure +0.76. You measured a focus effect on the 55V and 90V,
and I have no raws from either, so this may simply be lens-specific.

### Where the lens data lives

You found per-lens shading files in the camera's firmware. Phocus has its own copy. The camera writes a
34-byte lens identity into two maker-note entries (0x0017 and 0x0018), and Phocus looks everything else up
internally. Copy just those two entries from a 28P file into a 35-100 file and Phocus gives it the 28P's
colour shading, edge lift, vignetting correction and brightness. The EXIF lens name doesn't matter at
all. Break the pair (0x0018 on its own) and Phocus switches lens processing off entirely, which is how I
found its "no lens" baseline. The tables themselves live in Phocus's 119 MB HBUtil framework, which names
every XCD lens.

### Writing the correction into the raw

Because the correction is a fixed multiplier and the raw is uncompressed, the cleanest way to reproduce
it in Capture One is to do it before Capture One sees the file. A script makes a synthetic flat with the
lens state of a given raw, has Phocus render it through the hot folder, converts the measured gain
through Capture One's response curve, and caches a map per lens, focal length and aperture (42 so far).
Another writes a corrected copy of each raw. The copy renders with a plain profile, no Light Falloff and
no LCC:

| 23 photos not used in fitting, whole frame, median ΔE00 vs Phocus with corrections on | 28P (7) | 35-100 (16) |
|---|---|---|
| Corrected copy, plain profile | **0.65** | **0.49** |
| Profile per lens + colour LCC + Light Falloff 120 | 1.38 | 0.64 |
| Single profile + Light Falloff 120 | 2.07 | 0.65 |

Adding the lens-setting brightness to the maps took 14 of those frames from a mean of 0.55 to 0.47, with
their lightness offsets falling from 0.33 to 0.12 L\*. The batch tool now also writes a Capture One
settings file next to each copy, so it opens with the right profile and Light Falloff 0, and a lens I
don't own can get its own profile from Phocus renders alone, because Capture One turns each synthetic
patch into the same camera RGB whatever the lens.

The error is flat from centre to corner. The cost is a full-size copy of every raw, and some highlight
headroom in brightened corners. I tried buying that back by darkening the raw and raising
BaselineExposure. Capture One renders it identically, but it can no longer tell which photosites clipped
in camera, so a recovered sky gets a hard band. I dropped it.

### Highlights

People say Phocus is better with highlights, and there's something to it. On a synthetic exposure ladder
through clipping, both apps reach white about a quarter stop before the sensor clips, with the same
tones. Where one channel has clipped, Phocus keeps some colour (median chroma 17 against 0). Its Highlight
Recovery setting is the real difference: it rebuilds a clipped channel from the others and keeps tone up
to about 1.5 stops past clipping while staying neutral. Capture One's Highlight slider only compresses
tones below clipping. A photo with a clipped sky shows the same thing, and no profile can change it,
because it happens before the profile is applied.

## What I still don't know

The focus question on the 55V and 90V is the obvious one. The only public raws I've found from either
are from the original X2D, so X2D II files from those lenses, ideally at close focus, would let me test it
the same way. I haven't found what `HighlightDesaturation` does, since it changed
nothing in my tests. And I have exactly two GAIN records, mine and DPReview's -- if yours shows up as
another pair of numbers in the same range, the formula gets its first independent test.

If any of this is useful for your DCP, or you have 55V or 90V raws at close focus, I'd love to compare
notes.
