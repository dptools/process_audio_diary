# set of functions for generating visualizations

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
plt.ioff()
import matplotlib.backends.backend_pdf
import matplotlib.cm as cm
import pandas as pd
import numpy as np
from wordcloud import WordCloud, STOPWORDS
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import string
import inflect
import re
import math

# ignore Unicode warning in inflect package
import warnings
warnings.filterwarnings("ignore", category=UnicodeWarning)

# creates a pdf where each page is a histogram for one feature's distribution from an input distribution dataframe (specified as path to a CSV)
# all columns of the input CSV will be included as a page, unless added in the optional ignore_list argument. column names will be used as title of respective pages
# if a list of bin numbers is provided, then that list will be used in column order to specify the number of bins in the histogram
# similarly for ranges, which are expected to be provided if bin numbers are
# pdf is saved to the provided output path, nothing is returned
def distribution_plots(dist_df, pdf_save_path, ignore_list=[], bins_list=None, ranges_list=None, xlabel="Value", ylabel="Counts"):
	pdf = matplotlib.backends.backend_pdf.PdfPages(pdf_save_path)
	if bins_list is not None:
		count = 0
		if ranges_list is None:
			print("please provide a min and max along with a number of bins")
			return
	for col in dist_df.columns:
		if col in ignore_list:
			continue
		cur_dist = dist_df[col]
		fig = plt.figure(1)
		if bins_list is not None:
			plt.hist(cur_dist.dropna(),bins=bins_list[count],range=ranges_list[count])
			count = count + 1
		else:
			plt.hist(cur_dist.dropna())
		plt.title(col)
		plt.xlabel(xlabel)
		plt.ylabel(ylabel)
		plt.axis('tight')
		plt.tight_layout()
		pdf.savefig(fig,bbox_inches="tight")
		plt.close()
	pdf.close()
	return

