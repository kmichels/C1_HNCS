on run argv
	set log_ to ""
	set wanted to {"B0000832.3FR","B0000703.3FR","B0000861.3FR","B0000865.3FR","B0000679.3FR","B0000702.3FR","B0000746.3FR","B0000829.3FR","B0000863.3FR","B0000700.3FR","B0000632.3FR","B0000858.3FR","B0000704.3FR","B0000677.3FR","B0000623.3FR","B0000825.3FR","B0000701.3FR","B0000727.3FR","B0000621.3FR","B0000630.3FR"}
	tell application "Capture One"
		set d to current document
		set rn to "E3 probe half"
		if exists recipe rn of d then delete recipe rn of d
		make new recipe at end of recipes of d with properties {name:rn}
		set r to recipe rn of d
		set output format of r to TIFF
		set bits of r to 16
		set color profile of r to "ROMM RGB"
		set output sub folder of r to "E3probe"
		set sharpening of r to disable all
		set ignore crop of r to true
		set scaling method of r to Fixed
		set scaling unit of r to percent
		set primary scaling value of r to 50
		set existing files of r to overwrite
		set log_ to log_ & "recipe scale " & (primary scaling value of r) & " " & ((scaling unit of r) as text) & linefeed
		set n to 0
		repeat with im in (images of d)
			if (name of im) is in wanted then
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
				set log_ to log_ & (name of im) & " clone " & (id of c) & " lens=" & (lens profile of lc) & linefeed
				set qRes to process c recipe rn
				set n to n + 1
			end if
		end repeat
		set log_ to log_ & "queued " & n & linefeed
	end tell
	return log_
end run
