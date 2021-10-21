#!/usr/bin/env python

# frequently getting deprecated function warning for smart_open.open (UserWarning) and empty list related warnings from short sentences (RuntimeWarning)
# just supress for now to cleanup logs, can revisit how to handle this for generalized release 
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# path to model is currently hardcoded but this will definitely need to be updated!
# the model will be too big to include in GitLab but will also want to give instructions on downloading
word2vec_model_path = '/data/sbdp/NLP_models/GoogleNews-vectors-negative300.bin' 
# you may also consider using a different model or training your own, and point to it here. 
# as long as the produced .bin will work with the gensim.models package no changes to the below code would be necessary, besides ensuring dimensionality matches:
word2vec_dimensions = 300 # Google's model reduces word rep to 300 dimensions!
# the current model is Google's pretrained word2vec, big file- other corpuses I looked at through nltk (albeit awhile ago and briefly) didn't give very good results

# note that every time a function from this file is imported the word2vec model is reloaded, meaning it currently reloads it for each patient that has transcripts to process
# this is an inefficiency that should be addressed in a future version of the code (perhaps before generalized release)

import pandas as pd
import numpy as np
import os
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import curses 
from curses.ascii import isdigit 
import nltk
from nltk.corpus import cmudict
from gensim.models import Word2Vec, KeyedVectors
import string

# setup word2vec
g = KeyedVectors.load_word2vec_format(word2vec_model_path, binary=True) # this can be slow to load, so that will be upfront to importing this file

# setup syllables dictionary
d = cmudict.dict() 
exclude = set(string.punctuation) # and ensure punctuation does not interfere with lookup

# setup for sentiment analysis
analyser = SentimentIntensityAnalyzer()

# specify column names for the current summary stat measures
current_measures = ["syllables-count", "speaking-rate", "word-uncommonness-mean", "word-uncommonness-stdev", "sequential-coherence-mean", 
					"sequential-coherence-stdev", "pairwise-coherence-mean", "pairwise-coherence-stdev", "coherence-with-prev-sentence",
					"sentence-sentiment"] 


# Functions for speaking rate/syllable counts
# -------------------------------------------

# helper function that takes in a word and returns number of syllables
def nsyl(word, syl_dict=d): 
	try: 
		syllables_lookup = [len(list(y for y in x if isdigit(str(y)[-1]))) for x in syl_dict[word.lower()]]
		return syllables_lookup[0] # cmu_dict will give multiple answers if dif pronunciations, but just take 1st (most common)
	except:
		# if word is not in the syllable dictionary, use this estimation method instead
		# (referred from stackoverflow.com/questions/14541303/count-the-number-of-syllables-in-a-word)
		count = 0
		vowels = 'aeiouy'
		word = word.lower()
		try:
			if word[0] in vowels:
				count +=1
			for index in range(1,len(word)):
				if word[index] in vowels and word[index-1] not in vowels:
					count +=1
			if word.endswith('e'):
				count -= 1
			if word.endswith('le'):
				count+=1
			if count == 0:
				count +=1
			return count
		except:
			return 0

# function to count the number of syllables for each sentence in an input transcript
def count_number_syllables(transcript_df, syl_method=nsyl, punc_skip=exclude, inplace=True):
	sentences = [t[0:-1] for t in transcript_df["text"].tolist()]
	syllables_count = []
	for s in sentences:
		words = s.split(" ")
		cur_count = 0
		for w in words:
			# remove punctuation to avoid key error
			w_filt = ''.join(ch for ch in w if ch not in punc_skip)
			cur_count = cur_count + syl_method(w_filt)
		syllables_count.append(cur_count)

	# prep df for function output
	if inplace: # just add to the transcript dataframe, return nothing
		transcript_df["syllables-count"] = syllables_count
		return None
	else: # add to a new copy of the transcript df and return that
		new_df = transcript_df.copy()
		new_df["syllables-count"] = syllables_count
		return new_df