# create heatmap from input dataframe, save figure at save_path
# for coloring, should provide either absolute bounds using abs_col_bounds_list or a distribution for each feature (matching column name) with distribution_df. can also provide GB_input_dfs instead if want an RGB heatmap
def generate_horizontal_heatmap(input_df, save_path, drop_cols=[], distribution_df=None, abs_col_bounds_list=[], GB_input_dfs=[], colormap=cm.bwr, nan_color="grey", property_reorder_name=None, rel_col_std_bounds=3, cluster_bars_index=[], time_bars_offset=0, time_nums_offset=0, time_bars_index_space=7, x_axis_title="Study Day", title=None, label_features=True, features_rename=[], label_time=False, flip_y_label=False, fig_size=(30,5), x_ticks_add_offset=-0.02, y_ticks_add_offset=-0.02, cap_max_min=True,  minors_width=1, bars_width=5, nan_fill=-10000):
	for dc in drop_cols:
		input_df.drop(columns=dc,inplace=True)
	plt.rcParams["axes.grid"] = False
	colormap.set_under(color=nan_color) # to specifiy a color for NaN, values that are <= the min will be colored using this input color
	colormap.set_over(color=nan_color) # to specifiy a color for NaN, values that are >= the max will be colored using this input color
	eps=0.00000001 # small value for use in capping any data points above the max or below the min (to keep the value slightly below max/above min)
	if property_reorder_name is not None:
		# if a list of feature names is provided, use this to reorder (and/or filter) the columns in the input dataframe
		# (must match existing column names!)
		input_df = input_df[property_reorder_name]
		if len(GB_input_dfs) > 0:
			GB_input_dfs[0] = GB_input_dfs[0][property_reorder_name]
			GB_input_dfs[1] = GB_input_dfs[1][property_reorder_name]
	try:
		# drop index column from the input dataframes
		input_df=input_df.drop(['index'],axis=1)
		# these second two are only available if expecting a heatmap with independent R/G/B channels
		# (corresponding to the green and blue respectively, input_df will then be red)
		GB_input_dfs[0] = GB_input_dfs[0].drop(['index'],axis=1)
		GB_input_dfs[1] = GB_input_dfs[1].drop(['index'],axis=1)
	except: # if only a single input dataframe than above will fail, needs to be caught
		pass
	if len(GB_input_dfs) > 0: # if this is an R/G/B heatmap, fill in the NaN spots in each df with the appropriate value (on 0 to 1 scale) for that channel
		if nan_color == "grey":
			nan_color = (0.45,0.45,0.45)
		elif isinstance(nan_color, str):
			print("please input nan color as an RGB tuple. defaulting to dark grey")
			nan_color = (0.45,0.45,0.45)
		input_df.fillna(nan_color[0],inplace=True)
		GB_input_dfs[0].fillna(nan_color[1],inplace=True)
		GB_input_dfs[1].fillna(nan_color[2],inplace=True)
	else: # otherwise fill the NaNs with a value that will clearly be outside of the bounds. defaults to -10000 but if for some reason this is a viable value then will need to specify a different input for that
		input_df.fillna(nan_fill,inplace=True)
	# prepare plot
	fig,ax = plt.subplots(figsize=fig_size)
	# "normal" heatmap case, which will then either be colored relative to distribution or using provided absolute bounds
	if len(GB_input_dfs) == 0 and (distribution_df is not None or len(abs_col_bounds_list)>0):
		# loop through features
		count_labels = 0
		for label in input_df.columns:
			if distribution_df is not None: # distribution relative heatmap
				prop_dist = distribution_df[label].tolist() # please ensure corresponding columns in the distribution df and the input df are named identically
				prop_mean = np.nanmean(prop_dist) # get the mean and standard deviation for this feature
				prop_std = np.nanstd(prop_dist)
				min_bound = prop_mean - rel_col_std_bounds * prop_std # set bounds using that and the specified max/min standard deviation (defaults to 3)
				max_bound = prop_mean + rel_col_std_bounds * prop_std
			else: # otherwise it is a heatmap where explicit max/min bounds have been provided for each feature
				min_bound = abs_col_bounds_list[count_labels][0]
				max_bound = abs_col_bounds_list[count_labels][1]
			if cap_max_min: # cap any values above max or below min instead of letting them fill in as NaN
				input_df.loc[(input_df[label] != nan_fill) & (input_df[label] <= min_bound), [label]] = min_bound + eps
				input_df.loc[(input_df[label] != nan_fill) & (input_df[label] >= max_bound), [label]] = max_bound - eps
			# display current feature on the heatmap, masking rest
			ax.matshow(input_df.mask(((input_df == input_df) | input_df.isnull()) & (input_df.columns != label)).transpose(), cmap=colormap, vmin=min_bound, vmax=max_bound)
			count_labels = count_labels + 1
	elif len(GB_input_dfs) != 0: # this is an R/G/B heatmap as described above, input dfs should be taken as already containing the R, G, and B color values on 0-1 scale, so just need to be plotted appropriately
		ax.imshow(np.dstack((input_df.values.transpose(), GB_input_dfs[0].values.transpose(), GB_input_dfs[1].values.transpose())),origin='upper',interpolation='nearest',aspect='equal')
	else: # otherwise it is a heatmap with discrete colormap, so the input dataframe then contains the indices corresponding to the color in the colormap that each square should be
		ax.imshow(input_df.values.transpose(), cmap=colormap)
	# add annotations to graph - label features by default, make sure input dataframe columns are appropriate for this. 
	if label_features:
		if len(input_df.columns) == len(features_rename): # if a list of strings is provided that matches the included columns, use those to label instead
			plt.yticks(range(len(input_df.columns)), features_rename, fontsize=10) # likely to be longer, make font a bit smaller
		else:
			plt.yticks(range(len(input_df.columns)), input_df.columns, fontsize=12)
	else:
		plt.yticks([])
	if label_time: # labels columns once per vertical cluster bar
		plt.xticks(range((time_bars_index_space - time_bars_offset - 1), input_df.shape[0], time_bars_index_space), [str(y + time_nums_offset) for y in range((time_bars_index_space - time_bars_offset), input_df.shape[0]+1, time_bars_index_space)], fontsize=10)
		ax.xaxis.set_tick_params(labelbottom=True, labeltop=False)
	else:
		plt.xticks([])
	# add small grid lines while removing the ticks on the outside of the graph
	ticks1 = np.arange(0.5+x_ticks_add_offset,input_df.shape[0]-0.5) # 0.5 offset so not in middle of square
	ticks2 = np.arange(0.5+y_ticks_add_offset,len(input_df.columns)-0.5) # may require additional small offset depending on dimensions of df, see optional add_offset inputs for tweaking
	ax.set_xticks(ticks1, minor=True)
	ax.set_yticks(ticks2, minor=True)
	ax.xaxis.set_tick_params(width=0,which="both")
	ax.yaxis.set_tick_params(width=0,which="both")
	ax.grid(color='w', linestyle='-', linewidth=minors_width, which="minor")
	if flip_y_label: # put the text on the right instead of the left if this arg is set
		ax.yaxis.set_tick_params(labelright=True, labelleft=False)
	# add thicker vertical lines to denote bins of time - defaults to every 7 to specify weeks, offset allows weekdays to be consistent
	thicker = np.arange((time_bars_index_space - time_bars_offset) - 0.52,len(range(input_df.shape[0]))-0.5,time_bars_index_space)
	for n in thicker:
		plt.axvline(x=n, linewidth=bars_width, color='w')
	for n in cluster_bars_index: # add thicker horizontal lines to denote any feature clusters, if provided
		plt.axhline(y=n+0.48, linewidth=bars_width, color='w')
	if title is not None: # add title if provided
		plt.title(title, fontsize=10)
	if x_axis_title is not None: # add x title, defaults to "Study Day"
		plt.xlabel(x_axis_title, fontsize=12)
	ax.set_axisbelow(True)
	plt.savefig(save_path, bbox_inches="tight")  
	plt.close("all")

