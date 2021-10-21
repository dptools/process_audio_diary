#!/usr/bin/env python

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
plt.ioff()
import matplotlib.cm as cm
import numpy as np
import pandas as pd
from scipy.stats.stats import pearsonr, spearmanr
from scipy.cluster.hierarchy import dendrogram, linkage, cophenet
from scipy.spatial.distance import pdist
import os

# function to calculate pearson correlation and associate p-value in matrix format for the columns of input dataframes
# input dataframe(s) should include only columns desired to be correlated
# if only one df is given the correlations will be pairwise within the df
# if two dfs are given the correlation will be pairwise between the dfs
# if given two dataframes output will obviously not be symmetric matrix, otherwise can expect a typical correlation matrix
# returns matrix of correlations, matrix of pvalues
# if optional save_path is provided both will be written as numpy array to disk (.npy file format)
# 	(suffix added before the extension will distinguish correlation and significance matrices. please do not use dots within filename)
# pearson argument defaults to True, but if False then will run spearmanr instead
def calculate_correlation_matrix(df1, df2=None, save_path=None, pearson=True):
	# prep output matrices
	cols1 = df1.columns
	size1 = len(cols1)
	if df2 is not None:
		cols2 = df2.columns
		size2 = len(cols2)
	else:
		cols2 = cols1
		size2 = size1
		df2 = df1
	corr_matrix = np.zeros((size1,size2))
	sig_matrix = np.zeros((size1,size2))

	# populate output matrices
	for i in range(size1):
		lab = cols1[i]
		cur_row = df1[lab].tolist()
		for j in range(size2):
			lab = cols2[j]
			cur_col = df2[lab].tolist()
			nas = np.logical_or(np.isnan(np.array(cur_row)), np.isnan(np.array(cur_col)))
			if pearson:
				try:
					pearson_calc = pearsonr(np.array(cur_row)[~nas], np.array(cur_col)[~nas])
				except: # handle case where they have no elements in common at all
					pearson_calc = (np.nan,np.nan)
			else:
				try:
					pearson_calc = spearmanr(np.array(cur_row)[~nas], np.array(cur_col)[~nas])
				except:
					pearson_calc = (np.nan,np.nan)
			corr_matrix[i,j] = pearson_calc[0] # first index returned by the scipy function is the correlation
			sig_matrix[i,j] = pearson_calc[1] # next is the two tailed p-value

	# save when necessary
	if save_path is not None:
		save_path_corr = save_path.split(".")[0] + "_correlation.npy"
		save_path_sig = save_path.split(".")[0] + "_significance.npy"
		np.save(save_path_corr, corr_matrix)
		np.save(save_path_sig, sig_matrix)

	return corr_matrix, sig_matrix