# function to calculate speaking rate from a transcript with syllable count column added (i.e. run count_number_syllables first)
# optionally a time for the total length of the file can be input- otherwise the speaking rate for the last sentence will necessarily be marked as NaN
# 	(this timestamp should be given as a float, in seconds)
def calculate_speaking_rate(transcript_df_with_syls, audio_length=None, inplace=True):
	# note this assumes a particular timestamp format- but this should be handled via padding in the transcript_csv_conversion script if other formats appear
	# times are expected to go out to only 3 decimal places (millisecond level "accuracy", although TranscribeMe is certainly not careful to that precision level)
	
	# get sentence lengths in time
	speech_times_raw = transcript_df_with_syls["timefromstart"].tolist()
	# prior version was assuming there would be an hour placeholder as well, but for newer phone diaries there never is, so fix that!
	try:
		speech_times = [float(s[0:2])*60 + float(s[3:-1]) for s in speech_times_raw]
	except:
		# if there is an hour placeholder will hit this except block, can go from there
		speech_times = [float(s[0:2])*60*60 + float(s[3:5])*60 + float(s[6:-1]) for s in speech_times_raw]
	speech_differences = [speech_times[j] - speech_times[i] for i,j in zip(range(len(speech_times)-1), range(1,len(speech_times)))]
	if audio_length is not None:
		speech_differences.append(audio_length - speech_times[-1])
	else:
		speech_differences.append(np.nan)

	# get speaking rate
	syllables_number = transcript_df_with_syls["syllables-count"].tolist()
	speaking_rate = [float(x)/y if y > 0 else np.nan for x,y in zip(syllables_number, speech_differences)]

	# prep df for function output
	if inplace: # just add to the transcript dataframe, return nothing
		transcript_df_with_syls["speaking-rate"] = speaking_rate
		return None
	else: # add to a new copy of the transcript df and return that
		new_df = transcript_df_with_syls.copy()
		new_df["speaking-rate"] = speaking_rate
		return new_df


# Functions for word2vec calculated metrics
# -----------------------------------------

# helper function to get coherence and uncommonness metrics for an input sentence from the word2vec model, as well as a vector rep for the sentence
# this will return mean and standard deviation within the sentence of: 
#	word magnitude (uncommonness)
#	angle between sequential words (sequential coherence)
#	angle between all word pairs (pairwise coherence)
# it is returned as a dictionary with the following keys: avg-mag, std-mag, avg-seq-coh, std-seq-coh, avg-pw-coh, std-pw-coh.
# additionally returned as a second variable is a numpy array corresponding to the mean of each valid word vector in the sentence
#	this can later be used to estimate coherence between sentences in an entire transcript
# besides optional arguments to update the settings, verbose can also be set to True optionally to print additional info on any issues encountered
def sentence_wordtovec_metrics(sentence, model=g, model_dim=word2vec_dimensions, punc_skip=exclude - set("'"), verbose=False):
	word_vecs = np.empty((0,model_dim), dtype='float64')
	words = sentence.split(" ")
	for w in words:
		# remove punctuation to avoid key error- but contractions/possessive okay
		w_filt = ''.join(ch for ch in w if ch not in punc_skip)
		w_filt = w_filt.lower() # lower case
		try:
			cur_vec = np.array(model[w_filt],ndmin=2,dtype='float64')
			word_vecs = np.append(word_vecs, cur_vec, axis = 0)
		except:
			# given word not in google dictionary, rest of sentence will proceed to be processed
			# if this becomes a common problem, can start more closely tracking when it occurs and trying to account for it in below calculations
			if verbose:
				print(w + " not in current model, skipping this word")
	
	if word_vecs.shape[0] == 0:
		if verbose:
			print("input sentence:")
			print(sentence)
			print("has no valid words, returning None for both variables")
		return None, None

	if word_vecs.shape[0] == 1:
		if verbose:
			print("input sentence:")
			print(sentence)
			print("has only one valid word, dictionary will instead contain just a single magnitude key (value given under avg-mag)")
		return {'avg-mag': np.linalg.norm(word_vecs)}, np.mean(word_vecs, axis=0) # nothing to mean over for vec but will ensure dimensionality remains consistent

	# loop through generated word vectors to calculate metrics
	sequential_coherences = []
	pairwise_coherences = []
	word_magnitudes = []
	for v in range(word_vecs.shape[0]-1):
		# get current vector and calculate its magnitude
		vec1 = word_vecs[v,:]
		word_magnitudes.append(np.linalg.norm(vec1))
		
		# get coherence with next vector available
		vec2 = word_vecs[v+1,:]
		cos = np.dot(vec2, vec1)/np.linalg.norm(vec2)/np.linalg.norm(vec1) # cosine of the angle
		ang = np.arccos(np.clip(cos, -1, 1)) # the angle
		# append to sequential and pairwise lists
		sequential_coherences.append(ang)
		pairwise_coherences.append(ang)

		# now for pairwise get coherence with other vectors in sentence (not repeating any matches as the function is commutative)
		for u in range(v+2, word_vecs.shape[0]):
			next_vec = word_vecs[u,:]
			cos = np.dot(next_vec, vec1)/np.linalg.norm(next_vec)/np.linalg.norm(vec1) # cosine of the angle
			ang = np.arccos(np.clip(cos, -1, 1)) # the angle
			pairwise_coherences.append(ang)

	# get magnitude of the last vector as that would not be covered in the loop (note range is exclusive of the last number)
	final_vec = word_vecs[word_vecs.shape[0]-1,:] 
	word_magnitudes.append(np.linalg.norm(final_vec))
	
	# generate dictionary of calculated values
	metrics_dict = {"avg-mag": np.nanmean(word_magnitudes),
					"std-mag": np.nanstd(word_magnitudes),
					"avg-seq-coh": np.nanmean(sequential_coherences),
					"std-seq-coh": np.nanstd(sequential_coherences),
					"avg-pw-coh": np.nanmean(pairwise_coherences),
					"std-pw-coh": np.nanstd(pairwise_coherences)}

	# get represetative vector for the sentence by taking mean of word vectors
	sen_vec = np.mean(word_vecs, axis=0)

	return metrics_dict, sen_vec