# setup defaults for wordcloud input (stop words are removed)
# currently hardcoded - will probably want to add more?
stops = set(STOPWORDS)
stops.add("Um")
stops.add("Yeah")
stops.add("Uh")

# helper function that is passed to wordcloud function for sentiment colored words
# verbose can be set to True optionally to print additional info on any issues encountered
def sentiment_color_func(sentiment_dict, punc_skip, verbose=False):
	plural_check = inflect.engine()
	exclude = set(string.punctuation)
	for punc in punc_skip:
		exclude.remove(punc)
	def sentiment_color(word,**kwargs):
		try:
			word = ''.join(ch for ch in word if ch not in exclude).lower()
		except:
			return "rgb(255,255,255)" # color white, this is a truly unreadable word
		try:
			cur_val = sentiment_dict[word] * 255
		except:
			for word_key in sentiment_dict.keys():
				try:
					if plural_check.compare(word_key, word):
						cur_val = sentiment_dict[word_key] * 255
						break
				except:
					pass
		try:
			if cur_val <= 0:
				return "rgb(" + str(abs(int(cur_val))) + ",0,0)"
			else:
				return "rgb(0," + str(abs(int(cur_val))) + ",0)"
		except:
			if verbose:
				print("failed on word: " + word)
				print("current keys: ")
				print(sentiment_dict.keys())
			return "rgb(0,0,255)" # color blue, as missing info on its sentiment but still want in wordcloud
	return sentiment_color
	
