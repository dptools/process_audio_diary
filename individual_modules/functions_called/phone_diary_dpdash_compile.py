#!/usr/bin/env python

import os
import sys
import pandas as pd
import numpy as np
import datetime

# don't need to worry about this pandas warning in below script, so supress it 
pd.options.mode.chained_assignment = None

def dpdash_compile(study, OLID):
	# specify column headers that will be used for new CSV - 
	# those necessary for DPDash plus the matching audio filename, the transcript filename if available, and the name for final OpenSMILE results (VAD filtered)
	new_headers=["reftime","day","timeofday","weekday","study","patient","filename","transcript_name","filtered_opensmile_name"]

	# now specify the column headers that will be kept from the other relevant CSVs, in order (they will go after the DPDash cols)
	# first doing metadata ones -
	# recording number is a count of all diary submissions, date is the actual date the audio was assigned to, hour is the submission time in eastern 
	# (submission time is adjusted for late night submissions to go from 4 to 27)
	metadata_headers_to_keep=["recording_number","iso_date","ET_hour_int_formatted"]

	# then select only the audio qc features worth keeping -
	# first 4 features from the basic audio qc output, then the last 5 are from vad-derived measures
	# (see those scripts for more info on these features)
	# it is not yet clear how helpful pause_db or pause_flatness will be, so this may be modified in the future
	# could also end up including more information on the timing of pauses
	audio_qc_headers_to_keep=["length(minutes)","overall_db","amplitude_stdev","mean_flatness",
							  "total_speech_minutes","number_of_pauses","max_pause_seconds","pause_db","pause_flatness"]

	# if any transcripts are available, also format a transcript QC CSV separately, keeping the dpdash/metadata parts the same as it was for audio
	# again filtering down the transcript features a bit (will require more analysis to finalize what we should keep)
	transcript_qc_headers_to_keep=["num_subjects","num_sentences","num_words","min_words_in_sen","max_words_in_sen",
								   "num_inaudible","num_questionable","num_redacted",
								   "num_nonverbal_edits","num_verbal_edits","num_restarts","num_repeats","num_commas","num_dashes",
								   "min_timestamp_space","max_timestamp_space","min_timestamp_space_per_word","max_timestamp_space_per_word"]
	
	# get consent date for this patient, to use in determining study day
	try:
		study_metadata_path = "/data/sbdp/PHOENIX/GENERAL/" + study + "/" + study + "_metadata.csv"
		study_metadata = pd.read_csv(study_metadata_path)
		patient_metadata = study_metadata[study_metadata["Subject ID"] == OLID]
		consent_date_str = patient_metadata["Consent"].tolist()[0]
		consent_date = datetime.datetime.strptime(consent_date_str,"%Y-%m-%d")
	except:
		# occasionally we encounter issues with the study metadata file, so adding a check here
		print("No consent date information in the study metadata CSV for input OLID " + OLID + ", please review. Skipping for now.")
		return

	# navigate to folder of interest, load initial CSVs
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio")
		audio_metadata = pd.read_csv(study + "_" + OLID + "_phone_audio_ETFileMap.csv")
		audio_qc_basic = pd.read_csv(study + "_" + OLID + "_phone_audioQC_output.csv")
	except:
		# require both of the basic audio process outputs in order to compile DPDash CSV
		print("No processed phone audio exists for input OLID " + OLID + ", continuing") # should only be possible to reach this error if not called from the bash module
		return

	try:
		audio_vad = pd.read_csv(study + "_" + OLID + "_phone_audioVAD_pauseDerivedQC_output.csv")
	except:
		# VAD however can be optional. since doing left merge anyway, just create an empty dataframe with the relevant columns
		audio_vad = pd.DataFrame(columns=["filename","total_speech_minutes","number_of_pauses","max_pause_seconds","pause_db","pause_flatness"])

	# make full audio QC dataframe that includes all the VAD-derived measures in addition to the basic QC
	audio_qc = audio_qc_basic.merge(audio_vad,on="filename",how="left") # do left merge so files too short for VAD will still be kept

	# merge the existing audio filename formatting CSV with the existing audio QC output
	prefixes = audio_metadata["new_filename"].tolist()
	audio_metadata["filename"] = [str(x) + ".wav" for x in prefixes]
	intermediate = audio_metadata.merge(audio_qc,on="filename",how="inner")

	# get dpdash info
	recording_dates = [datetime.datetime.strptime(x,"%Y-%m-%d") for x in intermediate["iso_date"].tolist()]
	study_days = [(x - consent_date).days + 1 for x in recording_dates] # study day starts at 1 on day of consent
	weekdays = [((x.weekday() + 2) % 7) + 1 for x in recording_dates] # dpdash considers saturday 1 and friday 7, while date.weekday() will return monday 0 through sunday 6
	patients = [OLID for x in range(len(recording_dates))]
	studies = [study for x in range(len(recording_dates))]
	# fill in the remaining columns with nan - reftime and timeofday will be too confusing to fill out given the hour conversion assignment I did
	reftimes=[np.nan for x in range(len(recording_dates))]
	timeofdays=[np.nan for x in range(len(recording_dates))]

	# now get filenames that will be merged on
	fnames = intermediate["filename"].tolist()
	# then check for transcripts
	possible_transcript_names = [study + "_" + OLID + "_phone_audioTranscript_day" + str(x).zfill(4) + ".csv" for x in study_days]
	try:
		actual_transcript_names = os.listdir("transcripts/csv")
	except:
		actual_transcript_names = []
	transcript_name_list = [x if x in actual_transcript_names else np.nan for x in possible_transcript_names]
	# finally check for filtered OpenSMILE results - should exist for every row when this is called via main pipeline!
	possible_opensmile_names = [study + "_" + OLID + "_phone_audioSpeechOnly_OpenSMILE_day" + str(x).zfill(4) + ".csv" for x in study_days]
	try:
		actual_opensmile_names = os.listdir("opensmile_features_filtered")
	except:
		actual_opensmile_names = []
	opensmile_name_list = [x if x in actual_opensmile_names else np.nan for x in possible_opensmile_names]

	# construct new df with DPDash info to merge into existing dataframe 
	values = [reftimes, study_days, timeofdays, weekdays, studies, patients, fnames, transcript_name_list, opensmile_name_list]
	new_csv = pd.DataFrame()
	for i in range(len(new_headers)):
		h = new_headers[i]
		vals = values[i]
		new_csv[h] = vals

	# do the merge and select columns of choice
	final_csv_join = new_csv.merge(intermediate,on="filename",how="inner")
	final_cols = [x for x in new_headers]
	final_cols.extend(metadata_headers_to_keep)
	final_cols.extend(audio_qc_headers_to_keep)
	final_csv = final_csv_join[final_cols]
	# sort the df before saving it
	final_csv.sort_values(by="day",inplace=True)

	# get output name of choice
	final_day = final_csv["day"].tolist()[-1]
	output_name = study + "-" + OLID + "-phoneAudioQC-day1to" + str(final_day) + ".csv"
	# now actually save CSV
	final_csv.to_csv(output_name,index=False)

	# delete the old DPDash formatted files, as this naming convention won't overwrite anything - need to check for old days
	for d in range(1,study_days[-1]): # probably is a more efficient way to do this, but works fast in practice
		if os.path.isfile(study+"-"+OLID+"-phoneAudioQC-day1to" + str(d) + ".csv"):
			os.remove(study+"-"+OLID+"-phoneAudioQC-day1to" + str(d) + ".csv")

	# now check for transcript QC output similarly
	try:
		transcript_qc = pd.read_csv(study + "_" + OLID + "_phone_audio_transcriptQC_output.csv")
	except:
		# no transcripts yet for this OLID, so nothing left for function to do. 
		return

	# transcript QC will be strict subset of audio QC, so use above CSV to easily get DPDash formatted version of the transcript QC outputs
	final_transcript_csv_join = transcript_qc.merge(final_csv,on="transcript_name",how="inner")
	final_cols_transcript = [x for x in new_headers]
	final_cols_transcript.extend(metadata_headers_to_keep)
	final_cols_transcript.extend(transcript_qc_headers_to_keep)
	final_transcript_csv = final_transcript_csv_join[final_cols_transcript]
	final_transcript_csv.sort_values(by="day",inplace=True)

	# and save and delete old versions similarly to above
	# file name is currently hard coded to begin at study day 1 i.e. day of consent - should potentially inquire if it is better to start the file name at the first study day where data appears?
	output_name_transcript = study + "-" + OLID + "-phoneTranscriptQC-day1to" + str(final_day) + ".csv" # note the final day of available audio may be much larger than the last day of available transcript, but naming this using the audio final day
	# now actually save CSV
	final_transcript_csv.to_csv(output_name_transcript,index=False)
	# delete the old DPDash formatted files, as this naming convention won't overwrite anything - need to check for old days
	for d in range(1,study_days[-1]): 
		if os.path.isfile(study+"-"+OLID+"-phoneTranscriptQC-day1to" + str(d) + ".csv"):
			os.remove(study+"-"+OLID+"-phoneTranscriptQC-day1to" + str(d) + ".csv")

	# function is now totally done for this patient

if __name__ == '__main__':
    # Map command line arguments to function arguments.
    dpdash_compile(sys.argv[1], sys.argv[2])
