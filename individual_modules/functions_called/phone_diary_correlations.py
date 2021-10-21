#!/usr/bin/env python

import os
import pandas as pd
import sys
from numpy import inf
from correlation_functions import calculate_correlation_matrix, plot_correlation_matrix, create_dendrogram

# ignore "The symmetric non-negative hollow observation matrix looks suspiciously like an uncondensed distance matrix"
from scipy.cluster.hierarchy import ClusterWarning
from warnings import simplefilter
simplefilter("ignore", ClusterWarning)

def study_correlations(study):
	# start with settings info:

	# study distribution paths
	audio_qc_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioQC-distribution.csv"
	transcript_qc_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptQC-distribution.csv"
	OS_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioOpenSMILESummary-distribution.csv"
	OS_filtered_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioFilteredOpenSMILESummary-distribution.csv"
	transcript_nlp_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptNLP-distribution.csv"
	combined_dist_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneDiaryKeyFeatures-distribution.csv"

	# out paths
	audio_qc_corr_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioQC-correlationMatrix.png"
	transcript_qc_corr_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptQC-correlationMatrix.png"
	OS_corr_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioOpenSMILESummary-correlationMatrix.png"
	OS_filtered_corr_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneAudioFilteredOpenSMILESummary-correlationMatrix.png"
	transcript_nlp_corr_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneTranscriptNLP-correlationMatrix.png"
	combined_corr_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneDiaryKeyFeatures-correlationMatrix.png"
	# for key features also doing dendrogram
	combined_dend_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneDiaryKeyFeatures-clustersDendrogram.png"
	# and clustered matrix
	combined_corr_cluster_path = "/data/sbdp/Distributions/phone/voiceRecording/" + study + "-phoneDiaryKeyFeatures-correlationMatrixClustered.png"

	# columns to drop from each distribution before proceeding
	diary_ID_feats = ["day","patient","ET_hour_int_formatted"]

	# now load in DFs and calculate correlation matrix when available:

	# start with audio QC
	try:
		audio_qc_dist = pd.read_csv(audio_qc_dist_path).drop(labels=diary_ID_feats,axis=1)
		# also remove any -infinity values popping up in the decibel field: okay to replace with 0
		audio_qc_dist.replace(to_replace=-inf, value=0, inplace=True)
		audio_qc_r, audio_qc_p = calculate_correlation_matrix(audio_qc_dist)
		# offset values based on visual inspection of resulting matrix - depends a bit on size
		plot_correlation_matrix(audio_qc_r, audio_qc_dist.columns, audio_qc_corr_path, x_offset=0.01, y_offset=0.01)
	except:
		print("No audio QC data yet to correlate, continuing") 

	# then transcript QC
	try:
		transcript_qc_dist = pd.read_csv(transcript_qc_dist_path).drop(labels=diary_ID_feats,axis=1)
		transcript_qc_r, transcript_qc_p = calculate_correlation_matrix(transcript_qc_dist)
		# offset values based on visual inspection of resulting matrix - depends a bit on size
		plot_correlation_matrix(transcript_qc_r, transcript_qc_dist.columns, transcript_qc_corr_path, x_offset=0.01, y_offset=0.01)
	except:
		print("No transcript QC data yet to correlate, continuing") 

	# then OS raw
	try:
		OS_dist = pd.read_csv(OS_dist_path).drop(labels=diary_ID_feats,axis=1)
		OS_r, OS_p = calculate_correlation_matrix(OS_dist)
		# offset values based on visual inspection of resulting matrix - depends a bit on size
		plot_correlation_matrix(OS_r, OS_dist.columns, OS_corr_path, x_offset=0.0, y_offset=0.0)
	except:
		print("No OpenSMILE data yet to correlate, continuing") 

	# and next OS filtered
	try:
		OS_filtered_dist = pd.read_csv(OS_filtered_dist_path).drop(labels=diary_ID_feats,axis=1)
		OS_filtered_r, OS_filtered_p = calculate_correlation_matrix(OS_filtered_dist)
		# offset values based on visual inspection of resulting matrix - depends a bit on size
		plot_correlation_matrix(OS_filtered_r, OS_filtered_dist.columns, OS_filtered_corr_path, x_offset=0.0, y_offset=0.0)
	except:
		print("No pause-removed OpenSMILE data yet to correlate, continuing") 

	# finally do NLP for last of full distribution sets
	try:
		transcript_nlp_dist = pd.read_csv(transcript_nlp_dist_path).drop(labels=diary_ID_feats,axis=1)
		nlp_r, nlp_p = calculate_correlation_matrix(transcript_nlp_dist)
		# offset values based on visual inspection of resulting matrix - depends a bit on size
		plot_correlation_matrix(nlp_r, transcript_nlp_dist.columns, transcript_nlp_corr_path, y_offset=0.0)
	except:
		print("No transcript NLP data yet to correlate, continuing") 

	# then do a correlation of just the key features
	try:
		key_feat_dist = pd.read_csv(combined_dist_path).drop(labels=diary_ID_feats,axis=1)
		key_r, key_p = calculate_correlation_matrix(key_feat_dist)
		# offset values based on visual inspection of resulting matrix - depends a bit on size
		plot_correlation_matrix(key_r, key_feat_dist.columns, combined_corr_path, x_offset=-0.01, y_offset=-0.01)
	except:
		print("No key features distribution yet to correlate, continuing")
		# rest of code is just focused on the key features, so can return if none available
		return 

	# for the key features specifically also do a dendrogram
	create_dendrogram(key_r, key_feat_dist.columns, combined_dend_path)

	# and create a second correlation matrix that uses the identified clusters from early run for ordering/lines
	# hardcoded based on our data! it is a large dataset but could be biased by e.g. 3S taking up such a large percentage
	# will want to improve what we base this on in the future
	reorder_indices = [9, 11, 12, 3, 4, 2, 1, 5, # split based on cluster colors dendogram assigned
					   14, 0, 13, 20, 33, 35, 28, 32, 27, 29, 31, 
					   15, 16, 22, 23, 18, 19, 17, 26, 24, 25, 8, 30, 10, 34, 21, 6, 7]
	cluster_indices = [7, 13, 18, 22, 28, 30] # cutoff indices to draw thicker lines around identified clusters - this is based on cutoff of distance 2
	plot_correlation_matrix(key_r, key_feat_dist.columns, combined_corr_cluster_path, x_offset=-0.01, y_offset=-0.01, 
							y_index_reordering=reorder_indices, y_cluster_bars_index=cluster_indices, x_cluster_bars_index=cluster_indices)

	return # function complete

if __name__ == '__main__':
    # Map command line arguments to function arguments.
    study_correlations(sys.argv[1])
