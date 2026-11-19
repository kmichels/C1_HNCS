# Matching Phocus in Capture One: what an X2D II taught me about HNCS

*Draft write-up for blog.tonalphoto.com's author. Numbers are from [research-log.md](research-log.md).*

I shoot a Hasselblad X2D II 100C and I like what Phocus does with its colour, but I edit in Capture
One. Your post on [what a Lightroom camera profile can and cannot reproduce from
Phocus](https://blog.tonalphoto.com/lightroom-camera-profile-phocus-color/) is what made me think the
same could be done for Capture One. Several of your other posts pointed me at the right places:
- [Hasselblad tying HNCS to white balance](https://blog.tonalphoto.com/phocus-mac-imports-hncs-default/)
- [the edge brightening Phocus applies with lens correction
  off](https://blog.tonalphoto.com/phocus-radial-gain-lens-correction-off/)
- [the BaselineExposure tag](https://blog.tonalphoto.com/x2d-ii-baselineexposure-tag-phocus-lightroom/)
- [the lens-correction database in the
  firmware](https://blog.tonalphoto.com/xcd-65e-135v-unannounced-lenses-firmware/)
- [the hot folder as a batch processor](https://blog.tonalphoto.com/phocus-hot-folder-batch-processing/)
- [Phocus correcting for focus distance through its own
  data](https://blog.tonalphoto.com/hasselblad-x2d-ii-focus-distance/)

It can be done. Along the way I found a few things about Phocus I haven't seen written up anywhere. You
also sent me raws from five lenses I don't own, so this is partly a report on what they showed.
Everything is in a public repo: profiles, styles, tools and a long research log
([github.com/swalke16/C1_HNCS](https://github.com/swalke16/C1_HNCS)).

## Quickly

- **Capture One profiles that land about 0.5 ΔE00 from Phocus** at the frame centre, on frames never
  used in fitting. There's one per lens: the XCD 28P, 35-100 and 38V I own, plus the 25V, 55V, 90V,
  120 Macro and 135 from your raws. The 28P and 35-100 also have tungsten versions.
- **Phocus's lens correction, out to the corners.** A Capture One settings file written next to each raw
  before import carries an LCC made for that photo's lens setting, plus exposure and white balance. On 23
  of my photos that no fit had seen, the whole-frame median is about 0.5. The raws aren't touched.
- **Every X2D II carries a factory calibration record** that Phocus uses to make bodies render alike.
  Capture One ignores it; I haven't tested Lightroom. Your camera's record is further from mine than any
  I'd seen, and Phocus treats it exactly as the formula predicts. On your five raws, correcting for it brings Capture
  One from about 1.8 to between 0.16 and 0.51 ΔE00 over the whole frame.
- **HNCS has a recognisable structure.** A colour stage first, then one tone curve applied to each
  channel in Hasselblad's own RGB space, whose definition ships inside Phocus. That may matter for a DCP,
  because Adobe applies its tone curve differently.
- **Your Lightroom post's open items, checked in Capture One.** Whites near clipping track Phocus. A
  push behaves exactly like more light, in both apps. Bright saturated yellows were fading in my own
  profiles, which is fixed now. Colours drift above about 6500 K.
- **Some smaller things.** The Response and Working Space menus are decoded. Vignetting correction is a
  plain multiplier on the raw values. Phocus reads focus distance from one byte of the lens data, and on
  the 90V that byte moves the edge correction by close to half a stop. And Phocus's highlight recovery
  really does rebuild clipped channels.

## Slowly

### How I measured it

X2D II raws store the sensor data uncompressed, and that's what made this possible. A copy of a
real 3FR can be filled with flat patches of exactly known camera RGB, and both apps treat it as the
original photo, same camera, lens and white balance. So instead of fitting to photographs, I fitted to
tens of thousands of patches I designed.

Two tricks made that practical.
- **Capture One.** A "probe" profile whose device RGB is read as ROMM RGB gives back the exact camera
  RGB Capture One hands to a profile.
- **Phocus.** Your hot-folder setup, sidecar first and raw second, works without touching the GUI. Set
  `AutoExport` and `exportDirectory` in its preferences, and point the last entry of `ThumbnailsRecent`
  (macOS bookmarks) at a private folder, because that's the folder Phocus reopens on launch. One gotcha:
  macOS wouldn't let Phocus read a watch folder under `~/Documents`, so it lives under `~/Pictures`.

The fitted result is a 33³ table from camera RGB to Lab, written as a Capture One camera profile, with
Capture One's film curve set to Linear Response so the HNCS tone curve lives inside the profile.

### Every body is calibrated differently

Frames from DPReview's X2D II gallery rendered about 0.5 a\* and 0.5 b\* off from mine on greys, with
the same profile. Swapping metadata between files one piece at a time narrowed it to maker-note entry
0x0019. That's a 512-byte factory record that starts with `GAIN`, carries a date and a calibration-tool
version, and holds two half-floats at bytes 84–87. Mine are 2.600 and 2.260; the DPReview body's are
2.363 and 2.518. Nothing else in the file mattered, and Phocus doesn't check the record's checksum.

Sweeping those two numbers in synthetic files showed what Phocus does with them. The first is a green
gain and the second a blue gain on the camera RGB, roughly kG = (g1/2.60)^0.077 and kB =
(g2/2.26)^0.078. The effect is small: a 15% change in the stored value moves a channel about 1%. It's the
same on every lens and barely changes with white balance. Applying it to the DPReview frames took their
grey offset from −0.52/+0.53 to −0.08/+0.01.

Your camera gave the formula its first real test. Its record is 2.049 and 2.250, well outside the two I
had, and it predicts about 1.8% less green. I swapped your record into one of my synthetic files and
changed nothing else. Phocus moved greys by a\* +1.37 and b\* −0.92, against a predicted +1.41 and
−0.95, and the whole render matched the prediction to 0.07 ΔE00. On your real raws, rendered in Capture
One with profiles made for my body:

| your raw | without the correction | with it |
|---|---|---|
| 25V f/9 | 1.98 | **0.47** |
| 55V f/6.3 | 1.79 | **0.51** |
| 90V f/6.3 | 1.78 | **0.26** |
| 120 Macro f/8 | 1.33 | **0.16** |
| 135 f/6.3 | 1.80 | **0.18** |

(Whole frame, median ΔE00 against Phocus with lens corrections on.) Without the correction, everything is
also 0.4 to 0.6 L\* too bright, because the green gain carries lightness as well as colour.

What this means for anyone building profiles: a profile made on one body carries that body's
calibration, and Capture One never sees the record. If Lightroom doesn't read it either, your DCP fits
your camera and would be off by about this much on mine. In Capture One the correction works as a
white-balance and exposure change, so the settings file for each photo applies its own body's record.

### What HNCS is made of

Phocus has a film-curve setting in its sidecar, and one value of it renders about a stop brighter. I
used that difference to ask where the tone curve sits. A single curve applied to each channel of
**Hasselblad RGB** turns one rendering into the other to 0.31 ΔE00. That's the space in Phocus's bundled
`Hasselblad RGB.icc`: primaries at xy 0.681/0.314, 0.212/0.740 and 0.134/0.046, D50 white, gamma 2.2. The
same curve in ProPhoto only gets to 1.02, and lightness-only or hue-preserving curves are far worse. So
HNCS converts colour first and applies its tone curve last, per channel, in that space.

Knowing the space accounts for most of the three-dimensional behaviour too. With the tone curve in
Hasselblad RGB, a plain matrix plus that curve, fitted only on moderate colours, predicts the most
saturated patches at 2.2 ΔE00. The same model with the curve in ProPhoto is off by 6.9. Most of what
looked like HNCS reshaping saturated colours in three dimensions is just the tone curve working in a
smaller space. What's left for moderate colours is a 3D table: hue, saturation and lightness bins together
bring it to 0.37, close to the full table's 0.27.

What does that mean for a DCP? Adobe's pipeline applies its tone curve in ProPhoto, holding hue on the
largest and smallest channels. That model fit worst of all: 1.83 ΔE00 for moderate colours, against 1.01
for a per-channel curve in Hasselblad RGB. A DCP can still get close, because its LookTable can absorb the
difference, but I suspect that's where the hard cases in a DCP fit come from.

White balance changes the colour stage too. Within daylight it behaves like a colour matrix that shifts
steadily with temperature, much like a dual-illuminant DNG profile: a 3×3 in front of the daylight table
takes the warmest grid from 1.06 to 0.37 ΔE00. At tungsten the shift is large enough that I made separate
profiles.

### Your Lightroom post's open items, in Capture One

I ran the things your post flagged in Lightroom through the same synthetic method.
- **Near-white tones.** Capture One with an HNCS profile doesn't darken them. On a grey ladder through
  clipping it stays within 0.2 L\* of Phocus up to white, so the compression you measured is
  Lightroom's.
- **Pushes.** Exposure works like more light in both apps. A patch pushed +2 EV renders the same as one
  given four times the raw level: within 0.10 ΔE00 in Phocus, 0.02 in Capture One. So a push adds
  no difference of its own. It just moves colours up into the bright range, where the next item
  lives. At +2 EV the median chroma gap is about 1 C\*, the same size as yours. Whether it has the same
  cause in Lightroom I can't say.
- **Bright saturated colours.** Cyan matches at every level, right up to clipping. Bright yellows,
  oranges and yellow-greens didn't, but that was my own doing: the profiles faded colour toward grey above
  L\* 95, and Phocus keeps saturated yellows at L\* 98. With that fixed, bright yellows went from about 19
  ΔE00 to 2.4 on test patches. Real yellow regions in DPReview frames went from 4.9 to 1.6 and 3.2 to 0.5.
  Very saturated colours had a similar limit of my own making. The profiles squeezed chroma above 90, but
  the Lab encoding only limits a\* and b\* to about ±128 each. Compressing near that limit instead took
  colours above C\* 90 from 2.2 to 0.4 ΔE00. Reds and pinks go white sooner in Phocus than in Capture One,
  which happens before any profile.
- **White balance.** Greys hold everywhere from 4200 to 8000 K. Colourful patches match best near
  5500 K and drift either side: about 1.3 ΔE00 at 6500 K and 2.2 at 8000 K. Your single matrix stayed within 0.3 ΔE of
  per-setting fits from 4500 to 8000 K, so some of this may be how Capture One applies white balance
  rather than Phocus. Three of my real shade frames scored 0.58–0.78, against about 0.5 in daylight.
- **BaselineExposure.** Capture One applies the tag the same way Phocus does. DPReview frames tagged +1
  or +2 EV fit as well as untagged ones, with none of Lightroom's extra 0.2 EV.

### Lens corrections, edges and focus distance

Synthetic flat fields show exactly what Phocus does across the frame. Two things are separate.
- **Colour shading.** Less blue toward the edges: about +5 b\* at 60% of the half-diagonal on a mid-grey
  with the 28P. Phocus applies it whether lens corrections are on or off.
- **Vignetting correction**, with corrections on: up to about 2 stops in the 28P's corners.

My measurements first showed that correction shrinking for brighter images. That was Capture One. Its
Linear Response isn't proportional to the raw values in the shadows: it hands a profile 0.17× the raw level
at 1% of white and 0.64× at 10%, settling at 0.75× above 60%. Converted through that curve, Phocus's
correction is a fixed multiplier on the raw values, identical at different exposures.

Phocus also nudges overall brightness by lens setting, on top of its vignetting correction and whether
corrections are on or off. With the 35-100, a mid-grey renders about half an L\* darker at 50–65 mm than
at 35 mm f/11; the 28P is a touch brighter at f/4 than at f/8. Capture One doesn't do this, and it turned
out to be most of the frame-to-frame lightness differences I couldn't explain.

Your focus distance post found that Phocus corrects for focus through its own data, and that it ignores
both SubjectDistance and the private 0x0081–0x0083 fields. That data is byte 6 of the lens descriptor
(0x0018): a focus code that's 0 at infinity and climbs as you focus closer. Four 55V raws at f/2.5 gave
me three different vignetting maps, and lined up by that byte they made sense. Writing one file's code
into another reproduces its map exactly.

How much it matters depends on the lens. On the 55V, close focus darkens the centre by about a third of an
L\*. On my 28P, the corner correction drops by up to 0.07 stop. The 35-100 barely moves. Your 90V moves
most: with corrections on, the correction at 90% of the half-diagonal rises from +0.24 stop at infinity
to +0.65 at the closest code. The centre and the colour shading don't change. With corrections off,
focus makes no difference on the 90V. Its edge lift there is +0.15 stop over the centre, close to the
+0.20 between your +0.09 and +0.29 EV. Past the end of a lens's table, Phocus drops the correction
entirely.

One warning if you test this yourself: SubjectDistance doesn't say where these lenses were focused. My
clover close-up claims infinity and a distant tree claims 0.30 m. Picking near and far frames by it is how
I first convinced myself focus didn't matter.

### Where the lens data lives

You found the lens-correction database in the camera's firmware. Phocus has its own copy. The camera
writes a 34-byte lens identity into two maker-note entries (0x0017 and 0x0018), and Phocus looks
everything else up internally. Copy just those two entries from a 28P file into a 35-100 file and Phocus
gives it the 28P's colour shading, edge lift, vignetting correction and brightness. The EXIF lens name
doesn't matter at all. Break the pair (0x0018 on its own) and Phocus switches lens processing off
entirely, which is how I found its "no lens" baseline. The tables themselves live in Phocus's 119 MB
HBUtil framework, which names every XCD lens.

### Getting the correction into Capture One

Because the correction is a fixed multiplier on each channel, a Capture One LCC can carry it, as long as
there's one LCC per lens setting. A script makes a synthetic flat with the lens state of a given raw, has
Phocus render it through the hot folder, converts the measured gain through Capture One's response curve,
and caches a map per lens, focal length, aperture and focus code (57 so far). Another writes a synthetic
LCC reference from each map and has Capture One make the LCC. Phocus's correction is slightly elliptical
and off-centre, which Capture One's radial Light Falloff can't follow; the LCC follows it to about 0.015
stop.

An LCC also nudges the overall colour, so each one is calibrated on three flats in Capture One and the
nudge is cancelled through exposure and white balance. Capture One can't choose an LCC by lens setting on
its own, so the last step writes its own settings file next to each raw before import: profile, Linear
Response, the lens setting's LCC, exposure and white balance.

| Photos not used in fitting, whole frame, median ΔE00 vs Phocus with corrections on | 28P (7) | 35-100 (16) |
|---|---|---|
| Profile per lens, LCC per lens setting, in a settings file | **0.59** | **0.49** |
| Profile per lens, one colour LCC per lens, Light Falloff 120 | 1.38 | 0.64 |

A lens I don't own can get its own profile from Phocus renders alone, because Capture One turns each
synthetic patch into the same camera RGB whatever the lens. Only the raw's metadata is used. My 38V got its
profile that way, and nine frames from it land 0.35 to 0.53 from Phocus. Your five lenses did too: I gave
each raw my calibration record first, so the profiles fit my body, and then scored your photos with the
correction above. They come out flat to the corners as well (0.33 over the five), though each lens was
tested at one setting only.

### Highlights

People say Phocus is better with highlights, and there's something to it. On a synthetic exposure ladder
through clipping, both apps reach white about a quarter stop before the sensor clips, with the same
tones. Where one channel has clipped, Phocus keeps some colour (median chroma 17 against 0). Its Highlight
Recovery setting is the real difference: it rebuilds a clipped channel from the others and keeps tone up
to about 1.5 stops past clipping while staying neutral. Capture One's Highlight slider only compresses
tones below clipping. A photo with a clipped sky shows the same thing, and no profile can change it,
because it happens before the profile is applied.

## What I still don't know

- **Phocus version.** Everything here is on Phocus 4.2.2, and you're on 4.2.3. I don't know yet whether
  HNCS or the lens processing changed between them.
- **`HighlightDesaturation`.** It changed nothing in my tests.
- **The shade drift.** I don't know how much of it is Capture One's white balance rather than Phocus.

Thank you for the raws -- they settled two questions I'd written off. If you have frames from another
body, or 90V frames at a few focus distances to check the maps against, I'd love to compare notes.
