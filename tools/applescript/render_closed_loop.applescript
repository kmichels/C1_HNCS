on makeRecipe(d, rn, sub, pct)
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
		set primary scaling value of r to pct
		set existing files of r to overwrite
	end tell
end makeRecipe

on run argv
	set log_ to ""
	tell application "Capture One"
		set d to current document
		my makeRecipe(d, "E3 closed half", "E3closed", 50)
		my makeRecipe(d, "E3 closed full", "E3closed", 100)
		repeat with spec in {{"B0000623.3FR", "E3 closed half"}, {"B0000679.3FR", "E3 closed half"}, {"B0000703.3FR", "E3 closed half"}, {"B0000829.3FR", "E3 closed half"}, {"B0000863.3FR", "E3 closed half"}, {"B0000912.3FR", "E3 closed full"}, {"B0000929.3FR", "E3 closed full"}, {"B0000939.3FR", "E3 closed full"}}
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
			apply style (layer 1 of c) named "HNCS E3"
			set log_ to log_ & (item 1 of spec) & " clone " & (id of c) & " prof=" & (color profile of a) & " curve=" & (film curve of a) & " -> " & (item 2 of spec) & linefeed
			set qRes to process c recipe (item 2 of spec)
		end repeat
	end tell
	return log_
end run