# function to add columns to transcript dataframe corresponding to the six metrics computed in sentence_wordtovec_metrics
# it also adds a column that reports coherence between a row's sentence vector and the sentence vector corresponding to the previous row
#	(this does not incorporate any notion of subject identity, so it will populate this metric whether the next sentence is the same speaker or not)
#	(however, the subject column is sort of used towards this end in the later transcript summary stat functions)
def calculate_wordtovec_transcript(transcript_df, calc_func=sentence_wordtovec_metrics, inplace=True):
	# init vectors for new columns- first 6 matching to above function, plus the sentence-level coherence metric desribed here
	mean_mags = []
	std_mags = []
	mean_cohs = []
	std_cohs = []
	mean_pw_cohs = []
	std_pw_cohs = []
	sen_cohs = []

	# use given helper function to loop through sentences and construct column lists
	sentences = [t[0:-1] for t in transcript_df["text"].tolist()]
	prev_sen_vector = None
	for s in sentences:
		metrics, vector = calc_func(s)

		if metrics is None:
			mean_mags.append(np.nan)
			std_mags.append(np.nan)
			mean_cohs.append(np.nan)
			std_cohs.append(np.nan)
			mean_pw_cohs.append(np.nan)
			std_pw_cohs.append(np.nan)
			sen_cohs.append(np.nan)
			continue # not a valid sentence - but still need to match length of df, so append NaNs

		# reading values from dictionary
		# cap each metric at 5 sig figs for initial readability
		mean_mags.append(round(float(metrics["avg-mag"]), 5)) # will have this uncommonness value even if only 1 word in sentence
		try: # rest of values will only be available when there are multiple words
			std_mags.append(round(float(metrics["std-mag"]), 5))
			mean_cohs.append(round(float(metrics["avg-seq-coh"]), 5))
			std_cohs.append(round(float(metrics["std-seq-coh"]), 5))
			mean_pw_cohs.append(round(float(metrics["avg-pw-coh"]), 5))
			std_pw_cohs.append(round(float(metrics["std-pw-coh"]), 5))
		except: # if not available then fill with nan
			std_mags.append(np.nan)
			mean_cohs.append(np.nan)
			std_cohs.append(np.nan)
			mean_pw_cohs.append(np.nan)
			std_pw_cohs.append(np.nan)

		# calculating coherence for the sentence vectors
		if prev_sen_vector is None: # for first row this will be NaN
			sen_cohs.append(np.nan)
		else:
			cos = np.dot(vector, prev_sen_vector)/np.linalg.norm(vector)/np.linalg.norm(prev_sen_vector) # cosine of the angle
			ang = np.arccos(np.clip(cos, -1, 1))
			sen_cohs.append(round(float(ang), 5))
		
		# ensure previous vector value is reset
		prev_sen_vector = np.copy(vector)

	# prep df for function return
	if inplace: # just add to the transcript dataframe, return nothing
		transcript_df["word-uncommonness-mean"] = mean_mags
		transcript_df["word-uncommonness-stdev"] = std_mags
		transcript_df["sequential-coherence-mean"] = mean_cohs
		transcript_df["sequential-coherence-stdev"] = std_cohs
		transcript_df["pairwise-coherence-mean"] = mean_pw_cohs
		transcript_df["pairwise-coherence-stdev"] = std_pw_cohs
		transcript_df["coherence-with-prev-sentence"] = sen_cohs
		return None
	else: # add to a new copy of the transcript df and return that
		new_df = transcript_df.copy()
		new_df["word-uncommonness-mean"] = mean_mags
		new_df["word-uncommonness-stdev"] = std_mags
		new_df["sequential-coherence-mean"] = mean_cohs
		new_df["sequential-coherence-stdev"] = std_cohs
		new_df["pairwise-coherence-mean"] = mean_pw_cohs
		new_df["pairwise-coherence-stdev"] = std_pw_cohs
		new_df["coherence-with-prev-sentence"] = sen_cohs
		return new_df


