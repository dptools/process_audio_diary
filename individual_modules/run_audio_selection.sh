#!/bin/bash

# this is one of a set of wrapping bash scripts that allow the python scripts to be called on all patients in a given study
# it is called by the main pipeline, but can also be used in a modular fashion
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
# finally, need to get audio cutoff settings
# (in future may be path to config instead of asking about the cutoff values separately like this?)
if [[ -z "${length_cutoff}" ]]; then
	echo "Minimum acceptable audio length (in seconds)?"
	read length_cutoff
fi
if [[ -z "${db_cutoff}" ]]; then
	echo "Minimum acceptable audio db?"
	read db_cutoff
fi

# body:
# actually start running the main computations
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
for p in *; do # loop over all patients in the specified study folder on PHOENIX
	# first check that it is truly an OLID, that has phone audio data
	if [[ ! -d $p/phone/processed/audio/decrypted_files ]]; then
		continue
	fi
	cd "$p"/phone/processed/audio
	# can also skip over the patient if there is no new decrypted audio
	# (both this module and the steps that come after it in the main pipeline have no use for a patient with no newly processed audio)
	if [ -z "$(ls -A decrypted_files)" ]; then	
		cd /data/sbdp/PHOENIX/PROTECTED/"$study" # back out of pt folder before skipping
   		continue
	fi

	# create a temporary folder of audios that should be sent to TranscribeMe. 
	# (if auto send is on, it will be deleted automatically by the transcript push script, otherwise this is left to be dealt with manually)
	if [[ ! -d to_send ]]; then
		mkdir to_send 
	fi

	# this script will go through decrypted files for the current patient and move any that meet criteria to "to_send" - also renaming them appropriately for easy pull later
	python "$func_root"/phone_audio_send_prep.py "$study" "$p" "$length_cutoff" "$db_cutoff"

	# back out of pt folder when done
	cd /data/sbdp/PHOENIX/PROTECTED/"$study"
done