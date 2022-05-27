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
fi
# similarly, need to check for repo path, use it to define expected python script path
if [[ -z "${repo_root}" ]]; then
	# if don't have the variable, repeat similar process to get directory this script is in, which should be under individual_modules subfolder of the repo
	full_path=$(realpath $0)
	repo_root=$(dirname $full_path)
	func_root="$repo_root"/functions_called
else
	func_root="$repo_root"/individual_modules/functions_called
	pipeline="Y" # flag to see that this was called via pipeline, so can setup email
fi
# finally, need to collect transcribeme sftp password if don't have it
if [[ -z "${transcribeme_password}" ]]; then
	echo "TranscribeMe account password?"
	read -s transcribeme_password
	
	# notify user script is starting
	echo ""
	echo "Beginning script for study:"
	echo "$study"
	echo "will check for transcripts corresponding to files found in pending_audio folder for each patient in this study"
	echo ""
fi

# body:
# initialize email alert txt file, if this was called by the pipeline (no email alert from standalone module)
if [[ $pipeline == "Y" ]]; then
	echo "Transcription Pull Updates for ${study}:" > "$repo_root"/transcript_lab_email_body.txt 
	echo "" >> "$repo_root"/transcript_lab_email_body.txt # add blank line after main header. no need to add another below because those are automatically added before each patient header
	# give some additional context for what will be inside this email
	echo "Each newly pulled phone diary transcript and each phone transcript still being waited on are listed below, split by OLID. Additionally, if warnings were encountered during the process of pulling an available transcript, they will be listed under the corresponding patient section. If any (known) issues arose with subsequent transcript processing steps, a description is appended at the bottom of this email." >> "$repo_root"/transcript_lab_email_body.txt
fi
# actually start running the main computations
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
for p in *; do # loop over all patients in the specified study folder on PHOENIX
	# first check that it is truly an OLID, that has had some files successfully pushed to transcribeme in the past
	if [[ ! -d $p/phone/processed/audio/pending_audio ]]; then
		continue
	fi
	cd "$p"/phone/processed/audio
	# also check that pending_audio is not empty, so we know if there are actually files actively being waited on
	if [ -z "$(ls -A pending_audio)" ]; then
   		# back out of pt folder if there is nothing to check for
		cd /data/sbdp/PHOENIX/PROTECTED/"$study"
		continue
	fi
	# create transcripts folder if it hasn't been done for this patient yet
	if [[ ! -d transcripts ]]; then
		mkdir transcripts
	fi

	# announce each patient that will be input to the python script on this run through
	echo "Checking ${p}"

	# this script will go through the pending_audio folder for this patient, check for corresponding named outputs on the transcribeme server, pulling them if available
	# it will also do file management on the server, update the pending_audio folder accordingly
	# behaves slightly differently whether this is called individually or via pipeline, because when called via pipeline have email alert related work to do
	python "$func_root"/phone_transcribeme_sftp_pull.py "$study" "$p" "$transcribeme_password" "$pipeline" "$repo_root"/transcript_lab_email_body.txt

	# now add new info about this OLID to email alert body (if this is part of pipeline)
	if [[ $pipeline == "Y" ]]; then
		# pending_audio folder will contain all necessary info
		cd pending_audio

		# first list transcripts that were successfully pulled
		# get total number pulled this round to put into header
		num_pulled=$(find . -maxdepth 1 -name "done+*" -printf '.' | wc -m)
		echo "" >> "$repo_root"/transcript_lab_email_body.txt 
		echo "Participant ${p} Transcripts Newly Completed/Processed (${num_pulled} Total) - " >> "$repo_root"/transcript_lab_email_body.txt 
		# loop through files that have been pulled to append the names to email list
		shopt -s nullglob # if there are no "done" files, this will keep it from running empty loop
		for file in done+*; do 
			orig_name=$(echo "$file" | awk -F '+' '{print $2}') # splitting on + now
			echo "$orig_name" >> "$repo_root"/transcript_lab_email_body.txt
		done
		# delete the done files from pending now
		rm done+*

		# then list transcripts that remain pending
		# get remaining number of audios to put into header
		num_pending=$(ls -1 | wc -l)
		echo "" >> "$repo_root"/transcript_lab_email_body.txt 
		echo "Participant ${p} Transcripts Still Pending (${num_pending} Total) - " >> "$repo_root"/transcript_lab_email_body.txt 
		# loop through remaining files to append the names to email list
		shopt -s nullglob # if there are no remaining files, this will keep it from running empty loop
		for file in *; do 
			echo "$file" >> "$repo_root"/transcript_lab_email_body.txt
		done
	fi

	# back out of pt folder when done
	cd /data/sbdp/PHOENIX/PROTECTED/"$study"
done