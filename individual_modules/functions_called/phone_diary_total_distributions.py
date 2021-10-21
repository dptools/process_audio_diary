#!/usr/bin/env python

import os
import pandas as pd
import sys
from numpy import inf
from viz_helper_functions import distribution_plots

# make study-wide distribution plots for audio and transcript QC from phone diaries
# paths to input CSV and output PDF for each distribution currently hardcoded
def study_dists(study):
	# load audio QC distribution first
	audio_qc_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioQC-distribution.csv"
	try:
		audio_qc_dist = pd.read_csv(audio_qc_dist_path)
	except:
		audio_qc_dist = pd.DataFrame()

	# now make PDF
	pdf_out_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioQC-distributionPlots.pdf"
	if not audio_qc_dist.empty:
		try:
			os.remove(pdf_out_path) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
		except:
			pass
		# chose bin settings with manual iteration, since automatic generation wasn't showing details we want. this will be another hardcoded thing to revisit
		# may need to further update bins as well based on closer look at results, particularly for the newer VAD features
		distribution_plots(audio_qc_dist, pdf_out_path, ignore_list=["day","patient"], bins_list=[24,16,20,20,20,16,20,20,20,20], 
						   ranges_list=[(4,27),(0.0,4.0),(0.0,100.0),(0.0,0.2),(0.0,0.1),(0.0,4.0),(0,200),(0.0,10.0),(0.0,100.0),(0.0,0.1)])
	else:
		print("no audio QC for this study yet")

	# now repeat for the transcripts
	transcript_qc_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptQC-distribution.csv"
	try:
		transcript_qc_dist = pd.read_csv(transcript_qc_dist_path)
	except:
		transcript_qc_dist = pd.DataFrame()

	# plotting transcripts
	pdf_out_path_trans = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptQC-distributionPlots.pdf"
	if not transcript_qc_dist.empty:
		try:
			os.remove(pdf_out_path_trans) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
		except:
			pass
		# chose bin settings with manual iteration, since automatic generation wasn't showing details we want. this will be another hardcoded thing to revist
		distribution_plots(transcript_qc_dist, pdf_out_path_trans, ignore_list=["day","patient","ET_hour_int_formatted"], 
						   bins_list=[12,24,21,25,6,6,11,25,36,36,36,25,25,16,12,10,20], 
						   ranges_list=[(0,60),(0,600),(0,20),(0,50),(0,5),(0,5),(0,10),(0,50),(0,35),(0,35),(0,35),(0,125),(0,75),(-0.05,0.15),(0.0,1.0),(-0.01,0.015),(0.0,0.1)])
	else:
		print("no transcript QC for this study yet")

	# now do the same for OpenSMILE
	OS_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioOpenSMILESummary-distribution.csv"
	try:
		OS_dist = pd.read_csv(OS_dist_path)
	except:
		OS_dist = pd.DataFrame()

	# plotting OpenSMILE
	pdf_out_path_OS = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioOpenSMILESummary-distributionPlots.pdf"
	if not OS_dist.empty:
		try:
			os.remove(pdf_out_path_OS) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
		except:
			pass
		distribution_plots(OS_dist, pdf_out_path_OS, ignore_list=["day","patient","ET_hour_int_formatted"], bins_list=[24,10,12,20,10,10,16,10,10,6,10,10,25,25,30,30,10,10,16,7,16,7,24,12,16,8,12,6,24,10,12,6,32,16,12,6],
					   ranges_list=[(0.0,6.0),(0.0,2.5),(-40,20),(0,20),(0,50),(0,20),(-0.2,0.2),(0.0,0.1),(-0.05,0.05),(0.0,0.03),(0,50),(0,25),(0.0,0.25),(0.0,0.5),(0.0,3.0),(0.0,3.0),(-10,10),(0,10),(-40,40),(0,70),(-40,40),(0,70),
					   				(0,1200),(0,600),(0,1600),(0,800),(-250,50),(0,150),(0,2400),(0,1000),(-250,50),(0,150),(0,3200),(0,1600),(-250,50),(0,150)])
		# use hard-coded bin limits so that the per patient summaries will all use the same bins (as well as the study-wide) -> also matching between raw and pause filtered!
	else:
		print("no OpenSMILE results summary for this study yet")

	# repeat with filtered OpenSMILE - just paste and update filepaths from above
	OS_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioFilteredOpenSMILESummary-distribution.csv"
	try:
		OS_dist = pd.read_csv(OS_dist_path)
	except:
		OS_dist = pd.DataFrame()

	# plotting filtered OpenSMILE
	pdf_out_path_OS = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioFilteredOpenSMILESummary-distributionPlots.pdf"
	if not OS_dist.empty:
		try:
			os.remove(pdf_out_path_OS) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
		except:
			pass
		distribution_plots(OS_dist, pdf_out_path_OS, ignore_list=["day","patient","ET_hour_int_formatted"], bins_list=[24,10,12,20,10,10,16,10,10,6,10,10,25,25,30,30,10,10,16,7,16,7,24,12,16,8,12,6,24,10,12,6,32,16,12,6],
					   ranges_list=[(0.0,6.0),(0.0,2.5),(-40,20),(0,20),(0,50),(0,20),(-0.2,0.2),(0.0,0.1),(-0.05,0.05),(0.0,0.03),(0,50),(0,25),(0.0,0.25),(0.0,0.5),(0.0,3.0),(0.0,3.0),(-10,10),(0,10),(-40,40),(0,70),(-40,40),(0,70),
					   				(0,1200),(0,600),(0,1600),(0,800),(-250,50),(0,150),(0,2400),(0,1000),(-250,50),(0,150),(0,3200),(0,1600),(-250,50),(0,150)])
		# use hard-coded bin limits so that the per patient summaries will all use the same bins (as well as the study-wide) -> also matching between raw and pause filtered!
	else:
		print("no filtered OpenSMILE results summary for this study yet")

	# finally do for transcript NLP features
	transcript_nlp_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptNLP-distribution.csv"
	try:
		transcript_nlp_dist = pd.read_csv(transcript_nlp_dist_path)
	except:
		transcript_nlp_dist = pd.DataFrame()

	# plotting NLP
	pdf_out_path_nlp = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptNLP-distributionPlots.pdf"
	if not transcript_nlp_dist.empty:
		try:
			os.remove(pdf_out_path_nlp) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
		except:
			pass
		distribution_plots(transcript_nlp_dist, pdf_out_path_nlp, ignore_list=["day","patient","ET_hour_int_formatted"],
					   bins_list=[10,8,15,8,12,12,10,8,20,10,12,12,5,5,6,5,15,10,20,35,10,10,10,10,15,8,15,30,10,10,10,8,15,8,15,15,20,10,20,20,10,2,10,2,10,2], 
					   ranges_list=[(0,50),(0,40),(0,150),(0,40),(2,8),(0,6),(2,12),(0,8),(1.5,3.5),(0.0,1.0),(2.0,5.0),(0.0,3.0),(0.0,1.25),(0.0,0.5),(0.0,1.5),(0.0,1.25),
					   				(1.0,1.75),(0.0,0.5),(1.0,2.0),(0.0,1.75),(0.0,0.5),(0.0,0.5),(0.0,1.0),(0.0,0.5),(1.0,1.75),(0.0,0.4),(1.25,2.0),(0.0,1.5),(0.0,0.5),(0.0,0.25),(0.0,1.0),(0.0,0.4),
					   				(0.25,1.75),(0.0,0.4),(0.5,2.0),(0.0,1.5),(-1.0,1.0),(0.0,1.0),(-1.0,1.0),(-1.0,1.0),(0,9),(0,1),(0,9),(0,1),(0,9),(0,1)])
		# use hard-coded bin limits so that the per patient summaries will all use the same bins (as well as the study-wide)
	else:
		print("no transcript NLP for this study yet")