# function to generate a wordcloud for an input transcript dataframe, and save to save_path
# by default words are colored based on the sentiment of the sentence they are in, and only speech associated with the patient is included
#	(filtering on subject ID as in language feature summary functions)
# most of the other settings should be good as defaults for our use case, but one may consider tweaking the stop_words and max_font
# 	(max font is effectively a saturation point for very common words)
# nothing in the script will denote on your output whether this is patient speech only or all speech, so ensure save_path is clear on this or a title is provided
# in addition to the optional wordcloud settings, verbose can be set to True optionally to print additional info on any issues encountered
def transcript_wordcloud(transcript_df, save_path, sentiment=True, pt_only=True, title=None, min_font=6, max_font=200, freq_weight=1.0, 
						 include_punctuation=["'",'[',']',"-"], stop_words=stops, fig_size=(20,10), bg_color="white", 
						 split_char=" ", custom_word_color=sentiment_color_func, verbose=False):
	plural_check = inflect.engine() # use to count plural and singular versions of a word as the same word
	exclude = set(string.punctuation)
	for punc in include_punctuation:
		exclude.remove(punc) # punctuation that will be left in with the wordcloud
	# setup regexp that will be used for actually generating the custom wordcloud
	specials = [".", "?", "*", "$", "^", "[", "]", "+", "{", "}", "(", ")", "|"]
	regexp_start = "[\\w"
	regexp_end = "]+"
	regexp_middle = ["\\" + x if x in specials else x for x in include_punctuation]
	regexp_string = regexp_start
	for char in regexp_middle:
		regexp_string = regexp_string + char
	regexp_string = regexp_string + regexp_end
	regexp = re.compile(regexp_string)

	# filter to include only patient words when applicable
	if pt_only:
		subjects = transcript_df["subject"].tolist()
		pt_id = max(set(subjects), key = subjects.count)
		transcript_df = transcript_df[transcript_df["subject"]==pt_id]

	# use transcript to generate necessary inputs to wordcloud function
	sentences = transcript_df["text"].tolist()
	text_full = ""
	word_dict = {}
	analyser = SentimentIntensityAnalyzer() # color a word by the sentiment of the sentence it is in, when applicable
	# as sentiment coloring is the default and it is an easy computation, it is more straightforward to just include the sentiment info in the dictionary building process below
	# 	(when sentiment is off, the coloring will just not be based on this in the next section)
	for s in sentences:
		cur_sentiment = analyser.polarity_scores(s)["compound"]
		word_list = s.split(" ")
		new_break = ""
		for w in word_list:
			fine = True
			try:
				# remove any white space or related characters from string before also removing puncutation (besides exception list)
				w_filt = ''.join(ch for ch in w.strip() if ch not in exclude).lower()
			except:
				if verbose:
					print("problem with word: " + w) # sometimes weird characters cause incorrect splitting here
				continue
		
			# don't want single dashes to count as punctuation, but do remove double dashes at ends of words, as TranscribeMe tends to use them a lot to indicate pauses/stuttering
			if w_filt.endswith("--"):
				w_filt = w_filt[:-2]
			if w_filt.endswith("'s"):
				w_filt = w_filt[:-2] # also remove 's before checking sentiment, as want contractions to be fine but possessive s causes problems
			while len(w_filt) > 1 and w_filt[1] == "-": # remove single letter stuttering at beginning of word as well
				w_filt = w_filt[2:]
			if len(w_filt) <= 1:
				# single letter stutters can be skipped entirely
				continue
			
			for cur_word in word_dict.keys():
				try:
					if plural_check.compare(w_filt, cur_word):
						w_filt = cur_word
						break
				except:
					if verbose:
						print("problem with word: " + w) # wasn't able to use the current word in plural check, also indicates some weird charcter usage
					fine=False
					break
			if not fine:
				continue
			if w_filt in word_dict:
				word_dict[w_filt].append(cur_sentiment) # if a word appears multiple times it will just append the sentiment for the containing sentence on each occurence
			else:
				word_dict[w_filt] = [cur_sentiment]
			new_break = new_break + w_filt + split_char
		text_full = text_full + new_break # compiling full list of filtered text to be used in wordcloud gen
	for key in word_dict.keys(): # convert to mean sentiment
		val = word_dict[key]
		val_mean = np.nanmean(val)
		word_dict[key] = val_mean 

	# actually create wordcloud and clean up figure
	if sentiment:
		cur_color_function = custom_word_color(word_dict, include_punctuation, verbose=verbose)
		# note that if custom_word_color is provided as an optional argument, it will have to accept these (and only these) arguments in current implementation 
		wordcloud = WordCloud(regexp=regexp, width=1600, height=800, background_color=bg_color, relative_scaling = freq_weight, stopwords = stop_words, 
							  min_font_size=min_font, max_font_size=max_font, max_words=1000, color_func=cur_color_function, 
							  prefer_horizontal=0.8).generate(text_full) # relative scaling set to decide based on word frequency
	else: # just use default color assignment instead
		wordcloud = WordCloud(regexp=regexp, width=1600, height=800, background_color=bg_color, relative_scaling = freq_weight, stopwords = stop_words,
							  min_font_size=min_font, max_font_size=max_font, max_words=1000, 
							  prefer_horizontal=0.8).generate(text_full) # relative scaling set to decide based on word frequency
	plt.figure(1, figsize=fig_size)
	plt.imshow(wordcloud)
	plt.axis("off")
	if title is not None:
		plt.title(title)
	plt.savefig(save_path, bbox_inches="tight")
	plt.close("all")