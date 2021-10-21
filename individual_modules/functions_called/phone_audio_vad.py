#!/usr/bin/env python

# prevent librosa from logging a warning every time it is imported
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# need to import matplotlib a specific way for use on cluster
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
plt.ioff()

# rest of imports
import os
import numpy as np
import librosa
import librosa.display
import sys
import soundfile as sf
import pandas as pd
import datetime

# function that runs procedure specified in librosa documentation here: https://librosa.org/librosa_gallery/auto_examples/plot_vocal_separation.html#sphx-glr-auto-examples-plot-vocal-separation-py
def diary_vad(study, OLID):
	print("Running VAD on new phone audio for patient " + OLID)

	# will run VAD on all audio files currently in this patient's decrypted_files folder
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/decrypted_files")
	except:
		print("Problem with input arguments, or haven't decrypted any audio files yet for this patient") # should never reach this error if calling via pipeline
		return

	cur_files = os.listdir(".")
	if len(cur_files) == 0: # decrypted_audio folder may exist without any audio files in it when called from the feature extraction script, so add a check for that
		print("No new files for this patient, skipping") # should never reach this error if calling via pipeline
		return

	# also load metadata summary, necessary for generating appropriate filenames for permanent outputs
	try:
		audio_metadata = pd.read_csv("../" + study + "_" + OLID + "_phone_audio_ETFileMap.csv")
		study_metadata = pd.read_csv("/data/sbdp/PHOENIX/GENERAL/" + study + "/" + study + "_metadata.csv")
		patient_metadata = study_metadata[study_metadata["Subject ID"] == OLID]
		consent_date_str = patient_metadata["Consent"].tolist()[0]
		consent_date = datetime.datetime.strptime(consent_date_str,"%Y-%m-%d")
	except:
		print("No metadata for this patient yet") # should never reach this error if calling via pipeline
		return

	# loop through the list of diaries
	cur_files.sort()
	for filename in cur_files:
		if not filename.endswith(".wav"): # skip any non-audio files (and folders)
			continue

		# get metadata/setup filepaths for this diary
		diary_root = filename.split(".")[0]
		# foreground audio will only be saved temporarily within decrypted_audio
		fore_audio_out_path = "foreground_audio/" + diary_root + ".wav"
		# this will be used for pause detection, then cleared by pipeline

		if os.path.isfile(fore_audio_out_path):
			# skip the file if it was already processed before
			# this shouldn't occur if run from pipeline, but because VAD can be a bit slow to run, added this for addressing backlog with potential code interruptions
			continue 

		# spectrogram images will be saved permanently within processed/audio outputs, use appropriate naming convention for that
		# first need to look up day number corresponding to this filename
		try:
			cur_meta = audio_metadata[audio_metadata["new_filename"]==diary_root]
			# can't possibly be dupe filenames in metadata, so this is guaranteed to be one result (if any)
			cur_date = cur_meta["iso_date"].tolist()[0] 
			cur_date_format = datetime.datetime.strptime(cur_date,"%Y-%m-%d")
			cur_day = (cur_date_format - consent_date).days + 1
			image_out_path = "../vad_spectrogram_comparisons/" + study + "_" + OLID + "_phone_audioForegroundBackground_spectrogram_day" + str(cur_day).zfill(4) + ".png"
		except:
			# if can't find a filename, it means the audio was a secondary submission, won't save a spectrogram image for it
			# however will still get pause times, in line with convention for raw audio QC and OpenSMILE outputs
			image_out_path = ""
		
		# load the audio
		try:
			y, sr = librosa.load(filename)
		except:
			# ignore bad audio - will want to log this for pipeline
			print(filename + " audio is broken, skipping")
			continue 

		# compute VAD
		S_full, phase = librosa.magphase(librosa.stft(y))
		try:
			# this will fail if file is too short
			S_filter = librosa.decompose.nn_filter(S_full,aggregate=np.median,metric='cosine',width=int(librosa.time_to_frames(2, sr=sr)))
		except:
			print(filename + " is too short, skipping")
			continue
		S_filter = np.minimum(S_full, S_filter)
		margin_i, margin_v = 2, 10
		power = 2
		mask_i = librosa.util.softmask(S_filter,margin_i * (S_full - S_filter),power=power)
		mask_v = librosa.util.softmask(S_full - S_filter,margin_v * S_filter,power=power)
		S_foreground = mask_v * S_full
		S_background = mask_i * S_full

		# generate figure comparing original with foreground and background spectrograms for our core audios
		if image_out_path != "":
			plt.figure(figsize=(12, 8))
			plt.subplot(3, 1, 1)
			librosa.display.specshow(librosa.amplitude_to_db(S_full, ref=np.max),y_axis='log', sr=sr)
			plt.title('Full spectrum')
			plt.colorbar()
			plt.subplot(3, 1, 2)
			librosa.display.specshow(librosa.amplitude_to_db(S_background, ref=np.max),y_axis='log', sr=sr)
			plt.title('Background')
			plt.colorbar()
			plt.subplot(3, 1, 3)
			librosa.display.specshow(librosa.amplitude_to_db(S_foreground, ref=np.max),y_axis='log', x_axis='time', sr=sr)
			plt.title('Foreground')
			plt.colorbar()
			plt.tight_layout()
			plt.savefig(image_out_path)
			plt.close()

		# finally invert the filtered spectrogram to get back foreground audio, and save it
		foreground = librosa.core.istft(S_foreground)
		sf.write(fore_audio_out_path,foreground,sr)
		
	# once done looping through this patient's audio can simply return
	return