# use the study-wide distributions to create a single merged dataframe pared down to the most essential features per diary
# also creates another histogram PDF from this filtered CSV
# then save a CSV that summarizes more basic diary metadata per OLID (this one mainly getting at availability and basic quality measures)
def study_summary(study):
	# start with settings info:

	# study distribution paths
	audio_qc_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioQC-distribution.csv"
	transcript_qc_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptQC-distribution.csv"
	OS_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioOpenSMILESummary-distribution.csv"
	OS_filtered_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioFilteredOpenSMILESummary-distribution.csv"
	transcript_nlp_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptNLP-distribution.csv"

	# features to merge on
	diary_ID_feats = ["day","patient","ET_hour_int_formatted"]

	# select features to keep per modality
	audio_qc_feats = ["overall_db","length(minutes)","total_speech_minutes","number_of_pauses"]
	transcript_qc_feats = ["num_sentences","num_words","num_inaudible","num_questionable","num_redacted","num_nonverbal_edits","num_verbal_edits","num_restarts","num_repeats"]
	opensmile_feats = ["mean_Loudness_sma3","mean_F0semitoneFrom27.5Hz_sma3nz","mean_jitterLocal_sma3nz","mean_shimmerLocaldB_sma3nz",
					   "mean_F1frequency_sma3nz","mean_F2frequency_sma3nz","mean_F3frequency_sma3nz"]
	filtered_opensmile_feats = ["pauses_removed_" + x for x in opensmile_feats]
	nlp_feats = ["speaking-rate_file-mean","word-uncommonness-mean_file-mean","pairwise-coherence-mean_file-mean","pairwise-coherence-mean_file-max","pairwise-coherence-mean_file-min",
				 "coherence-with-prev-sentence_file-mean","sentence-sentiment_file-mean","sentence-sentiment_file-max","sentence-sentiment_file-min"]
	
	# bin information to use for the new PDF - use same bins for a given feature as are used in the larger PDFs
	full_bins_list = [24,20,16,16,20,12,24,6,6,11,25,36,36,36,24,10,25,30,24,24,32,24,10,25,30,24,24,32,12,20,15,15,30,15,20,20,20]
	full_ranges_list = [(4,27),(0.0,100.0),(0.0,4.0),(0.0,4.0),(0,200),(0,60),(0,600),(0,5),(0,5),(0,10),(0,50),(0,35),(0,35),(0,35),
						(0.0,6.0),(0,50),(0.0,0.25),(0.0,3.0),(0,1200),(0,2400),(0,3200),(0.0,6.0),(0,50),(0.0,0.25),(0.0,3.0),(0,1200),(0,2400),(0,3200),
						(2,8),(1.5,3.5),(1.0,1.75),(1.25,2.0),(0.0,1.5),(0.25,1.75),(-1.0,1.0),(-1.0,1.0),(-1.0,1.0)]
	# goes in order DFs are merged, and within using the order that the above lists use - submission time will be very first and then go through starting at audio qc

	# out paths
	combined_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneDiaryKeyFeatures-distribution.csv"
	combined_pdf_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneDiaryKeyFeatures-distributionPlots.pdf"
	OLID_summary_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneDiarySummary-perOLID.csv"

	# now load in DFs and do merges:

	# for each type of distribution, if it doesn't exist yet will make an empty DF to merge, since will be doing outer merge anyway
	# after loading each in filter to only the relevant columns
	try:
		audio_qc_dist = pd.read_csv(audio_qc_dist_path)
		audio_qc_dist = audio_qc_dist[diary_ID_feats + audio_qc_feats]
	except:
		audio_qc_dist = pd.DataFrame(columns=diary_ID_feats+audio_qc_feats)
	try:
		transcript_qc_dist = pd.read_csv(transcript_qc_dist_path)
		transcript_qc_dist = transcript_qc_dist[diary_ID_feats + transcript_qc_feats]
	except:
		transcript_qc_dist = pd.DataFrame(columns=diary_ID_feats+transcript_qc_feats)
	try:
		OS_dist = pd.read_csv(OS_dist_path)
		OS_dist = OS_dist[diary_ID_feats + opensmile_feats]
	except:
		OS_dist = pd.DataFrame(columns=diary_ID_feats+opensmile_feats)
	try:
		# add prefix to columns to make sure when DFs are merged we can distinguish the raw and filtered versions
		OS_filtered_dist = pd.read_csv(OS_filtered_dist_path).add_prefix("pauses_removed_")
		# need to rename the key merge columns back to the original names though!
		OS_filtered_dist.rename(columns={"pauses_removed_day":"day","pauses_removed_patient":"patient","pauses_removed_ET_hour_int_formatted":"ET_hour_int_formatted"}, inplace=True) 
		OS_filtered_dist = OS_filtered_dist[diary_ID_feats + filtered_opensmile_feats]
	except:
		OS_filtered_dist = pd.DataFrame(columns=diary_ID_feats+filtered_opensmile_feats)
	try:
		transcript_nlp_dist = pd.read_csv(transcript_nlp_dist_path)
		transcript_nlp_dist = transcript_nlp_dist[diary_ID_feats + nlp_feats]
	except:
		transcript_nlp_dist = pd.DataFrame(columns=diary_ID_feats+nlp_feats)

	combined_df = audio_qc_dist.merge(transcript_qc_dist, on=diary_ID_feats, how="outer").merge(OS_dist, on=diary_ID_feats, how="outer").merge(OS_filtered_dist, on=diary_ID_feats, how="outer").merge(transcript_nlp_dist, on=diary_ID_feats, how="outer")

	# also remove any -infinity values popping up in the decibel field: okay to replace with 0
	combined_df.replace(to_replace=-inf, value=0, inplace=True)

	# save new DF and generate PDF:

	# make sure the DF isn't empty first
	if combined_df.empty:
		print("No distribution info for this study yet, exiting")
		return

	combined_df.to_csv(combined_dist_path,index=False)

	try:
		os.remove(combined_pdf_path) # pdf writer can have problems with overwriting automatically, so intentionally delete if there is a preexisting PDF with this name
	except:
		pass
	distribution_plots(combined_df, combined_pdf_path, ignore_list=["day","patient"], bins_list=full_bins_list, ranges_list=full_ranges_list)

	# finally deal with the OLID-based summary

	# new column names for the basic summary info that will be compiled per OLID
	summary_feats = ["patient","num_days_diary_period","diaries_count","transcribed_count","sum_length(minutes)","sum_total_speech_minutes","sum_transcribed_words",
					 "mean_overall_db","stdev_overall_db","min_overall_db","max_overall_db"]

	# narrow down to only the columns needed for the summaries, and then group the DF by OLID
	summary_df = combined_df[["patient","day","length(minutes)","total_speech_minutes","num_words","overall_db"]]
	summary_df_grouped = summary_df.groupby(by="patient")

	# do the various summary operations and take only the columns relevant for that operation
	grouped_df_count = summary_df_grouped.count().reset_index()[["patient","day","num_words"]]
	grouped_df_sum = summary_df_grouped.sum().reset_index()[["patient","length(minutes)","total_speech_minutes","num_words"]]
	grouped_df_mean = summary_df_grouped.mean().reset_index()[["patient","overall_db"]]
	grouped_df_stdev = summary_df_grouped.std().reset_index()[["patient","overall_db"]]
	grouped_df_min = summary_df_grouped.min().reset_index()[["patient","day","overall_db"]]
	grouped_df_max = summary_df_grouped.max().reset_index()[["patient","day","overall_db"]]

	# begin by merging min and max so it can be used to get study day period length
	grouped_df_min.rename(columns={"overall_db":"min_overall_db","day":"min_day"}, inplace=True)
	grouped_df_max.rename(columns={"overall_db":"max_overall_db","day":"max_day"}, inplace=True)
	grouped_df_extremes = grouped_df_min.merge(grouped_df_max, on="patient", how="inner")
	grouped_df_extremes["num_days_diary_period"] = grouped_df_extremes["max_day"] - grouped_df_extremes["min_day"]

	# now merge in the rest of the summary stat DFs 
	grouped_df_mean.rename(columns={"overall_db":"mean_overall_db"}, inplace=True)
	grouped_df_stdev.rename(columns={"overall_db":"stdev_overall_db"}, inplace=True)
	grouped_df_summary_stats = grouped_df_extremes.merge(grouped_df_mean, on="patient", how="inner").merge(grouped_df_stdev, on="patient", how="inner")

	# finally merge in the aggregate stats and then filter/reorder columns as set above
	grouped_df_count.rename(columns={"day":"diaries_count","num_words":"transcribed_count"}, inplace=True)
	grouped_df_sum.rename(columns={"length(minutes)":"sum_length(minutes)","total_speech_minutes":"sum_total_speech_minutes","num_words":"sum_transcribed_words"}, inplace=True)
	grouped_df_agg_stats = grouped_df_count.merge(grouped_df_sum, on="patient", how="inner")
	grouped_df_final = grouped_df_summary_stats.merge(grouped_df_agg_stats, on="patient", how="outer") # do outer merge in case discrepancy with transcript-related stats here
	OLID_summary = grouped_df_final[summary_feats] 

	# saving it to specified path before returning
	# for both of these CSVs okay to just overwrite every time
	OLID_summary.to_csv(OLID_summary_path, index=False)
	return

if __name__ == '__main__':
    # Map command line arguments to function arguments.
    study_dists(sys.argv[1])
    study_summary(sys.argv[1])
