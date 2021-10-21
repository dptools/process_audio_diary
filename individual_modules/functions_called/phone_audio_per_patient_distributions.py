#!/usr/bin/env python

import os
import pandas as pd
import numpy as np
import glob
import sys
from viz_helper_functions import distribution_plots

# note that this function adds to the study distribution by concatenation and then dropping duplicates
# this will work well except in the case that new features are added - will need to rerun from scratch if so
# (can always change file name if don't want to lose previously compiled distribution in this case)

# in the future (perhaps before generalized release) could improve efficiency by checking if file is in the distribution already instead of always going through each one
# this will be particularly relevant for the OpenSMILE summaries, which do take a bit of time to run

def audio_dist(study, OLID):
	# switch to specific patient folder
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio")
	except:
		print("Problem with input arguments, or no processed audio for this patient yet") # should never reach this error if calling via bash module
		return

	# load current QC file
	cur_QC_path = glob.glob(study + "-" + OLID + "-phoneAudioQC-day1to*.csv")[0] # should only ever be one match if called from module
	cur_QC = pd.read_csv(cur_QC_path)
	# requires audio QC file to do the core work here, so not a big deal if it crashes on a given patient for not having one

	# before doing QC preprocessing prep a filemap for OpenSMILE portion later
	filemap = cur_QC[["filename", "day", "ET_hour_int_formatted"]]
	# also one for the VAD-filtered OpenSMILE
	filemap_filtered = cur_QC[["filtered_opensmile_name", "day", "ET_hour_int_formatted"]]

	# remove extraneous metadata from the QC spreadsheet - just want enough to identify each row uniquely, don't need easy path back to filenames or dates
	# note again these are hard-coded right now! audio features will be same as those found in DPDash
	select_features = ["day","patient","ET_hour_int_formatted","length(minutes)","overall_db","amplitude_stdev","mean_flatness",
					   "total_speech_minutes","number_of_pauses","max_pause_seconds","pause_db","pause_flatness"]
	cur_QC = cur_QC[select_features]

	print("Preparing audio feature distributions for " + OLID)
	# create patient-specific distribution PDF for the QC features
	pdf_out_path = study + "-" + OLID + "-phoneAudioQC-distributionPlots.pdf" # output name again hardcoded (per patient/study) for now
	try:
		os.remove(pdf_out_path) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
		# distribution continually updates so can't just skip if there is already an output!
	except:
		pass
	# chose bin settings with manual iteration, since automatic generation wasn't showing details we want. this will be another hardcoded thing to revisit
	# may need to further update bins as well based on closer look at results, particularly for the newer VAD features
	distribution_plots(cur_QC, pdf_out_path, ignore_list=["day","patient"], bins_list=[24,16,20,20,20,16,20,20,20,20], 
					   ranges_list=[(4,27),(0.0,4.0),(0.0,100.0),(0.0,0.2),(0.0,0.1),(0.0,4.0),(0,200),(0.0,10.0),(0.0,100.0),(0.0,0.1)])

	# now do the combining with existing df
	# path to study wide distribution we will add to - currently hard coded!
	# also assuming this folder structure for Distributions is pre-existing
	dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioQC-distribution.csv"
	
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

	# moving on to OpenSMILE distributions
	# features to consider is currently hard coded and currently contains all of them!
	# will likely want to cut down on the number of features plotted, possibly also remove the standard deviation summary
	OS_features = ["Loudness_sma3", "alphaRatio_sma3", "hammarbergIndex_sma3", "slope0-500_sma3", "slope500-1500_sma3", "F0semitoneFrom27.5Hz_sma3nz", "jitterLocal_sma3nz", 
				   "shimmerLocaldB_sma3nz", "HNRdBACF_sma3nz", "logRelF0-H1-H2_sma3nz", "logRelF0-H1-A3_sma3nz", "F1frequency_sma3nz", "F1bandwidth_sma3nz", 
				   "F1amplitudeLogRelF0_sma3nz", "F2frequency_sma3nz", "F2amplitudeLogRelF0_sma3nz", "F3frequency_sma3nz", "F3amplitudeLogRelF0_sma3nz"]
	# for this need to first summarize across the audio diaries for this patient
	# will take mean and stdev of each feature per diary for now
	pts = []
	days = []
	timestamps = []
	feature_means = [[] for x in range(len(OS_features))]
	feature_stds = [[] for x in range(len(OS_features))]
	# in addition to summaries, will also just directly plot each individual OS output as a histogram - mainly for comparing VAD filtered versus not

	try:
		os.chdir("opensmile_feature_extraction")
	except:
		print("No OpenSMILE results yet for " + OLID + ", skipping")
		return
	OS_files = os.listdir(".")
	if len(OS_files) == 0:
		print("No OpenSMILE results yet for " + OLID + ", skipping")
		return

	OS_files.sort()
	for OS_name in OS_files:
		# setup metadata for this file first
		name_match = OS_name.split(".")[0] + ".wav"
		match_df = filemap[filemap["filename"] == name_match]
		try:
			cur_day = match_df["day"].tolist()[0]
			cur_time = match_df["ET_hour_int_formatted"].tolist()[0]
		except:
			continue # no match, expect this currently for multiple submissions

		# only bother loading if the file hasn't already been processed - check by looking for existing distribution PDF for this diary
		pdf_out_path_cur = "per_diary_distribution_plots/" + study + "_" + OLID + "_phone_audio_OpenSMILE_day" + str(cur_day).zfill(4) + ".pdf" 
		if os.path.isfile(pdf_out_path_cur):
			continue

		# now look at OpenSMILE results
		try:
			cur_df = pd.read_csv(OS_name,sep=';')
			if cur_df.empty:
				continue
		except:
			continue

		# compile info for summary df
		# once file is safely loaded can start appending to feature lists 
		pts.append(OLID)
		days.append(cur_day)
		timestamps.append(cur_time)
		for feat in range(len(OS_features)):
			cur_feat = OS_features[feat]
			cur_vals = cur_df[cur_feat].tolist()
			feature_means[feat].append(np.nanmean(cur_vals))
			feature_stds[feat].append(np.nanstd(cur_vals))

		# also make distribution PDF for this particular diary
		# since only doing for diaries that are not secondary submissions, match to formatted OpenSMILE name also used in VAD-filtered results (w/o the "speech only" part here)
		distribution_plots(cur_df[OS_features], pdf_out_path_cur, bins_list=[30,10,14,20,10,40,40,40,12,16,16,20,14,14,16,14,18,14], 
						   ranges_list=[(0.0,7.5),(-50,50),(-70,70),(-0.5,0.5),(-0.25,0.25),(0,100),(0.0,1.0),(0.0,10.0),(-30,30),
						   				(-200,200),(-200,200),(0,2000),(0,3500),(-250,100),(0,4000),(-250,100),(0,4500),(-250,100)])
		# use hard-coded bin limits so that all files of this type will be plotted in the same way - also doing same for both raw and filtered OpenSMILE diaries!

	# back out of OS folder
	os.chdir("..")

	# save df for this patient's OpenSMILE results
	pt_df = pd.DataFrame()
	pt_df["patient"] = pts
	pt_df["day"] = days
	pt_df["ET_hour_int_formatted"] = timestamps
	for i in range(len(OS_features)):
		cur_feat = OS_features[i]
		cur_feat1 = "mean_" + cur_feat
		cur_feat2 = "stdev_" + cur_feat
		cur_vals1 = feature_means[i]
		cur_vals2 = feature_stds[i]
		pt_df[cur_feat1] = cur_vals1
		pt_df[cur_feat2] = cur_vals2
	pt_os_save_name = study + "_" + OLID + "_phone_audio_OpenSMILEFeaturesSummary.csv"
	pt_df.to_csv(pt_os_save_name, index=False)

	# create patient-specific distribution PDF now with the summary values
	pdf_out_path_OS = study + "-" + OLID + "-phoneAudioOpenSMILESummary-distributionPlots.pdf" # output name again hardcoded (per patient/study) for now
	try:
		os.remove(pdf_out_path_OS) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
	except:
		pass
	distribution_plots(pt_df, pdf_out_path_OS, ignore_list=["day","patient","ET_hour_int_formatted"], bins_list=[24,10,12,20,10,10,16,10,10,6,10,10,25,25,30,30,10,10,16,7,16,7,24,12,16,8,12,6,24,10,12,6,32,16,12,6],
					   ranges_list=[(0.0,6.0),(0.0,2.5),(-40,20),(0,20),(0,50),(0,20),(-0.2,0.2),(0.0,0.1),(-0.05,0.05),(0.0,0.03),(0,50),(0,25),(0.0,0.25),(0.0,0.5),(0.0,3.0),(0.0,3.0),(-10,10),(0,10),(-40,40),(0,70),(-40,40),(0,70),
					   				(0,1200),(0,600),(0,1600),(0,800),(-250,50),(0,150),(0,2400),(0,1000),(-250,50),(0,150),(0,3200),(0,1600),(-250,50),(0,150)])
	# use hard-coded bin limits so that the per patient summaries will all use the same bins (as well as the study-wide) -> also matching between raw and pause filtered!

	# finally do the combining with existing df
	# path to study wide distribution we will add to - currently hard coded!
	dist_path_OS = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioOpenSMILESummary-distribution.csv"
	
	# load study-wide distribution and concatentate
	try:
		cur_dist_OS = pd.read_csv(dist_path_OS)
		cur_dist_OS = pd.concat([cur_dist_OS, pt_df], ignore_index=True)
		cur_dist_OS.drop_duplicates(subset=["day","patient","ET_hour_int_formatted"], inplace=True)
		cur_dist_OS.reset_index(drop=True, inplace=True)
	except:
		# if this is the first patient ever being processed for this study then can just set to be pt_df
		# will also hit this exception if concat fails, which should only occur when there is a column mismatch - so if feature set changes
		cur_dist_OS = pt_df

	# save the new study-wide dist
	cur_dist_OS.to_csv(dist_path_OS, index=False)

	# repeat the entire process with filtered OpenSMILE results from VAD, where available - pasting same code again, just change filename parts and make sure can handle NaNs
	# features to consider is currently hard coded and currently contains all of them!
	# will likely want to cut down on the number of features plotted, possibly also remove the standard deviation summary
	OS_features = ["Loudness_sma3", "alphaRatio_sma3", "hammarbergIndex_sma3", "slope0-500_sma3", "slope500-1500_sma3", "F0semitoneFrom27.5Hz_sma3nz", "jitterLocal_sma3nz", 
				   "shimmerLocaldB_sma3nz", "HNRdBACF_sma3nz", "logRelF0-H1-H2_sma3nz", "logRelF0-H1-A3_sma3nz", "F1frequency_sma3nz", "F1bandwidth_sma3nz", 
				   "F1amplitudeLogRelF0_sma3nz", "F2frequency_sma3nz", "F2amplitudeLogRelF0_sma3nz", "F3frequency_sma3nz", "F3amplitudeLogRelF0_sma3nz"]
	# for this need to first summarize across the audio diaries for this patient
	# will take mean and stdev of each feature per diary for now
	pts = []
	days = []
	timestamps = []
	feature_means = [[] for x in range(len(OS_features))]
	feature_stds = [[] for x in range(len(OS_features))]
	# in addition to summaries, will also just directly plot each individual OS output as a histogram - mainly for comparing VAD filtered versus not

	try:
		os.chdir("opensmile_features_filtered")
	except:
		print("No filtered OpenSMILE results yet for " + OLID + ", skipping")
		return
	OS_files = os.listdir(".")
	if len(OS_files) == 0:
		print("No filtered OpenSMILE results yet for " + OLID + ", skipping")
		return

	OS_files.sort()
	for OS_name in OS_files:
		match_df = filemap_filtered[filemap_filtered["filtered_opensmile_name"] == OS_name]
		# should always have exactly one match here, at least if this is run from pipeline
		# but keep in try/catch anyway to be safe
		try:
			cur_day = match_df["day"].tolist()[0]
			cur_time = match_df["ET_hour_int_formatted"].tolist()[0]
		except:
			continue

		# only bother loading if the file hasn't already been processed - check by looking for existing distribution PDF for this diary
		pdf_out_path_cur = "per_diary_distribution_plots/" + OS_name.split(".")[0] + ".pdf" 
		if os.path.isfile(pdf_out_path_cur):
			continue

		# now look at OpenSMILE results
		try:
			cur_df = pd.read_csv(OS_name) # will actually be using commas now
			if cur_df.empty:
				continue
		except:
			continue

		# compile info for summary df
		# once file is safely loaded can start appending to feature lists 
		pts.append(OLID)
		days.append(cur_day)
		timestamps.append(cur_time)
		for feat in range(len(OS_features)):
			cur_feat = OS_features[feat]
			cur_vals = cur_df[cur_feat].tolist()
			# already good to go with NaNs
			feature_means[feat].append(np.nanmean(cur_vals))
			feature_stds[feat].append(np.nanstd(cur_vals))

		# also make distribution PDF for this particular diary
		# done using the default 10 ms bins
		distribution_plots(cur_df[OS_features], pdf_out_path_cur, bins_list=[30,10,14,20,10,40,40,40,12,16,16,20,14,14,16,14,18,14], 
						   ranges_list=[(0.0,7.5),(-50,50),(-70,70),(-0.5,0.5),(-0.25,0.25),(0,100),(0.0,1.0),(0.0,10.0),(-30,30),
						   				(-200,200),(-200,200),(0,2000),(0,3500),(-250,100),(0,4000),(-250,100),(0,4500),(-250,100)])
		# use hard-coded bin limits so that all files of this type will be plotted in the same way - also doing same for both raw and filtered OpenSMILE diaries!

	# back out of OS folder
	os.chdir("..")

	# save df for this patient's filtered OpenSMILE results
	pt_df = pd.DataFrame()
	pt_df["patient"] = pts
	pt_df["day"] = days
	pt_df["ET_hour_int_formatted"] = timestamps
	for i in range(len(OS_features)):
		cur_feat = OS_features[i]
		cur_feat1 = "mean_" + cur_feat
		cur_feat2 = "stdev_" + cur_feat
		cur_vals1 = feature_means[i]
		cur_vals2 = feature_stds[i]
		pt_df[cur_feat1] = cur_vals1
		pt_df[cur_feat2] = cur_vals2
	pt_os_save_name = study + "_" + OLID + "_phone_audio_filteredOpenSMILEFeaturesSummary.csv"
	pt_df.to_csv(pt_os_save_name, index=False)

	# create patient-specific distribution PDF now
	pdf_out_path_OS = study + "-" + OLID + "-phoneAudioFilteredOpenSMILESummary-distributionPlots.pdf" # output name again hardcoded (per patient/study) for now
	try:
		os.remove(pdf_out_path_OS) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
	except:
		pass
	distribution_plots(pt_df, pdf_out_path_OS, ignore_list=["day","patient","ET_hour_int_formatted"], bins_list=[24,10,12,20,10,10,16,10,10,6,10,10,25,25,30,30,10,10,16,7,16,7,24,12,16,8,12,6,24,10,12,6,32,16,12,6],
					   ranges_list=[(0.0,6.0),(0.0,2.5),(-40,20),(0,20),(0,50),(0,20),(-0.2,0.2),(0.0,0.1),(-0.05,0.05),(0.0,0.03),(0,50),(0,25),(0.0,0.25),(0.0,0.5),(0.0,3.0),(0.0,3.0),(-10,10),(0,10),(-40,40),(0,70),(-40,40),(0,70),
					   				(0,1200),(0,600),(0,1600),(0,800),(-250,50),(0,150),(0,2400),(0,1000),(-250,50),(0,150),(0,3200),(0,1600),(-250,50),(0,150)])
	# use hard-coded bin limits so that the per patient summaries will all use the same bins (as well as the study-wide) -> also matching between raw and pause filtered!

	# finally do the combining with existing df
	# path to study wide distribution we will add to - currently hard coded!
	dist_path_OS = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioFilteredOpenSMILESummary-distribution.csv"
	
	# load study-wide distribution and concatentate
	try:
		cur_dist_OS = pd.read_csv(dist_path_OS)
		cur_dist_OS = pd.concat([cur_dist_OS, pt_df], ignore_index=True)
		cur_dist_OS.drop_duplicates(subset=["day","patient","ET_hour_int_formatted"], inplace=True)
		cur_dist_OS.reset_index(drop=True, inplace=True)
	except:
		# if this is the first patient ever being processed for this study then can just set to be pt_df
		# will also hit this exception if concat fails, which should only occur when there is a column mismatch - so if feature set changes
		cur_dist_OS = pt_df

	# save the new study-wide dist
	cur_dist_OS.to_csv(dist_path_OS, index=False)

	# function finally done
	return

if __name__ == '__main__':
    # Map command line arguments to function arguments.
    audio_dist(sys.argv[1], sys.argv[2])