# function that uses saved foreground audio from the diary_vad function to detect pause times in the diary
# it uses a sliding window, with some threshold on the total summary (RMS) across all the bins in that window
# optional arguments to change the threshold, the size of the window, and the amount moved each time step can be provided
# however only the default values have been verified as producing good results on our test set
def diary_pause_detect(study, OLID, spec_thres=0.03, window_sec=0.25, slide_sec=0.05):
	print("Running pause detection on new phone audio for patient " + OLID)

	# setup for output df that will be used to save CSV of all pause times
	df_cols = ["filename","pause_number","pause_start_bin","pause_stop_bin","pause_length_seconds"]
	filenames = [] # will use Biewe formatted filenames here in keeping with convention
	pause_ids = []
	pause_starts = []
	pause_stops = []
	pause_lengths = []
	df_vals = [filenames, pause_ids, pause_starts, pause_stops, pause_lengths]
	pause_times_output_path = "/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/" + study + "_" + OLID + "_phone_audioVAD_pauseTimesOutput.csv"

	# will run pause detection on all audio files currently in this patient's decrypted_files folder
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/decrypted_files/foreground_audio")
	except:
		print("Problem with input arguments, or haven't run VAD on any decrypted audio files yet for this patient") # should never reach this error if calling via pipeline
		return

	cur_files = os.listdir(".")
	if len(cur_files) == 0: # could have an empty foreground folder even with a non-empty decrypted_files if all existing audios are corrupted
		print("No new usable files for this patient, skipping")
		return

	cur_files.sort() # go in order, although can also always sort CSV later.
	for filename in cur_files:
		if not filename.endswith(".wav"): # skip any non-audio files (and folders)
			continue

		# now load the foreground audio
		try:
			data, fs = sf.read(filename)
		except:
			# ignore bad audio - will want to log this for pipeline
			print(filename + " audio is broken, skipping")
			continue 

		# compute spectrogram
		S_full, phase = librosa.magphase(librosa.stft(data))
		num_timepoints = S_full.shape[1]

		# figure out window length - need to adjust for how many samples go into a given spectrogram bin by default (not an optional setting)
		samples_per_spec_bin = 512
		window_len = int((float(fs)/samples_per_spec_bin) * window_sec)
		slide_len = int((float(fs)/samples_per_spec_bin) * slide_sec)

		# get max across frequency bins at each time point, then do RMS over the window size
		diary_summary = []
		for i in range(0, num_timepoints, slide_len):
			window_max = []
			for j in range(i, i+window_len):
				try:
					cur_time = S_full[:,j].flatten()
				except:
					continue # at very end of file will encounter a short window, so j index won't always exist in cur_time
				cur_max = np.max(cur_time)
				window_max.append(cur_max)
			window_max = np.array(window_max)
			cur_RMS = np.sqrt(np.mean(window_max**2))
			diary_summary.append(cur_RMS)

		# find indices that don't meet threshold
		diary_summary = np.array(diary_summary)
		low_indices = np.where(diary_summary < spec_thres)[0]

		# each index will correspond to that point in range(0, num_timepoints, slide_len), convert it to actual pause indexes in the spectrogram instead
		pause_indices = []
		timepoints_list = list(range(0, num_timepoints, slide_len))
		for ind in low_indices:
			start_point = timepoints_list[ind]
			pause_indices.extend(range(start_point, start_point+window_len))
		pause_indices = list(set(pause_indices)) # remove duplicates
		pause_indices.sort() # make sure pause indices are in ascending order

		# check if there are no pauses, skip the current file if so to avoid code crashing
		if len(pause_indices) == 0:
			# no need to even print a message as that is covered by the QC function below
			continue

		# now convert pause indices to be a list of lists where each internal list is a continuous set of indices
		pause_periods = np.split(pause_indices, np.where(np.diff(pause_indices) != 1)[0]+1)

		# finally use the pause list to add this diary's pauses to the lists for the df
		cur_count = 1
		for pause in pause_periods:
			if len(pause) < 2:
				# I don't think this should be possible to reach, but just in case avoid adding any pauses that are too short to list
				continue
			filenames.append(filename)
			pause_ids.append(cur_count)
			pause_starts.append(pause[0]*samples_per_spec_bin*2) # convert back to wav file index - double sample rate for original audio vs foreground, so also need to multiply by 2
			pause_stops.append(pause[-1]*samples_per_spec_bin*2) # convert back to wav file index - double sample rate for original audio vs foreground, so also need to multiply by 2
			# note for the stop conversion it is technically cutting the identified pause slightly short because it includes only the first true index of the final spectrogram bin
			# however already did all testing with this setup, and it is quite a miniscule difference so going forward as is for the internal code. could switch in the release code
			# (not to mention that if anything the pauses were extending a bit too long, so not concerned with extending further)
			pause_lengths.append(len(pause)*samples_per_spec_bin/float(fs)) # account for spectrogram timepoint length in calculating pause time as well - can just use this file sample rate though as was calculated in this file
			# note that pause length uses the number of spectrogram bins in the pause, so it includes the full indices of the final bin which are not reflected in the stop time
			# therefore pause length is always ~23 ms longer than the file clipping for that pause will actually be - could somewhat add up over many pauses, but shouldn't matter much for our purposes
			cur_count = cur_count + 1
		
	# once done looping through this patient's diaries compile DF of pause times across them
	new_df = pd.DataFrame()
	for i in range(len(df_cols)):
		col = df_cols[i]
		vals = df_vals[i]
		new_df[col] = vals

	# then save CSV
	if os.path.isfile(pause_times_output_path): # concatenate first if necessary - this code only processes newest files, so can't just overwrite
		old_df = pd.read_csv(pause_times_output_path)
		join_csv = pd.concat([old_df, new_df])
		join_csv.reset_index(drop=True, inplace=True)
		join_csv.drop_duplicates(subset=["filename", "pause_number"],inplace=True) # drop any duplicates in case audio got decrypted a second time
		join_csv.to_csv(pause_times_output_path,index=False)
	else:
		new_df.to_csv(pause_times_output_path,index=False)

	# then this function is complete
	return

