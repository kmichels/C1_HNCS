on run argv
	set log_ to ""
	tell application "Capture One"
		set d to current document
		set rn to "HNCS r20 val"
		if not (exists recipe rn of d) then
			make new recipe at end of recipes of d with properties {name:rn}
			set r to recipe rn of d
			set output format of r to TIFF
			set bits of r to 16
			set color profile of r to "ROMM RGB"
			set output sub folder of r to "r20val"
			set sharpening of r to disable all
			set ignore crop of r to true
			set scaling method of r to Fixed
			set scaling unit of r to percent
			set primary scaling value of r to 50
			set existing files of r to overwrite
		end if
		repeat with arg in argv
			set im to first image of d whose name is (arg as text)
			set v to variant 1 of im
			set a to adjustments of v
			set sharpening amount of a to 0
			set noise reduction luminance of a to 0
			set noise reduction details of a to 0
			set noise reduction color of a to 0
			set noise reduction single pixel of a to 0
			set lc to lens correction of v
			set distortion of lc to 0
			set sharpness falloff of lc to 0
			set hide distorted areas of lc to false
			set log_ to log_ & (arg as text) & " prof=" & (color profile of a) & " curve=" & (film curve of a) & " LF=" & (light falloff of lc) & " EV=" & (exposure of a) & " lcc=" & (applied LCC name of v) & " cast=" & (LCC color cast of v) & " uniform=" & (LCC uniform light of v) & linefeed
			set qRes to process v recipe rn
		end repeat
	end tell
	return log_
end run
