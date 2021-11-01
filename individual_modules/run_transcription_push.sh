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
	pipeline="Y" # flag to see that this was called via pipeline, so can start to setup email
fi
# also collect send limit information
if [[ -z "${auto_send_limit_bool}" ]]; then
	echo "Would you like to set an upper limit on the amount of audio the code can send? (Y or N)"
	read auto_send_limit_bool
	if [ $auto_send_limit_bool = "Y" ] || [ $auto_send_limit_bool = "y" ]; then
		echo "Maximum sum audio length (in minutes)?"
		read auto_send_limit
	fi
	# if auto_send_limit_bool is set, will assume auto_send_limit should be too, as should be calling from pipeline
fi
# finally, need to collect transcribeme sftp password if don't have it
if [[ -z "${transcribeme_password}" ]]; then
	echo "TranscribeMe account password?"
	read -s transcribeme_password
	
	# notify user script is starting
	echo ""
	echo "Beginning script for study:"
	echo "$study"
	echo "all files currently in to_send folder for each patient in this study will be uploaded to TranscribeMe"
	if [ $auto_send_limit_bool = "Y" ] || [ $auto_send_limit_bool = "y" ]; then
		echo "as long as the total minutes of audio across patients does not exceed:"
		echo "$auto_send_limit"
	fi
	echo ""
fi

# body:
# actually start running the main computations - first check that total length doesn't exceed the threshold, if necessary
if [ $auto_send_limit_bool = "Y" ] || [ $auto_send_limit_bool = "y" ]; then
	python "$func_root"/phone_audio_length_check.py "$study" "$auto_send_limit"
	if [ $? = 1 ]; then # function returns with error code if length exceeded
		# if called from pipeline will need to update the email body to denote the length was exceeded
		if [[ -e "$repo_root"/audio_lab_email_body.txt ]]; then 
			echo "Note that no audio was uploaded to TranscribeMe because the total length exceeded the input limit of ${auto_send_limit} minutes" >> "$repo_root"/audio_lab_email_body.txt
			echo "" >> "$repo_root"/audio_lab_email_body.txt
		fi
		exit 0 # so exit with status okay, no problems but don't want to proceed with transcript upload code below
	fi
fi

# now start going through patients for the upload
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
for p in *; do # loop over all patients in the specified study folder on PHOENIX
	# first check that it is truly an OLID, that has phone audio data to send
	if [[ ! -d $p/phone/processed/audio/to_send ]]; then # check for to_send folder
		continue
	fi
	cd "$p"/phone/processed/audio

	# create a folder of audios that have been sent to TranscribeMe, and are waiting on result
	# (this folder will only be made for new patient/study, otherwise it will just sit empty when no pending transcripts)
	# (may be worth deleting manually for a patient once they disenroll though? that would then remove those patients from the email alerts)
	if [[ ! -d pending_audio ]]; then
		mkdir pending_audio
	fi
	# make this folder before the check that to_send is empty, that way a new participant that has had some audios processed will still appear in email alerts

	if [ -z "$(ls -A to_send)" ]; then # also check that to_send isn't empty
		rm -rf to_send # if it is empty, clear it out!
		cd /data/sbdp/PHOENIX/PROTECTED/"$study" # back out of pt folder before skipping
		continue
	fi

	# this script will go through the files in to_send and send them to transcribeme, moving them to pending_audio if push was successful
	# behaves slightly differently whether this is called individually or via pipeline, because when called via pipeline have email alert related work to do
	python "$func_root"/phone_transcribeme_sftp_push.py "$study" "$p" "$transcribeme_password" "$pipeline"

	# check if to_send is empty now - if so delete it, if not print an error message
	if [ -z "$(ls -A to_send)" ]; then
   		rm -rf to_send
	else
		echo ""
   		echo "Warning: some diaries meant to be pushed to TranscribeMe failed to upload. Check /data/sbdp/PHOENIX/PROTECTED/${study}/${p}/phone/processed/audio/to_send for more info."
   		echo ""
	fi

	# back out of pt folder when done
	cd /data/sbdp/PHOENIX/PROTECTED/"$study"
done