#!/usr/bin/env python

import os
import pandas as pd
import numpy as np
import glob
import sys
import math
from viz_helper_functions import generate_horizontal_heatmap

# don't need to worry about this pandas warning in below script, so supress it 
pd.options.mode.chained_assignment = None

def diary_qc_heatmap(study, OLID, wipe=False):
	# switch to specific patient folder
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio")
	except:
		print("Problem with input arguments") # should never reach this error if calling via bash module
		return

	# load current QC file
	cur_QC_path = glob.glob(study + "-" + OLID + "-phoneAudioQC-day1to*.csv")[0] # should only ever be one match if called from module
	cur_QC = pd.read_csv(cur_QC_path)

	# prep to fill in empty days
	days_avail = cur_QC["day"].tolist()
	first_day = days_avail[0]
	last_day = days_avail[-1]
	if first_day < 1 or last_day != max(days_avail):
		print("Problem with study day numbering for subject " + OLID + ", exiting")
		return
	# also setup split into multiple heatmaps, do so week structure kept in tact - 13 weeks per heatmap so there will be ~4 heatmaps per year
	num_splits = int(math.ceil(float(last_day)/91.0)) # 91 days in 13 weeks, round up
	last_day_stretch = num_splits * 91 # fill it out to this divisible day, not the actual last day of available recording
	days_full = range(1,last_day_stretch+1)
	days_full_df = pd.DataFrame()
	days_full_df["day"] = days_full
	days_full_df["hack"] = ["hack" for x in days_full] # add a second column so pandas thinks the upcoming join is real
	full_QC = days_full_df.merge(cur_QC, on="day", how="left")

	# get weekday of day 1 for spacing of the thick bars
	weekday_list = cur_QC["weekday"].tolist()
	first_weekday = weekday_list[0] # first need weekday of first available day
	days_passed = first_day - 1 # get how many days passed between the day of consent (1) and the first available day
	if days_passed < first_weekday: # adjustment is easy if don't have to loop back around
		weekday_one = first_weekday - days_passed
	else:
		remaining_offset = days_passed - first_weekday # days left to go backwards after reset to 7
		adjusted_offset = remaining_offset % 7 # for every 7 days loop back around to 7 again, so just need the mod
		weekday_one = 7 - adjusted_offset # go backwards the additional remaining day
	# dpdash considers saturday 1 and friday 7, but really we want monday to have an offset of 0 and sunday an offset of 6 (as initial line would come 6 in in that case)
	weekday_offset = (weekday_one + 4) % 7

	# select features to use in heatmaps (days will already be in order)
	# note again these are hard-coded right now!
	select_features = ["length(minutes)","overall_db","mean_flatness","number_of_pauses","total_speech_minutes"]
	full_QC = full_QC[select_features]

	# now also load transcript QC to do similarly (if it exists) otherwise make blank df
	# load current QC file
	try:
		cur_QC_path_trans = glob.glob(study + "-" + OLID + "-phoneTranscriptQC-day1to*.csv")[0] # won't be a match unless there are transcripts for this patient
		cur_QC_trans = pd.read_csv(cur_QC_path_trans)
	except:
		cur_QC_trans = pd.DataFrame()

	# setup features to use from transcript QC (note again these are hard coded right now)
	select_features_trans = ["num_sentences","num_words","num_inaudible","num_questionable","num_redacted","min_timestamp_space_per_word"]

	if cur_QC_trans.empty: # if couldn't load a real df earlier means no transcripts, fill the select columns with NaNs
		full_QC_trans = pd.DataFrame()
		for tfeat in select_features_trans:
			full_QC_trans[tfeat] = [np.nan for x in range(len(days_full))]
	else:
		full_QC_trans = days_full_df.merge(cur_QC_trans, on="day", how="left") # use same day list as audio here because transcripts available must be a subset
		full_QC_trans = full_QC_trans[select_features_trans]

	# concatenate the feature columns for the two to get final df to work from
	final_QC = pd.concat([full_QC, full_QC_trans], axis=1) 

	# now actually make heatmaps
	# chose settings with some manual iteration, this will be another hardcoded thing to revist
	# set up unimodal features to be only white to red by including negative in the bound
	# may require additional adjustments as we test
	# also name the features on the plot to make clear what the ranges are
	abs_col_bounds_list=[(0.0,4.0),(20,100),(-0.1,0.1),(0,75),(0.0,4.0),(0,35),(0,400),(-4,4),(-4,4),(-6,6),(-0.0075,0.0075)] 
	features_with_ranges = ["Audio Length (0 to 4 minutes)", "Volume (20 to 100 db)", "Spectral Flatness (-0.1 to 0.1)", 
							"Number of Pauses (0 to 75)", "Speech Length (0 to 4 miuntes)", 
							"Sentence Count (0 to 35)", "Word Count (0 to 400)", 
							"Inaudible Count (-4 to 4)", "Questionable Count (-4 to 4)", "Redacted Count (-6 to 6)",
							"Quickest Sentence (-0.0075 to 0.0075 minutes/word)"]
	for i in range(num_splits): # loop through sections to make the heatmaps
		out_path = "heatmaps/" + study + "-" + OLID + "-phoneDiaryQC-featureProgression-days" + str(i*91 + 1) + "to" + str((i+1)*91) + ".png" # output name again hardcoded (per patient/study) for now
		if (not wipe) and (i < num_splits - 1) and (os.path.exists(out_path)):
			# the last of the split may need to be updated due to new diaries, but assume by default that there will never be old data filled in from before the most recent day, so don't need to actually recreate those heatmaps. 
			# should speed up function a bit on subsequent runs
			continue	
		cur_slice = final_QC.iloc[i*91:(i+1)*91, :]
		generate_horizontal_heatmap(cur_slice, out_path, abs_col_bounds_list=abs_col_bounds_list, bars_width=7, time_bars_offset=weekday_offset, time_nums_offset=i*91, cluster_bars_index=[4], label_time=True, features_rename=features_with_ranges)
	
if __name__ == '__main__':
    # Map command line arguments to function arguments.
    # when pipeline calls it will always assume wipe is false, so not all heatmaps will be regenerated.
    # if need all heatmaps to be recreated, can call this script independently from command line with additional "True" or "1" argument
    # alternatively, could just delete old results manually and then rerun entire pipeline
    try:
    	if sys.argv[3]:
    		diary_qc_heatmap(sys.argv[1], sys.argv[2], wipe=True)
    	else:
    		diary_qc_heatmap(sys.argv[1], sys.argv[2])
    except:
    	diary_qc_heatmap(sys.argv[1], sys.argv[2])
