#!/usr/bin/env python

import os
import pandas as pd
import sys
from viz_helper_functions import transcript_wordcloud

def transcript_wordclouds(study, OLID):
	# switch to specific patient folder - transcript CSVs
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/transcripts/csv")
	except:
		print("Problem with input arguments") # should never reach this error if calling via bash module
		return

	print("Generating transcript wordclouds for " + OLID)
	transcript_paths = os.listdir(".")
	for transcript_path in transcript_paths:
		try:
			cur_trans = pd.read_csv(transcript_path)
		except:
			print("Problem loading " + transcript_path)
			continue
		out_path = "../../wordclouds/" + transcript_path.split(".")[0] + "_wordcloud.png"
		if not os.path.exists(out_path):
			# only create if doesn't already exist for this transcript (as can be a somewhat time intensive process)
			try:
				transcript_wordcloud(cur_trans, out_path)
				# note that sometimes multiple words with a space between will be considered as one word, seemingly inexplicably
				# this happens infrequently enough that it is not worth the time to troubleshoot currently
				# instead simply color the "word" as blue instead of on the normal red/black/green colorscale
				# (see transcript_wordcloud function for more details)
			except:
				print("Function crashed on " + transcript_path)
				continue
	
if __name__ == '__main__':
    # Map command line arguments to function arguments.
    transcript_wordclouds(sys.argv[1], sys.argv[2])
