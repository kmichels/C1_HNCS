on run argv
	set log_ to ""
	tell application "Capture One"
		set d to current document
		set rn to "E1 baseline full"
		if exists recipe rn of d then delete recipe rn of d
		make new recipe at end of recipes of d with properties {name:rn}
		set r to recipe rn of d
		set output format of r to TIFF
		set bits of r to 16
		set color profile of r to "ROMM RGB"
		set output sub folder of r to "E1baseline"
		set sharpening of r to disable all
		set ignore crop of r to true
		set scaling method of r to Fixed
		set scaling unit of r to percent
		set primary scaling value of r to 100
		set existing files of r to overwrite
		repeat with im in (images of d)
			set nm to name of im
			if nm is in {"B0000912.3FR", "B0000929.3FR", "B0000939.3FR"} then
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
				set log_ to log_ & nm & " clone " & (id of c) & " prof=" & (color profile of a) & " curve=" & (film curve of a) & linefeed
				set qRes to process c recipe rn
			end if
		end repeat
	end tell
	return log_
end run
