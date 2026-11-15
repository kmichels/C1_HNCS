-- Render every image in the current Capture One document through the probe profile, at the given scale.
-- usage: osascript render_probe_all.applescript <percent> <output subfolder> [<temperature> <tint>]
-- Pass temperature and tint to force one white balance on every frame (to match a Phocus export
-- whose white balance was set to fixed numbers); otherwise each frame keeps its As Shot.
-- Works on clones; prints their ids so they can be deleted afterwards (delete removes only the clone).
on run argv
	set pct to (item 1 of argv) as integer
	set sub to item 2 of argv
	set fixWB to ((count of argv) ≥ 4)
	if fixWB then
		set wbT to (item 3 of argv) as real
		set wbTint to (item 4 of argv) as real
	end if
	set log_ to ""
	tell application "Capture One"
		set d to current document
		set rn to "HNCS probe " & pct
		if exists recipe rn of d then delete recipe rn of d
		make new recipe at end of recipes of d with properties {name:rn}
		set r to recipe rn of d
		set output format of r to TIFF
		set bits of r to 16
		set color profile of r to "ROMM RGB"
		set output sub folder of r to sub
		set sharpening of r to disable all
		set ignore crop of r to true
		set scaling method of r to Fixed
		set scaling unit of r to percent
		set primary scaling value of r to pct
		set existing files of r to overwrite
		set n to 0
		repeat with im in (images of d)
			set c to clone variant (variant 1 of im)
			reset adjustments c
			set a to adjustments of c
			set sharpening amount of a to 0
			set noise reduction luminance of a to 0
			set noise reduction details of a to 0
			set noise reduction color of a to 0
			set noise reduction single pixel of a to 0
			set lc to lens correction of c
			set light falloff of lc to 0
			set sharpness falloff of lc to 0
			set distortion of lc to 0
			set hide distorted areas of lc to false
			set color profile of a to "Hasselblad X2D II 100C E0 Probe"
			set film curve of a to "Linear Response"
			if fixWB then
				set temperature of a to wbT
				set tint of a to wbTint
			end if
			set log_ to log_ & (name of im) & " clone " & (id of c) & " wb " & ((temperature of a) as text) & "/" & ((tint of a) as text) & linefeed
			set qRes to process c recipe rn
			set n to n + 1
		end repeat
		set log_ to log_ & "queued " & n & linefeed
	end tell
	return log_
end run
