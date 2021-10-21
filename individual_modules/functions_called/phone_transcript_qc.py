#!/usr/bin/env python

# Script to generate summary values for each available transcript csv
# Output will primarily serve as QC for transcription process, to be used in conjunction with audio QC
# Feature extraction and visualization occur in downstream scripts.

# A few efficiency improvements I could make noted below.

import os
import pandas as pd 
import numpy as np 
import sys

def diary_transcript_qc(study, OLID):
	print("Running Transcript QC for " + OLID) # if calling from bash module, this will only print for patients that have phone transcript CSVs (whether new or not)

	# specify column headers that will be used for every CSV
	headers=["OLID","transcript_name","num_subjects","num_sentences","num_words","min_words_in_sen","max_words_in_sen","num_inaudible","num_questionable","num_redacted","num_nonverbal_edits","num_verbal_edits","num_restarts","num_repeats","num_commas","num_dashes","final_timestamp","min_timestamp_space","max_timestamp_space","min_timestamp_space_per_word","max_timestamp_space_per_word","min_absolute_timestamp_space_per_word","S1_sentence_count"]

	# initialize lists for df - in same order as header columns
	patients=[]
	fnames=[]
	nsubjs=[]
	nsens=[]
	nwords=[]
	minwordsper=[]
	maxwordsper=[]
	ninaud=[]
	nquest=[]
	nredact=[]
	nuhum=[]
	nfiller = []
	nrestarts = []
	nrepeats = []
	ncommas=[]
	ndashes = []
	fintimes=[]
	minspaces=[]
	maxspaces=[]
	minspacesweighted=[]
	maxspacesweighted=[]
	minspacesweightedabs=[]
	nS1=[] # should mainly only see 1 subject for these

	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/transcripts/csv")
	except: # this should only be possible to reach if the function was called directly, and not via the bash module.
		print("No transcripts to process for input study/OLID - if this is unexpected, please ensure transcripts have been pulled and CSV formatting script has been run")
		return

	cur_files = os.listdir(".")
	cur_files.sort() # go in order, although can also always sort CSV later.
	for filename in cur_files:
		if not filename.endswith(".csv"): # skip any non-csv files (and folders) in case they exist
			continue
		# load in CSV and clear any rows where there is a missing value (should always be a subject, timestamp, and text; code is written so metadata will always be filled so it should only filter out problems on part of transcript)
		cur_trans = pd.read_csv(filename)
		cur_trans = cur_trans[["subject", "timefromstart", "text"]]
		cur_trans.dropna(inplace=True)
		# should add some check to ensure transcript CSV loads okay and has expected columns? Either that or at least have it fail more gracefully for a particular transcript below

		# separate out sentences and ensure transcript is not empty
		cur_sentences = [x.lower() for x in cur_trans["text"].tolist()] # case shouldn't matter
		if len(cur_sentences) == 0:
			print("Current transcript is empty, skipping this file (" + filename + ")")
			continue

		# add metadata info to lists for CSV
		patients.append(OLID)
		fnames.append(filename)

		# get total number of subjects, sentences, and words, as well as the sentence with least and most words
		nsubjs.append(len(set(cur_trans["subject"].tolist())))
		nsens.append(len(cur_sentences))
		words_per = [len(x.split(" ")) for x in cur_sentences]
		nwords.append(np.nansum(words_per))
		minwordsper.append(np.nanmin(words_per))
		maxwordsper.append(np.nanmax(words_per))

		# count number of [inaudible] occurences, number of [*?] occurences (where * is any guess at what was said), and number of [redacted] occurences
		# now counting disfluencies too 
		# includes occurences of non-verbal edits (uh/um) and verbal edits (like/you know/I mean, followed by a comma specifically)
		# as well as occurences of repeats (look for repeated words and also repeated characters)
		# and occurences of restarts (generally encoded by the --, although this won't be perfect)
		# also count numbers of single dashes and commas as additional QC on these disfluency metrics
		inaud_per = [x.count("[inaudible]") for x in cur_sentences]
		quest_per = [x.count("?]") for x in cur_sentences] # assume bracket should never follow a ? unless the entire word is bracketed in
		redact_per = [x.count("[redacted]") for x in cur_sentences]
		um_per = [x.count("um") for x in cur_sentences]
		uh_per = [x.count("uh") for x in cur_sentences]
		like_per = [x.count("like,") for x in cur_sentences]
		know_per = [x.count("you know,") for x in cur_sentences]
		mean_per = [x.count("i mean,") for x in cur_sentences]
		ddash_per = [x.count("--") for x in cur_sentences] # estimate of restarts, could also be long mid-sentence pause
		# for repetitions, looking for either repetition of characters after a single dash (no spaces)
		# or repetition of actual words in a sentence (splitting on space but also counting repetition if comma appears as the punctuation on either of the two words)
		dash_repetition = [np.nansum([1 if len(y.split("-")) > 1 and len(y.split("-")[0]) <= len(y.split("-")[1]) and y.split("-")[0]==y.split("-")[1][0:len(y.split("-")[0])] else 0 for y in x.split(" ")]) for x in cur_sentences]
		word_repetition = [np.nansum([1 if x.split(" ")[y-1].replace(",","")==x.split(" ")[y].replace(",","") else 0 for y in range(1,len(x.split(" ")))]) for x in cur_sentences]
		commas_per = [x.count(",") for x in cur_sentences]
		dash_per = [x.count("-") for x in cur_sentences]
		ninaud.append(np.nansum(inaud_per))
		nquest.append(np.nansum(quest_per))
		nredact.append(np.nansum(redact_per))
		nuhum.append(np.nansum(um_per) + np.nansum(uh_per))
		nfiller.append(np.nansum(like_per) + np.nansum(know_per) + np.nansum(mean_per))
		nrestarts.append(np.nansum(ddash_per))
		nrepeats.append(np.nansum(dash_repetition) + np.nansum(word_repetition))
		ncommas.append(np.nansum(commas_per))
		ndashes.append(np.nansum(dash_per))

		# get last timestamp - note this will be for the time *before* the last sentence
		cur_times = cur_trans["timefromstart"].tolist()
		# convert all timestamps to a float value indicating number of minutes (all time values will be in terms of minutes in this QC output)
		try:
			cur_minutes = [float(int(x.split(":")[0]))*60.0 + float(int(x.split(":")[1])) + float(x.split(":")[2])/60.0 for x in cur_times]
		except:
			cur_minutes = [float(int(x.split(":")[0])) + float(x.split(":")[1])/60.0 for x in cur_times] # format sometimes will not include an hours time, so need to catch that
		fintimes.append(cur_minutes[-1])

		# get min and max space between timestamps, and then as a function of number of words in the intermediate sentence
		# also added in the minimum of the absolute values of the weighted spaces, because the negative time one word sentences were often popping up in both existing min columns, kind of defeating the purpose 
		# (the number of negatives that seemed to show up with DPBPD test run are concerning/should be addressed)
		differences_list = [j - i for i, j in zip(cur_minutes[: -1], cur_minutes[1 :])]
		if len(differences_list) == 0:
			# current transcript is of minimal length (1 sentence), so no valid timestamp differences, append nan
			minspaces.append(np.nan)
			maxspaces.append(np.nan)
			minspacesweighted.append(np.nan)
			maxspacesweighted.append(np.nan)
			minspacesweightedabs.append(np.nan)
		else:
			minspaces.append(np.nanmin(differences_list))
			maxspaces.append(np.nanmax(differences_list))
			weighted_list = [j/float(i) for i, j in zip(words_per[: -1], differences_list)]
			minspacesweighted.append(np.nanmin(weighted_list))
			maxspacesweighted.append(np.nanmax(weighted_list))
			weighted_list_no_neg = [abs(x) for x in weighted_list]
			minspacesweightedabs.append(np.nanmin(weighted_list_no_neg))
			# may want to round these floats in the future for easier readability?

		# get number of sentences assigned to main subject ID, should generally match the number of words line, only won't if number of subjects >1
		S1_sentences = cur_trans[cur_trans["subject"]=="S1"]["text"].tolist()
		nS1.append(len(S1_sentences))

	if len(fnames) == 0: # transcripts/csv folder could exist without there being anything in it - but should only be able to reach this if function called directly rather than through pipeline/bash module
		print ("No available transcript CSVs for input OLID")
		return
		
	os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio")

	# construct current CSV
	values = [patients, fnames, nsubjs, nsens, nwords, minwordsper, maxwordsper, ninaud, nquest, nredact, nuhum, nfiller, nrestarts, nrepeats, ncommas, ndashes, fintimes, minspaces, maxspaces, minspacesweighted, maxspacesweighted, minspacesweightedabs, nS1]
	new_csv = pd.DataFrame()
	for i in range(len(headers)):
		h = headers[i]
		vals = values[i]
		new_csv[h] = vals

	# save current CSV - overwrite any existing one for this patient
	output_path = study+"_"+OLID+"_phone_audio_transcriptQC_output.csv"
	# running through all transcripts every time for now, as much faster to run than audio QC and don't have the decrypted files concern either. 
	# may revisit making this more efficient in the future though
	new_csv.to_csv(output_path,index=False)
			
if __name__ == '__main__':
    # Map command line arguments to function arguments.
    diary_transcript_qc(sys.argv[1], sys.argv[2])
