#!/bin/bash

# this is one of a set of wrapping bash scripts that allow the python scripts to be called on all patients in a given study
# it is called by the main pipeline (visualization portion), but can also be used in a modular fashion
# if wanting to run the components of the pipeline on a single patient instead, the python scripts can be called directly
# this script could also be modified to run on only a subset of patients by adding additional checks into the loop over patients below

# setup:
# if called by pipeline will have study variable already set, but to allow modular usage prompt for study of interest if variable is unset
if [[ -z "${study}" ]]; then
	echo "Module called stand alone, prompting for necessary settings:"
	echo "Study of interest?"
	echo "(should match PHOENIX study name, validated options are BLS and DPBPD)"
	read study

	# sanity check provided answer, it should at least exist on PHOENIX
	if [[ ! -d /data/sbdp/PHOENIX/PROTECTED/$study ]]; then
		echo "invalid study id"
		exit
	fi

	echo ""
	echo "Beginning script for study:"
	echo "$study"
	echo ""
fi
# similarly, need to check for repo path, use it to define expected python script path
if [[ -z "${repo_root}" ]]; then
	# if don't have the variable, repeat similar process to get directory this script is in, which should be under individual_modules subfolder of the repo
	full_path=$(realpath $0)
	repo_root=$(dirname $full_path)
	func_root="$repo_root"/functions_called
else
	func_root="$repo_root"/individual_modules/functions_called
fi

# body:
# actually start running the main computations
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
echo "Looping through patients"
for p in *; do # loop over all patients in the specified study folder on PHOENIX
	# first check that it is truly an OLID, that has previouly processed audio
	if [[ ! -d $p/phone/processed/audio ]]; then
		continue
	fi
	cd "$p"/phone/processed/audio

	# make output folders for per-file OpenSMILE distribution PDFs
	if [[ -d opensmile_feature_extraction ]]; then
		if [[ ! -d opensmile_feature_extraction/per_diary_distribution_plots ]]; then
			mkdir opensmile_feature_extraction/per_diary_distribution_plots
		fi
	fi
	if [[ -d opensmile_features_filtered ]]; then
		if [[ ! -d opensmile_features_filtered/per_diary_distribution_plots ]]; then
			mkdir opensmile_features_filtered/per_diary_distribution_plots
		fi
	fi

	# check that there is an audio qc CSV to use, if so run the audio distribution compile script (works on QC and also OpenSMILE if available)
	# (this script updates the study-wide distribution and generates a PDF of histograms for current patient)
	if [[ -n $(shopt -s nullglob; echo *-phoneAudioQC-day*.csv) ]]; then
		python "$func_root"/phone_audio_per_patient_distributions.py "$study" "$p"
	fi

	# now do analogously for the transcript QC, and transcript NLP if available
	if [[ -n $(shopt -s nullglob; echo *-phoneTranscriptQC-day*.csv) ]]; then
		python "$func_root"/phone_transcript_per_patient_distributions.py "$study" "$p"
	fi

	# back out of folder before continuing to next patient
	cd /data/sbdp/PHOENIX/PROTECTED/"$study"
done

# once done with loop over patients create study-wide distribution PDFs
echo "Generating study-wide plots"
python "$func_root"/phone_diary_total_distributions.py "$study"