# Functions for sentiment analysis
# --------------------------------

# function that adds sentence sentiment score to the input transcript dataframe
def calculate_sentiment(transcript_df, sentiment_model=analyser, inplace=True):
	# vader sentiment analyzer will return sentiment score for any input sentence (1.0 to -1.0), so simple loop through and plugin here
	sentence_sentiments = []
	sentences = [t[0:-1] for t in transcript_df["text"].tolist()]
	for s in sentences:
		cur_sentiment = sentiment_model.polarity_scores(s)["compound"]
		sentence_sentiments.append(cur_sentiment)

	# prep df for function return
	if inplace: # just add to the transcript dataframe, return nothing
		transcript_df["sentence-sentiment"] = sentence_sentiments
		return None
	else: # add to a new copy of the transcript df and return that
		new_df = transcript_df.copy()
		new_df["sentence-sentiment"] = sentence_sentiments
		return new_df


# Functions for counting keywords in transcript
# ---------------------------------------------

# function to count the number of occurences per sentence of each word in the keywords_list input
# by default a row for each keyword will be added to the input transcript
# this does not separate out punctuation, deal with plurals, etc.
#	(by default, spaces are added around each keyword by the code to ensure it finds only true instances of that word)
#	(making the optional argument substrings=True will not pad the word with spaces, instead detecting any words that contain the word)
# to count multiple word forms, input them to this function but set optional combine argument to True
#	(this will result in a single column titled using the first keyword in the list)
# it is case insensitive
# phrases can also be input if desired
def count_keywords(transcript_df, keywords_list, inplace=True, combine=False, substrings=False):
	# prep text
	if substrings:
		true_keywords = [x.lower() for x in keywords_list] # case insensitive
	else:
		true_keywords = [" " + x.lower() + " " for x in keywords_list] # pad with spaces so substrings are not recognized accidentally
	sentences = [t[0:-1].lower() for t in transcript_df["text"].tolist()] # also ensure it is case insensitive

	if not combine: # default case where each input is treated separately
		# gather counts
		per_sentence_counters = [[] for x in keywords_list]
		columns_to_add = ["keyword-count-" + x for x in keywords_list]
		for s in sentences:
			for k in range(len(keywords_list)):
				per_sentence_counters[k].append(s.count(true_keywords[k]))

		# prep df for function return
		if inplace: # just add to the transcript dataframe, return nothing
			for col in range(len(columns_to_add)):
				cur_name = columns_to_add[col]
				cur_list = per_sentence_counters[col]
				transcript_df[cur_name] = cur_list
			return None
		else: # add to a new copy of the transcript df and return that
			new_df = transcript_df.copy()
			new_df["sentence-sentiment"] = sentence_sentiments
			return new_df
	else: # generate single column
		# summing counts
		per_sentence_counter = []
		column_title = "keyword-count-combined-" + keywords_list[0]
		for s in sentences:
			cur_count = 0
			for k in true_keywords:
				cur_count = cur_count + s.count(k)
			per_sentence_counter.append(cur_count)

		# prep df for function return
		if inplace:
			transcript_df[column_title] = per_sentence_counter
			return None
		else:
			new_df = transcript_df.copy()
			new_df[column_title] = per_sentence_counter
			return new_df


