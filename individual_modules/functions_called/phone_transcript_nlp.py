#!/usr/bin/env python

# Script to extract NLP features from each available. previously unprocessed transcript csv - includes coherence/word uncommonness, sentiment, speech rate, and keyword matcher

import os
import pandas as pd 
import sys
import glob
# import helper functions to calculate the features within each transcript and save a summary
from language_feature_functions import count_number_syllables, calculate_speaking_rate, calculate_wordtovec_transcript, calculate_sentiment, count_keywords, summarize_transcript_stats

chosen_keywords=["stress", "depress", "anx"] # hardcoded across all studies for now, really just an example for illustration - will count anything fully containing these letters so can get at variations via roots

def diary_transcript_nlp(study, OLID):
	print("Running Transcript Feature Extraction for " + OLID) # if calling from bash module, this will only print for patients that have phone transcript CSVs that have not been processed yet

	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/transcripts/csv")
	except: # this should only be possible to reach if the function was called directly, and not via the bash module.
		print("No transcripts to process for input study/OLID - if this is unexpected, please ensure transcripts have been pulled and CSV formatting script has been run")
		return

	# load audio QC for this pt to get the diary file lengths - necessary for getting speech rate of final sentence
	audio_QC_path = glob.glob("../../" + study + "-" + OLID + "-phoneAudioQC-day1to*.csv")[0] # should only ever be one match if called from module
	audio_QC = pd.read_csv(audio_QC_path)
	# if this fails to load okay for function to crash on the input patient, error message should be clear and output can't be completed
	# very unlikely this module would ever be called without having some basic QC results for a given diary

	# compile list for patient summary DF
	trans_dfs = []

	cur_files = os.listdir(".")
	cur_files.sort() # go in order, although can also always sort CSV later.
	for filename in cur_files:
		if not filename.endswith(".csv"): # skip any non-csv files (and folders) in case they exist
			continue

		if os.path.isfile("../csv_with_features/" + filename): # also skip if it has already been processed
			continue

		# load in CSV and clear any rows where there is a missing value (should always be a subject, timestamp, and text; code is written so metadata will always be filled so it should only filter out problems on part of transcript)
		try:
			cur_trans = pd.read_csv(filename)
			cur_trans = cur_trans[["subject", "timefromstart", "text"]]
			cur_trans.dropna(inplace=True)
		except: # ensure it fails gracefully if there is an issue with a particular transcript
			print("Problem loading this file (" + filename + "), skipping")
			continue

		# separate out sentences and ensure transcript is not empty
		cur_sentences = cur_trans["text"].tolist()
		if len(cur_sentences) == 0:
			print("Current transcript is empty, skipping this file (" + filename + ")")
			continue

		# get audio length to use in the speech rate function
		try:
			cur_file_QC = audio_QC[audio_QC["transcript_name"]==filename]
			cur_length_seconds = float(cur_file_QC["length(minutes)"].tolist()[0]) * 60.0
		except:
			print("No audio QC record for file (" + filename + "), skipping")
			continue

		# compute features for this transcript in place
		try:
			count_number_syllables(cur_trans)
			calculate_speaking_rate(cur_trans, audio_length=cur_length_seconds)
			calculate_wordtovec_transcript(cur_trans)
			calculate_sentiment(cur_trans)
			count_keywords(cur_trans, chosen_keywords, substrings=True)
		except:
			print("Problem with current transcript (" + filename + "), one or more of NLP functions crashed - continuing")
			continue

		# save the specific transcript CSV
		save_path = "../csv_with_features/" + filename
		cur_trans.to_csv(save_path, index=False)

		cur_trans["filename"] = [filename for x in range(cur_trans.shape[0])] # need filename for the summary op to work
		trans_dfs.append(cur_trans)

	if len(trans_dfs) == 0: # transcripts/csv folder could exist without there being anything in it - but should only be able to reach this if function called directly rather than through pipeline/bash module
		print("No available transcript CSVs for input OLID")
		return

	# finally compute the summary stats for this pt
	summary_save = "../../" + study + "_" + OLID + "_" + "phone_transcript_NLPFeaturesSummary.csv"
	final_summary = summarize_transcript_stats(trans_dfs)
	if os.path.isfile(summary_save):
		old_df = pd.read_csv(summary_save)
		join_csv=pd.concat([old_df, final_summary])
		join_csv.reset_index(drop=True, inplace=True)
		join_csv.drop_duplicates(subset=["filename"],inplace=True) # drop any duplicates just in case
		join_csv.to_csv(summary_save,index=False)
	else:
		final_summary.to_csv(summary_save,index=False)
		
if __name__ == '__main__':
    # Map command line arguments to function arguments.
    diary_transcript_nlp(sys.argv[1], sys.argv[2])
