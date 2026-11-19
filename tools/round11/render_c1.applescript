on run argv
	set log_ to ""
	set specs to {{"HNCSnc.3fr", 0}, {"HNCSncE2.3fr", 1}, {"HNCSncE4.3fr", 2}, {"HNCSwb4200.3fr", 0}, {"HNCSwb4500.3fr", 0}, {"HNCSwb5000.3fr", 0}, {"HNCSwb5500.3fr", 0}, {"HNCSwb6000.3fr", 0}, {"HNCSwb6500.3fr", 0}, {"HNCSwb7000.3fr", 0}, {"HNCSwb7500.3fr", 0}, {"HNCSwb8000.3fr", 0}}
	tell application "Capture One"
		set d to current document
		set rn to "HNCS r11 half"
		if exists recipe rn of d then delete recipe rn of d
		make new recipe at end of recipes of d with properties {name:rn}
		set r to recipe rn of d
		set output format of r to TIFF
		set bits of r to 16
		set color profile of r to "ROMM RGB"
		set output sub folder of r to "r11"
		set sharpening of r to disable all
		set ignore crop of r to true
		set scaling method of r to Fixed
		set scaling unit of r to percent
		set primary scaling value of r to 50
		set existing files of r to overwrite
		set log_ to log_ & "recipe profile " & (color profile of r) & linefeed
		repeat with spec in specs
			set im to first image of d whose name is (item 1 of spec)
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
			set color profile of a to "Hasselblad X2D II 100C HNCS E5 35-100"
			set film curve of a to "Linear Response"
			set exposure of a to (item 2 of spec)
			set log_ to log_ & (item 1 of spec) & " prof=" & (color profile of a) & " curve=" & (film curve of a) & " ev=" & (exposure of a) & " K=" & (temperature of a) & " tint=" & (tint of a) & linefeed
			set qRes to process c recipe rn
		end repeat
	end tell
	return log_
end run
