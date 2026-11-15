on makeRecipe(d, rn, sub)
	tell application "Capture One"
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
		set primary scaling value of r to 50
		set existing files of r to overwrite
	end tell
end makeRecipe

on run argv
	set log_ to ""
	tell application "Capture One"
		set d to current document
		repeat with lf in {0, 60, 80, 100, 120}
			my makeRecipe(d, "E3 lf" & lf, "LF" & lf)
		end repeat
		repeat with nm in {"B0000623.3FR", "B0000679.3FR", "B0000702.3FR"}
			set im to first image of d whose name is (nm as text)
			repeat with lf in {0, 60, 80, 100, 120}
				set c to clone variant (variant 1 of im)
				reset adjustments c
				set a to adjustments of c
				set sharpening amount of a to 0
				set noise reduction luminance of a to 0
				set noise reduction details of a to 0
				set noise reduction color of a to 0
				set noise reduction single pixel of a to 0
				set lc to lens correction of c
				set light falloff of lc to (lf as integer)
				set sharpness falloff of lc to 0
				set distortion of lc to 0
				set hide distorted areas of lc to false
				apply style (layer 1 of c) named "HNCS E3"
				set log_ to log_ & nm & " clone " & (id of c) & " lf=" & (light falloff of lc) & " prof=" & (color profile of a) & " lens=" & (lens profile of lc) & linefeed
				set qRes to process c recipe ("E3 lf" & lf)
			end repeat
		end repeat
	end tell
	return log_
end run