# Functions for summarizing stats across transcripts
# --------------------------------------------------

# function to create a dataframe with summary values for each transcript in an input list of transcript dataframes
# summarizes over sentences using mean, standard deviation, max, and min for each feature in each transcript
#	"_file-[stat]" will be appended to each column name to denote
# 	this means the total number of columns will be 5 * metric_columns, + 1 for the filename identifier column
# 	the total number of rows will equal the number of provided transcripts
# the resulting df will be returned, and if a save_path is provided it will also be written.
# the summary values will be based upon the sentence-level summary metrics provided in metric_columns
# with keyword_include on, the function will also take all columns that begin with "keyword-count" and produce a corresponding column containing the sum of counts in a transcript
# 	(it will also produce a 0/1 column indicating if that word appears in the transcript or not. the two columns will append _file-sum and _file-appears, respectively)
def summarize_transcript_stats(transcript_dfs_list, metric_columns=current_measures, keyword_include=True, save_path=None):
	# prep df columns
	all_stat_columns = []
	for m in metric_columns:
		all_stat_columns.append(m + "_file-mean")
		all_stat_columns.append(m + "_file-stdev")
		all_stat_columns.append(m + "_file-max")
		all_stat_columns.append(m + "_file-min")
	stat_values = [[] for x in range(len(all_stat_columns))] # list of lists contains eventual df columns
	if keyword_include: # add keyword df columns when applicable
		keyword_columns_in = []
		keyword_columns_out = []
		for col in transcript_dfs_list[0].columns:
			if col.startswith("keyword-count"):
				keyword_columns_in.append(col)
				keyword_columns_out.append(col + "_file-sum")
				keyword_columns_out.append(col + "_file-appears")
		keyword_values = [[] for x in range(len(keyword_columns_out))]
	filenames = []
	
	# loop through transcripts
	for transcript in transcript_dfs_list:
		filenames.append(transcript["filename"].tolist()[0])

		# go through the provided sentence metrics to get the 4 different summary values
		for c in range(len(metric_columns)):
			cur_vals = transcript[metric_columns[c]].tolist()
			stat_values[c*4].append(round(np.nanmean(cur_vals),5))
			stat_values[c*4 + 1].append(round(np.nanstd(cur_vals),5))
			stat_values[c*4 + 2].append(round(np.nanmax(cur_vals),5))
			stat_values[c*4 + 3].append(round(np.nanmin(cur_vals),5))

		# go through the keyword metrics when applicable to get the relevant summary values
		if keyword_include:
			for k in range(len(keyword_columns_in)):
				cur_counts = transcript[keyword_columns_in[k]].tolist()
				cur_sum = np.nansum(cur_counts)
				keyword_values[k*2].append(cur_sum)
				if cur_sum > 0:
					cur_appear = 1
				else:
					cur_appear = 0
				keyword_values[k*2 + 1].append(cur_appear)

	# generate df
	final_summary = pd.DataFrame()
	for prop in range(len(all_stat_columns)):
		final_summary[all_stat_columns[prop]] = stat_values[prop]
	if keyword_include:
		for prop in range(len(keyword_columns_out)):
			final_summary[keyword_columns_out[prop]] = keyword_values[prop]
	final_summary["filename"] = filenames

	# save and return
	if save_path is not None:
		final_summary.to_csv(save_path, index=False)
	return final_summary