# function to use pause times for generation of various outputs for QC
# includes spectrograms of pause-only and speech-only audios for each diary, a table of pause-derived QC metrics per diary, and filtered OpenSMILE outputs for each diary
def diary_pause_qc(study, OLID):
	print("Using pause times to generate additional QC outputs from new phone audio for patient " + OLID)

	# static setting for converting from rms to db later
	ref_rms=float(2*(10**(-5)))

	# setup for output df that will contain QC features (one row per file)
	df_cols = ["OLID","filename","total_speech_minutes","number_of_pauses","max_pause_seconds","mean_pause_seconds","pause_db","pause_flatness"]
	patients = []
	filenames = [] # will use Biewe formatted filenames here in keeping with convention
	speech_lengths = []
	num_pauses = [] 
	max_pauses = []
	mean_pauses = [] 
	pause_dbs = []
	pause_flatnesses = []
	df_vals = [patients, filenames, speech_lengths, num_pauses, max_pauses, mean_pauses, pause_dbs, pause_flatnesses]
	pause_qc_output_path = "/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/" + study + "_" + OLID + "_phone_audioVAD_pauseDerivedQC_output.csv"

	# also setup for filtered OpenSMILE features. currently keeping all of the returned features, except metadata
	# metadata will be processed separately as needed, filtered CSV will be saved with comma separation (OS by default uses semi-colon)
	OS_features = ["Loudness_sma3", "alphaRatio_sma3", "hammarbergIndex_sma3", "slope0-500_sma3", "slope500-1500_sma3", "F0semitoneFrom27.5Hz_sma3nz", "jitterLocal_sma3nz", 
				   "shimmerLocaldB_sma3nz", "HNRdBACF_sma3nz", "logRelF0-H1-H2_sma3nz", "logRelF0-H1-A3_sma3nz", "F1frequency_sma3nz", "F1bandwidth_sma3nz", 
				   "F1amplitudeLogRelF0_sma3nz", "F2frequency_sma3nz", "F2amplitudeLogRelF0_sma3nz", "F3frequency_sma3nz", "F3amplitudeLogRelF0_sma3nz"]

	# check first that the patient has audio in the decrypted_files folder, necessary for QC computations
	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/decrypted_files")
	except:
		print("Problem with input arguments, or haven't decrypted any audio files yet for this patient") # should never reach this error if calling via pipeline
		return
	cur_files = os.listdir(".")
	if len(cur_files) == 0: # decrypted_audio folder may exist without any audio files in it when called from the feature extraction script, so add a check for that
		print("No new files for this patient, skipping") # should never reach this error if calling via pipeline
		return

	# now load pause times CSV and metadata summaries, also necessary
	# pause times used for everything, metadata for OpenSMILE and spectrogram image file organization
	try:
		pause_times = pd.read_csv("../" + study + "_" + OLID + "_phone_audioVAD_pauseTimesOutput.csv")
		audio_metadata = pd.read_csv("../" + study + "_" + OLID + "_phone_audio_ETFileMap.csv")
		study_metadata = pd.read_csv("/data/sbdp/PHOENIX/GENERAL/" + study + "/" + study + "_metadata.csv")
		patient_metadata = study_metadata[study_metadata["Subject ID"] == OLID]
		consent_date_str = patient_metadata["Consent"].tolist()[0]
		consent_date = datetime.datetime.strptime(consent_date_str,"%Y-%m-%d")
	except:
		print("No metadata and/or pause times for this patient yet") # should never reach this error if calling via pipeline
		return

	# can loop through decrypted files now to do actual computations
	cur_files.sort() # go in order, although can also always sort CSV later.
	for filename in cur_files:
		if not filename.endswith(".wav"): # skip any non-audio files (and folders)
			continue

		# get metadata/setup filepaths specific for this diary
		diary_root = filename.split(".")[0]
		# spectrogram images will be saved permanently within processed/audio outputs, use appropriate naming convention for that
		# saving a spectrogram of the pause audio and a spectrogram of the speech audio within the same folder as the vad comparison image
		# also saving filtered opensmile features in their own folder, again using appropriate day number
		# first need to look up day number corresponding to this filename
		try:
			cur_meta = audio_metadata[audio_metadata["new_filename"]==diary_root]
			# can't possibly be dupe filenames in metadata, so this is guaranteed to be one result (if any)
			cur_date = cur_meta["iso_date"].tolist()[0] 
			cur_date_format = datetime.datetime.strptime(cur_date,"%Y-%m-%d")
			cur_day = (cur_date_format - consent_date).days + 1
			pause_image_out_path = "../vad_spectrogram_comparisons/" + study + "_" + OLID + "_phone_audioPauseOnly_spectrogram_day" + str(cur_day).zfill(4) + ".png"
			speech_image_out_path = "../vad_spectrogram_comparisons/" + study + "_" + OLID + "_phone_audioSpeechOnly_spectrogram_day" + str(cur_day).zfill(4) + ".png"
			os_filter_out_path = "../opensmile_features_filtered/" + study + "_" + OLID + "_phone_audioSpeechOnly_OpenSMILE_day" + str(cur_day).zfill(4) + ".csv"
			if os.path.isfile(os_filter_out_path):
				# OpenSMILE filtering is the last part, so if already have this file none of the computation should need to be rerun on current diary, can skip to next
				# should never reach this condition if running through pipeline, but added to help with addressing backlog, in case code gets interrupted
				continue
		except:
			# if can't find a filename, it means the audio was a secondary submission, won't save spectrograms or opensmile outputs here
			# however will still get a row in the VAD-derived QC output CSV, in line with convention for raw audio QC and OpenSMILE outputs
			pause_image_out_path = ""
			speech_image_out_path = ""
			os_filter_out_path = ""

		# now load the audio
		try:
			data, fs = sf.read(filename)
		except:
			# ignore bad audio - will want to log this for pipeline
			print(filename + " audio is broken, skipping")
			continue 

		# data will always be mono for audio diaries
		chan1 = data.flatten()

		# get corresponding pause times for this file
		cur_pauses = pause_times[pause_times["filename"]==filename]

		# for now just skip over any file that didn't find pauses - but log this
		if cur_pauses.empty:
			# this will occur for the really short files that weren't able to have a foreground! 
			print("no pauses in file (" + filename + "), skipping")
			continue

		# once succesfully loaded it is safe to append filename
		patients.append(OLID) # append patient ID for each valid file (for each concatenation on study level)
		filenames.append(filename)

		# append the pause-related summary info to those lists
		num_pauses.append(cur_pauses.shape[0])
		max_pauses.append(np.max(cur_pauses["pause_length_seconds"].tolist()))
		mean_pauses.append(np.mean(cur_pauses["pause_length_seconds"].tolist()))

		# get the speech time as well
		raw_length_seconds = float(len(chan1))/fs # length of full file
		sum_pause_seconds = np.sum(cur_pauses["pause_length_seconds"].tolist()) # sum of calculated pause lengths
		speech_seconds = raw_length_seconds - sum_pause_seconds # difference will be speech time in seconds 
		speech_minutes = speech_seconds/float(60) # convert to minutes
		speech_lengths.append(speech_minutes)

		# then do db of pause audio
		# first will create an audio signal that is only the pause times concatenated
		pauses_only = np.array([])
		pause_starts = cur_pauses["pause_start_bin"].tolist()
		pause_stops = cur_pauses["pause_stop_bin"].tolist()
		for x in range(len(pause_starts)): # extend numpy array with the audio values from each pause
			pauses_only = np.append(pauses_only, chan1[pause_starts[x]:pause_stops[x]])
		pauses_rms = np.sqrt(np.mean(np.square(pauses_only)))
		pause_only_db = 20 * np.log10(pauses_rms/ref_rms)
		pause_dbs.append(pause_only_db)

		# finally add the mean spectral flatness of this pause-only audio
		try:
			pause_spec_flat = librosa.feature.spectral_flatness(y=pauses_only)
			pause_flatnesses.append(np.mean(pause_spec_flat))
		except:
			pause_flatnesses.append(np.nan)

		# now done with pause-derived QC calculations for this file, move on to the other outputs that need to be calculated
		if pause_image_out_path == "":
			# nothing else to do with this file if don't have a day-based filename
			continue

		# need speech only signal as well to save that spectrogram
		speech_only = np.array([])
		speech_start = [0]
		for t in pause_stops:
			speech_start.append(t)
		speech_stop = []
		for t in pause_starts:
			speech_stop.append(t)
		speech_stop.append(len(chan1)-1)
		for x in range(len(speech_start)):
			speech_only = np.append(speech_only, chan1[speech_start[x]:speech_stop[x]])

		# compute spectrogram of pause signal
		try:
			S_full_pause, phase_pause = librosa.magphase(librosa.stft(pauses_only))
		except:
			print("pause is too short to create a spectrogram for file (" + filename + "), skipping pause/speech spectrograms and OpenSMILE filtering")
			continue
		# plot it
		plt.figure()
		librosa.display.specshow(librosa.amplitude_to_db(S_full_pause, ref=np.max), y_axis='log', sr=fs)
		plt.title('Pause times spectrum')
		plt.colorbar()
		plt.tight_layout()
		plt.savefig(pause_image_out_path)
		plt.close()

		# now same for speech
		try:
			S_full_speech, phase_speech = librosa.magphase(librosa.stft(speech_only))
		except:
			# has to be pause times to get to this point, but never checking that there is speech until now
			# need to do so to prevent function from crashing without processing this patient's other files
			print("no speech in file (" + filename + "), skipping speech spectrogram and OpenSMILE filtering")
			continue
		plt.figure()
		librosa.display.specshow(librosa.amplitude_to_db(S_full_speech, ref=np.max), y_axis='log', sr=fs)
		plt.title('Speech times spectrum')
		plt.colorbar()
		plt.tight_layout()
		plt.savefig(speech_image_out_path)
		plt.close()

		# last portion is filtering OpenSMILE results
		raw_os_path = "../opensmile_feature_extraction/" + diary_root + ".csv"
		if not os.path.isfile(raw_os_path): # if relying on just the VAD module, it is possible OpenSMILE results won't exist, so handle that
			print("no OpenSMILE results yet for this file (" + diary_root + ")") # should never reach this if called from main pipeline however
			continue
		try:
			raw_os_result = pd.read_csv(raw_os_path,sep=';')
		except:
			print("OpenSMILE results for this file (" + diary_root + ") are corrupted or empty")
			continue
		os_start_times = raw_os_result["frameTime"].tolist() # list of the start times for each 10 ms bin of the audio file, provided in seconds
		os_stop_times = [t + 0.01 for t in os_start_times] # stop times will always be 10 ms later
		raw_os_result["frameStop"] = os_stop_times
		pause_start_times = [b/float(fs) for b in pause_starts] # convert the pause start (and then stop) bin numbers to times in seconds
		pause_stop_times = [b/float(fs) for b in pause_stops]
		# nan out only those OS rows that have start and stop time both fall into one of the pause bins
		for p_start,p_stop in zip(pause_start_times, pause_stop_times): # do for each pause period independently
			raw_os_result.loc[(raw_os_result["frameTime"] >= p_start) & (raw_os_result["frameStop"] <= p_stop)] = np.nan # nan out all entries in matching df slice
		# final df cleanup and save
		raw_os_result = raw_os_result[OS_features] # take only the features of interest
		raw_os_result["frameTime"] = os_start_times # add back the frame start times (want it to exist even in the NaN rows!)
		raw_os_result.to_csv(os_filter_out_path, index=False)
		
	# once done looping through this patient's diaries compile DF of pause-derived QC metrics across them and save to CSV
	new_df = pd.DataFrame()
	for i in range(len(df_cols)):
		col = df_cols[i]
		vals = df_vals[i]
		new_df[col] = vals

	# now save CSV
	if os.path.isfile(pause_qc_output_path): # concatenate first if necessary - this code only processes newest files, so can't just overwrite
		old_df = pd.read_csv(pause_qc_output_path)
		join_csv = pd.concat([old_df, new_df])
		join_csv.reset_index(drop=True, inplace=True)
		join_csv.drop_duplicates(subset=["OLID", "filename"],inplace=True) # drop any duplicates in case audio got decrypted a second time
		join_csv.to_csv(pause_qc_output_path,index=False)
	else:
		new_df.to_csv(pause_qc_output_path,index=False)

	# then this function is complete
	return

# run VAD functions when this file is called as a script on command line
if __name__ == '__main__':
    # Map command line arguments to function arguments.
    diary_vad(sys.argv[1], sys.argv[2])
    # in this case have the file run multiple functions that are defined here, as VAD, pause detection, and pause-derived QC + OS are all separate functions
    diary_pause_detect(sys.argv[1], sys.argv[2])
    # note these functions need to be run in order if importing them elsewhere
    diary_pause_qc(sys.argv[1], sys.argv[2])
