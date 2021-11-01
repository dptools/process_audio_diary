#!/usr/bin/env python

import os
import sys
import glob
import shutil
import pandas as pd
import numpy as np

def move_audio_to_send(study, OLID, length_cutoff, db_cutoff):
	# navigate to folder of interest, load initial CSVs
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio")
		dpdash_name_format = study + "-" + OLID + "-phoneAudioQC-day1to*.csv"
		dpdash_name = glob.glob(dpdash_name_format)[0] # DPDash script deletes any older days in this subfolder, so should only get 1 match each time
		dpdash_qc = pd.read_csv(dpdash_name)
		os.chdir("decrypted_files") # now actually go into folder with audios to be checked
	except:
		print("No new phone audio for input OLID " + OLID + ", continuing") # should only be possible to reach this error if not called from the bash module
		return

	# loop through the audios available in decrypted_files
	# if acceptable will match name to desired transcript name, and move to to_send folder
	# if unacceptable will rename to prepend an error code, keep in decrypted_files
	cur_decrypted = os.listdir(".")
	for filen in cur_decrypted:
		if filen=="smile.log":
			os.remove(filen) # make sure OpenSMILE log files don't count towards the error rate!
			continue
		if filen=="foreground_audio":
			shutil.rmtree(filen) # can also remove the foreground audios now
			continue

		# match filename directly in the DPDash CSV - if it doesn't match assume this means it was a second recording from the same day
		# could also happen if DPDash CSV hasn't been updated with current set of audios yet
		# but if run as part of main pipeline this should never happen, and can't imagine running this particular script outside the context of the pipeline
		cur_df = dpdash_qc[dpdash_qc["filename"]==filen]
		if cur_df.empty:
			# use error code 0 to denote it is an extra audio without a day assignment - qc not even considered
			error_rename = "0err" + filen
			os.rename(filen, error_rename)
			continue # move onto next file

		# now decide if file meets criteria or not. will only be one row in the df, grab the length and volume from that
		cur_length = float(cur_df["length(minutes)"].tolist()[0]) * 60.0 # convert from minutes to seconds to compare to the seconds cutoff input
		cur_db = float(cur_df["overall_db"].tolist()[0])
		if cur_length < float(length_cutoff):
			# use error code 1 to denote the file is too short - volume not even considered
			error_rename = "1err" + filen
			os.rename(filen, error_rename)
			continue # move onto next file
		if cur_db < float(db_cutoff):
			# use error code 2 to denote the file has audio quality issue
			error_rename = "2err" + filen
			os.rename(filen, error_rename)
			continue # move onto next file

		# if reach this point file is okay, should be moved to to_send
		# will be renamed so that the matching txt files later pulled from transcribme can be kept as is
		# get day number from DPDash CSV to do this, use 4 digit string formatting
		cur_day = str(cur_df["day"].tolist()[0])
		cur_day_format = cur_day.zfill(4)
		new_name = study + "_" + OLID + "_phone_audioTranscript_day" + cur_day_format + ".wav"
		move_path = "../to_send/" + new_name
		shutil.move(filen, move_path)

if __name__ == '__main__':
    # Map command line arguments to function arguments.
    move_audio_to_send(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