# function to plot correlation matrix
# labels for y axis must be given, labels for x axis can optionally be given
#	(these are expected to match the order of the matrix, which will match the order of the columns in df1 if produced from function above)
# 	(if plotting an asymmetrical "correlation matrix" x_labels should of course also be provided, corresponding to df2 columns above)
# the figure will save at the provided path (with format of the extension given)
# y_index_reordering may be provided to reorder the features on the y axis before displaying, and likewise for x_index_reordering
#	(both optional inputs should be lists that provide the permuted indices for all features on that axis)
# 	(if only y_index_reordering is provided it will be assumed this is a symmetric matrix, and both axes will be reordered using this information) 
#	(if indices are left out than those rows [or columns] will be cut)
# additional optional parameters of interest include title, chosen colormap, and max and min values to apply to the colormap
# a final optional input of note is y_cluster_bars_index (and the analogous x_cluster_bars_index): these will put thicker lines at those indices on the final matrix, for the respective axes
# 	(figure size, label font size, and properties for the thick cluster and thin primary grid lines can also be tweaked if necessary)
def plot_correlation_matrix(corr_matrix, y_labels, save_path, x_labels=None, y_index_reordering=None, x_index_reordering=None, title=None, 
							colormap=cm.PRGn, vmin=-1.0, vmax=1.0, y_cluster_bars_index=[], x_cluster_bars_index=[], cluster_width=5, 
							cluster_color='w', y_offset=0.02, x_offset=0.02, line_width=1, line_color='w', font_size=8, fig_size=(15,15)):
	# reorder axes when instructed
	if y_index_reordering is not None:
		corr_matrix = corr_matrix[np.array(y_index_reordering), :]
		y_labels = [y_labels[n] for n in y_index_reordering]
		if x_index_reordering is not None:
			corr_matrix = corr_matrix[:, np.array(x_index_reordering)]
			if x_labels is not None:
				x_labels = [x_labels[n] for n in x_index_reordering]
		else:
			corr_matrix = corr_matrix[:, np.array(y_index_reordering)]
			if x_labels is not None:
				x_labels = [x_labels[n] for n in y_index_reordering]

	# create image
	plt.figure(figsize=fig_size)
	plt.imshow(corr_matrix, cmap=colormap, vmin=vmin, vmax=vmax)

	# add labels/title
	plt.yticks(range(len(y_labels)), y_labels, fontsize=font_size)
	small_markers_y = [n + 0.48 for n in range(len(y_labels)-1)] # specify grid marker coordinates along with tick labels
	if x_labels is not None:
		plt.xticks(range(len(x_labels)), x_labels, rotation=90, fontsize=font_size)
		small_markers_x = [n + 0.48 for n in range(len(x_labels)-1)]
	else:
		plt.xticks([],[])
		small_markers_x = [n + 0.48 for n in range(len(y_labels)-1)]
	if title is not None:
		plt.title(title)

	# apply grid
	for sline in small_markers_y:
		plt.axhline(y=sline+y_offset, linewidth=line_width, color=line_color)
	for sline in small_markers_x:
		plt.axvline(x=sline+x_offset, linewidth=line_width, color=line_color)

	# apply thicker lines to denote possible clusters/groupings of interest (by default the lists are empty)
	for ind in y_cluster_bars_index:
		plt.axhline(small_markers_y[ind], linewidth=cluster_width, color=cluster_color)
	for ind in x_cluster_bars_index:
		plt.axvline(small_markers_x[ind], linewidth=cluster_width, color=cluster_color)

	# save
	plt.savefig(save_path, bbox_inches="tight")  
	plt.close("all")

# function to create dendrogram from a given correlation matrix (used to calculate pearson [or spearman] distance between each feature)
# labels matching the order of the correlation matrix indices are required to annotate the chart
# save_path is also required, and the extension provided will specify the type of image saved (svg vs png, etc.)
# optionally, a different cluster distance method can be used besides the default "complete"
# [single or average could also be viable options for the correlation distance used here. complete appears most popular]
# a title can also optionally be added, and cluster quality info optionally removed from the plot text
# additionally, a ylim tuple can optionally be provided to adjust the distance axis
def create_dendrogram(corr_matrix, labels, save_path, cluster_dist_method='complete', title=None, include_cluster_rating=True, ylim=None):
	dend_dist = 1 - corr_matrix # calculate pearson distance
	dend_link = linkage(dend_dist, cluster_dist_method) # perform hierarchical clustering- 1st input is the distance metric between points, and the second is a method specification for how to calculate distance between clusters
	dend_qc, dend_link_coph = cophenet(dend_link, pdist(dend_dist)) # check quality of clustering, will access qc variable: closer value to 1, better clustering
	plt.figure(1)
	if title is not None:
		plt.suptitle(title)
	if include_cluster_rating:
		plt.title("Cluster Rating = " + str(dend_qc),fontsize=5)
	dendrogram(
		dend_link,
        labels=labels,
		leaf_rotation=90.,  # rotates the x axis labels
        leaf_font_size=8.  # font size for the x axis labels
	)
	if ylim is not None:
		plt.ylim(ylim)
	plt.savefig(save_path, bbox_inches="tight")  
	plt.close("all")