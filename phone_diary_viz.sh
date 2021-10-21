#!/bin/bash

# test using console and log file simultaneously
exec >  >(tee -ia viz.log)
exec 2> >(tee -ia viz.log >&2)

# this script generates relevant visualizations (as well as intermediate outputs such as compiling study-wide distribution) for both audio and transcript sides of the pipeline

# start by getting the absolute path to the directory this script is in, which will be the top level of the repo
# this way script will work even if the repo is downloaded to a new location, rather than relying on hard coded paths to where I put the repo. 
full_path=$(realpath $0)
repo_root=$(dirname $full_path)
# export the path to the repo for scripts called by this script to also use - will unset at end
export repo_root

# gather user settings, first asking which study the code should run on - this is only setting currently for the viz side
# (in future will want to be able to read this from a config file so code can be run with no user intervention - hold up right now is password handling)
echo "Study of interest?"
echo "(should match PHOENIX study name, validated options are BLS and DPBPD)"
read study
# sanity check that the study folder is real at least
cd /data/sbdp/PHOENIX/PROTECTED
if [[ ! -d $study ]]; then
	echo "invalid study id"
	exit
fi
cd "$study" # switch to study folder for first loop over patient list
# make study an environment variable, for calling bash scripts throughout this script. will be unset at end
export study

# let user know script is starting
echo ""
echo "Beginning script - diary visualization generation for:"
echo "$study"
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# start with distributions - per patient and for the overall study
# feature distributions (OpenSMILE and NLP) also generated here, including doing OpenSMILE summary operation
echo "Generating QC and feature distributions with histograms"
bash "$repo_root"/individual_modules/run_distribution_plots.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# create heatmaps to see progression of select audio and transcript QC features over time per patient (each diary one block)
# (could also propose alternative dot plots?)
echo "Generating QC heatmaps for each patient"
bash "$repo_root"/individual_modules/run_heatmap_plots.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# sentiment-colored wordclouds for the transcripts
echo "Generating sentiment-colored wordclouds for each available transcript"
bash "$repo_root"/individual_modules/run_wordclouds.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# finally do correlation matrices for the study-wide distributions
# since no need to loop over patients here or do any other bash preprocessing, just call python script directly
echo "Creating study-wide correlation matrices"
python "$repo_root"/individual_modules/functions_called/phone_diary_correlations.py "$study"
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# script wrap up - unset environment variables so doesn't mess with future scripts
unset study
unset repo_root
echo "Script completed"
