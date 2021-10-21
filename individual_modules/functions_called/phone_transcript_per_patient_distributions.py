#!/usr/bin/env python

import os
import pandas as pd
import glob
import sys
from viz_helper_functions import distribution_plots

# note that this function adds to the study distribution by concatenation and then dropping duplicates
# this will work well except in the case that new features are added - will need to rerun from scratch if so
# (can always change file name if don't want to lose previously compiled distribution in this case)

def transcript_dist(study, OLID):
	# switch to specific patient folder
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio")
	except:
		print("Problem with input arguments, or no processed audio diaries yet for this patient") # should never reach this error if calling via bash module
		return

	# load current QC file
	try:
		cur_QC_path = glob.glob(study + "-" + OLID + "-phoneTranscriptQC-day1to*.csv")[0] # should only ever be one match if called from module
		cur_QC = pd.read_csv(cur_QC_path)
	except:
		print("No transcripts processed yet for this patient, returning") # in case this function is called standalone, notify the user if no processed transcripts exist
		return

	# set up for merging with NLP later before doing the QC-related processing
	cur_QC["filename"] = cur_QC["transcript_name"]
	merger = cur_QC[["filename","ET_hour_int_formatted"]]

	# remove extraneous metadata from the QC spreadsheet - just want enough to identify each row uniquely, don't need easy path back to filenames or dates
	# note again these are hard-coded right now!
	select_features = ["day","patient","ET_hour_int_formatted","num_sentences","num_words","min_words_in_sen","max_words_in_sen","num_inaudible","num_questionable",
					   "num_redacted","num_nonverbal_edits","num_verbal_edits","num_restarts","num_repeats","num_commas","num_dashes",
					   "min_timestamp_space","max_timestamp_space","min_timestamp_space_per_word","max_timestamp_space_per_word"]
	# unit for all the timestamp space features is minutes
	cur_QC = cur_QC[select_features]


	print("Preparing transcript feature distributions for " + OLID)
	# create patient-specific distribution PDF for QC features first
	pdf_out_path = study + "-" + OLID + "-phoneTranscriptQC-distributionPlots.pdf" # output name again hardcoded (per patient/study) for now
	try:
		os.remove(pdf_out_path) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
		# overwrite each time because expect distribution to continually update
	except:
		pass
	# chose bin settings with manual iteration, since automatic generation wasn't showing details we want. this will be another hardcoded thing to revist
	distribution_plots(cur_QC, pdf_out_path, ignore_list=["day","patient","ET_hour_int_formatted"], 
					   bins_list=[12,24,21,25,6,6,11,25,36,36,36,25,25,16,12,10,20], 
					   ranges_list=[(0,60),(0,600),(0,20),(0,50),(0,5),(0,5),(0,10),(0,50),(0,35),(0,35),(0,35),(0,125),(0,75),(-0.05,0.15),(0.0,1.0),(-0.01,0.015),(0.0,0.1)])

	# now do the combining with existing df
	# path to study wide distribution we will add to - currently hard coded!
	# also assuming this folder structure for Distributions is pre-existing
	dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptQC-distribution.csv"
	
	# load study-wide distribution and concatentate
	try:
		cur_dist = pd.read_csv(dist_path)
		cur_dist = pd.concat([cur_dist, cur_QC], ignore_index=True, sort=False) # add sort = False to prevent future warning
		cur_dist.drop_duplicates(subset=["day","patient","ET_hour_int_formatted"], inplace=True)
		cur_dist.reset_index(drop=True, inplace=True)
	except:
		# if this is the first patient ever being processed for this study then can just set to be cur_QC
		cur_dist = cur_QC
		# note that if feature set ever changes, the QC distribution spreadsheet will need to be deleted so it can be recompiled from scratch
		# otherwise new columns will just be filled with NaN in the old spreadsheet, and then the new rows with the correct values will end up the dropped ones

	# now save the new study-wide dist
	cur_dist.to_csv(dist_path, index=False)

	# repeat the same for the NLP features
	cur_NLP_path = study + "_" + OLID + "_phone_transcript_NLPFeaturesSummary.csv"
	try:
		cur_dist_NLP = pd.read_csv(cur_NLP_path)
	except:
		print("No NLP features computed for this patient (" + OLID + ") yet, returning")
		return
	
	# match with convention for QC features
	cur_dist_NLP = cur_dist_NLP.merge(merger, on="filename", how="left") # get submission time for when we start tracking multiple submissions
	cur_dist_NLP["patient"] = [x.split("_")[1] for x in cur_dist_NLP["filename"].tolist()]
	cur_dist_NLP["day"] = [int(x.split("day")[1].split(".")[0]) for x in cur_dist_NLP["filename"].tolist()]
	cur_dist_NLP.drop(columns=["filename"], inplace=True)
	# keeping all features for now, but consider filtering once we get a sense for results

	# create patient-specific distribution PDF
	pdf_out_path_NLP = study + "-" + OLID + "-phoneTranscriptNLP-distributionPlots.pdf" # output name again hardcoded (per patient/study) for now
	try:
		os.remove(pdf_out_path_NLP) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
	except:
		pass
	distribution_plots(cur_dist_NLP, pdf_out_path_NLP, ignore_list=["day","patient","ET_hour_int_formatted"],
					   bins_list=[10,8,15,8,12,12,10,8,20,10,12,12,5,5,6,5,15,10,20,35,10,10,10,10,15,8,15,30,10,10,10,8,15,8,15,15,20,10,20,20,10,2,10,2,10,2], 
					   ranges_list=[(0,50),(0,40),(0,150),(0,40),(2,8),(0,6),(2,12),(0,8),(1.5,3.5),(0.0,1.0),(2.0,5.0),(0.0,3.0),(0.0,1.25),(0.0,0.5),(0.0,1.5),(0.0,1.25),
					   				(1.0,1.75),(0.0,0.5),(1.0,2.0),(0.0,1.75),(0.0,0.5),(0.0,0.5),(0.0,1.0),(0.0,0.5),(1.0,1.75),(0.0,0.4),(1.25,2.0),(0.0,1.5),(0.0,0.5),(0.0,0.25),(0.0,1.0),(0.0,0.4),
					   				(0.25,1.75),(0.0,0.4),(0.5,2.0),(0.0,1.5),(-1.0,1.0),(0.0,1.0),(-1.0,1.0),(-1.0,1.0),(0,9),(0,1),(0,9),(0,1),(0,9),(0,1)])
	# use hard-coded bin limits so that the per patient summaries will all use the same bins (as well as the study-wide)

	# now do the combining with existing df
	# path to study wide distribution we will add to - currently hard coded!
	dist_path_NLP = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptNLP-distribution.csv"
	
	# load study-wide distribution and concatentate
	try:
		full_dist_NLP = pd.read_csv(dist_path_NLP)
		full_dist_NLP = pd.concat([full_dist_NLP, cur_dist_NLP], ignore_index=True)
		full_dist_NLP.drop_duplicates(subset=["day","patient"], inplace=True)
		full_dist_NLP.reset_index(drop=True, inplace=True)
	except:
		# if this is the first patient ever being processed for this study then can just set to be cur_dist_NLP
		# will also hit this exception if concat fails, which should only occur when there is a column mismatch - so if feature set changes
		full_dist_NLP = cur_dist_NLP

	# finally save the new study-wide dist
	full_dist_NLP.to_csv(dist_path_NLP, index=False)

if __name__ == '__main__':
    # Map command line arguments to function arguments.
    transcript_dist(sys.argv[1], sys.argv[2])
