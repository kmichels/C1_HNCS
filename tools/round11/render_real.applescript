on run argv
	set log_ to ""
	tell application "Capture One"
		set d to current document
		set rn to "HNCS r11 real"
		if exists recipe rn of d then delete recipe rn of d
		make new recipe at end of recipes of d with properties {name:rn}
		set r to recipe rn of d
		set output format of r to TIFF
		set bits of r to 16
		set color profile of r to "ROMM RGB"
		set output sub folder of r to "r11real"
		set sharpening of r to disable all
		set ignore crop of r to true
		set scaling method of r to Fixed
		set scaling unit of r to percent
		set primary scaling value of r to 50
		set existing files of r to overwrite
		repeat with nm in {"B0000686.3FR", "B0000688.3FR", "B0000840.3FR"}
			set im to first image of d whose name is (nm as text)
			set v to variant 1 of im
			set a to adjustments of v
			set lc to lens correction of v
			set log_ to log_ & nm & " as opened: prof=" & (color profile of a) & " curve=" & (film curve of a) & " LF=" & (light falloff of lc) & " dist=" & (distortion of lc) & " K=" & (temperature of a) & linefeed
			set c to clone variant v
			set a to adjustments of c
			set lc to lens correction of c
			set color profile of a to "Hasselblad X2D II 100C HNCS E5 35-100"
			set film curve of a to "Linear Response"
			set light falloff of lc to 0
			set distortion of lc to 0
			set sharpness falloff of lc to 0
			set hide distorted areas of lc to false
			set sharpening amount of a to 0
			set noise reduction luminance of a to 0
			set noise reduction color of a to 0
			set qRes to process c recipe rn
		end repeat
	end tell
	return log_
end run
