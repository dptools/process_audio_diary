#!/bin/bash

# test using console and log file simultaneously
exec >  >(tee -ia audio.log)
exec 2> >(tee -ia audio.log >&2)

# this script handles all preprocessing/metadata organization/raw feature extraction on the audio end for Beiwe phone diaries, up to the point that new audio files of interest are pushed to TranscribeMe 
# for an ongoing study it will be run once weekly

# hard code at the top the list of email recipients for now
# for the lab alert email, just listing 3 main addresses to start
# (giving my Harvard one because mail command seems more finicky with sending to my partners address?)
lab_email_list="mennis@g.harvard.edu,ELIEBENTHAL@MCLEAN.HARVARD.EDU,jtbaker@partners.org"
# also have list for email notifying TranscribeMe that there have been new uploads
# just putting main sales support email for now, and including myself for records
transcribeme_email_list="sales_support@transcribeme.com,joshua@transcribeme.com,mennis@g.harvard.edu"

# start by getting the absolute path to the directory this script is in, which will be the top level of the repo
# this way script will work even if the repo is downloaded to a new location, rather than relying on hard coded paths to where I put the repo. 
full_path=$(realpath $0)
repo_root=$(dirname $full_path)
# export the path to the repo for scripts called by this script to also use - will unset at end
export repo_root

# gather user settings, first asking which study the code should run on
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

# then get password for decryption for this study
echo "Study passphrase?"
read -s password

# now ask about auto transcription
echo "Automatically send acceptable diaries for transcription? (Y or N)"
read auto_send_on
# make sure the answer was valid, and if it is yes gather the other settings
if [ $auto_send_on = "Y" ] || [ $auto_send_on = "y" ]; then
	# get password for transcribeme sftp
	echo "TranscribeMe account password?"
	read -s transcribeme_password

	# get cutoffs - in future when settings may get more complicated, consider reading in a config file instead?
	echo "Minimum acceptable audio length (in seconds)?"
	read length_cutoff
	echo "Minimum acceptable audio db?"
	read db_cutoff
elif [ $auto_send_on = "N" ] || [ $auto_send_on = "n" ]; then
	# all decrypted files will be kept for user to manually review if auto transcribe is not on
	length_cutoff=0
	db_cutoff=0
else
	echo "invalid option"
	unset study
	exit
fi

# let user know script is starting
echo ""
echo "Beginning script - phone audio preprocessing for:"
echo "$study"
# give additional info about this preprocess run
if [ $auto_send_on = "Y" ] || [ $auto_send_on = "y" ]; then
	echo "Automatically sending all qualifying audio to TranscribeMe"
	echo "qualifying audio have a duration (in seconds) of at least:"
	echo "$length_cutoff"
	echo "and db level of at least:"
	echo "$db_cutoff"
else
	echo "Audio will not be automatically sent to TranscribeMe"
	echo "all decrypted files will be left in the to_send subfolder of phone/processed/audio for each patient"
fi
echo ""

# setup audio processed subfolder (for new studies/patients)
for p in *; do
	# check that it is truly an OLID (assuming all directories are, but could also check for 5 characters like doing in onsite)
	# this will also confirm that this OLID has a phone directory!
	if [[ ! -d /data/sbdp/PHOENIX/PROTECTED/$study/$p/phone/processed ]]; then
		continue
	fi
	if [[ ! -d /data/sbdp/PHOENIX/PROTECTED/$study/$p/phone/processed/audio ]]; then
		mkdir /data/sbdp/PHOENIX/PROTECTED/"$study"/"$p"/phone/processed/audio # create subfolder if havent yet
	fi

	# if auto send is on:
	# for each patient, check that there is currently no to_send folder (or if there is, it is empty)
	# otherwise those contents would also get uploaded to TranscribeMe, but that may not be intended behavior -
	# when someone calls full pipeline with auto transcribe on, they would probably expect only the newly processed files to be sent
	# especially because when it is run with auto send off, a to_send folder will be left that someone may forget about, could inadvertently send a backlog later
	# so solution for now is just to exit the script if there are preexisting to_send files for this study
	# then let user know the outstanding files should be dealt with outside of the main pipeline
	if [ $auto_send_on = "Y" ] || [ $auto_send_on = "y" ]; then
		if [[ -d /data/sbdp/PHOENIX/PROTECTED/"$study"/"$p"/phone/processed/audio/to_send ]]; then 
			# know to_send exists for this patient now, so need it to be empty to continue the script
			cd /data/sbdp/PHOENIX/PROTECTED/"$study"/"$p"/phone/processed/audio
			if [ ! -z "$(ls -A to_send)" ]; then
				echo "Automatic transcription was selected, but there are preexisting audio files in to_send folder(s) under this study"
				echo "As those would get sent potentially unintentionally by auto transcription, please handle the backlog outside of the main pipeline"
				echo "The files that need to be addressed can be listed with the following command:"
				echo "ls /data/sbdp/PHOENIX/PROTECTED/${study}/*/phone/processed/audio/to_send"
				echo ""
				echo "Exiting, please requeue once the above has been addressed"
				exit # will exit if there is a problem with even one patient in this study
			fi
		fi

		# do a similar check for a decrypted_files folder. if one already exists additional audio would be accidentally sent to TranscribeMe
		if [[ -d /data/sbdp/PHOENIX/PROTECTED/"$study"/"$p"/phone/processed/audio/decrypted_files ]]; then 
			cd /data/sbdp/PHOENIX/PROTECTED/"$study"/"$p"/phone/processed/audio
			if [ ! -z "$(ls -A decrypted_files)" ]; then
				echo "Automatic transcription was selected, but there are preexisting audio files in decrypted_files folder(s) under this study"
				echo "As those would get sent potentially unintentionally by auto transcription, please handle the backlog outside of the main pipeline"
				echo "The files that need to be addressed can be listed with the following command:"
				echo "ls /data/sbdp/PHOENIX/PROTECTED/${study}/*/phone/processed/audio/decrypted_files"
				echo ""
				echo "Exiting, please requeue once the above has been addressed"
				exit # will exit if there is a problem with even one patient in this study
			fi
		fi
	fi



done

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# format file metadata first - fast, so just rerun for all audio diaries every time
echo "Creating timezone map for all audio diaries"
bash "$repo_root"/individual_modules/run_metadata_generation.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# now decrypt any yet to be analyzed files
echo "Decrypting new audio files"
export password # set password as an environment variable for the decryption script to use - in the future need to better address how we are dealing with passwords
bash "$repo_root"/individual_modules/run_new_audio_decryption.sh
export password="" # erase the environment variable immediately after decrypt done
unset password # just unset would probably be fine, but being extra careful
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# now run audio QC
echo "Running audio QC on newly decrypted files"
bash "$repo_root"/individual_modules/run_audio_qc.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# then run OpenSMILE
echo "Running OpenSMILE on newly decrypted files"
bash "$repo_root"/individual_modules/run_opensmile.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# now run VAD - includes full list of identified pause times, calculation of additional QC measures, filtering of OpenSMILE results, and creation of spectrograms
echo "Running VAD functions on newly decrypted files"
bash "$repo_root"/individual_modules/run_vad.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# now do a dpdash format run
echo "Creating DPDash formatted audio QC output"
bash "$repo_root"/individual_modules/run_dpdash_format.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# finally can set aside the audio files to be sent for transcription
echo "Setting aside files to be sent for transcription"
echo "(if auto transcription is off, all decrypted files will be moved to the to_send subfolder, left there)"
# export variables to be used by the audio selection bash script, will be unset once done
export length_cutoff
export db_cutoff
# run script
bash "$repo_root"/individual_modules/run_audio_selection.sh
# post-script cleanup
unset length_cutoff
unset db_cutoff
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# if auto send is on, will now actually send the set aside transcripts and prepare email to alert relevant lab members/transcribeme
# the below script will also locally move any transcript successfully sent from the to_send subfolder to the pending_audio subfolder 
# (if to_send is empty at the end it will be deleted, otherwise an error message to review the transcripts left in that folder will be included in email)
# (note email alert should be treated as sanity check, to at least confirm how many minutes were uploaded before TranscribeMe actually starts working on them -
#  once auto is turned on, it will assume any qualifying newly decrypted audios should be sent, will not stop to confirm even for a high number of minutes)
if [ $auto_send_on = "Y" ] || [ $auto_send_on = "y" ]; then
	echo "Sending files for transcription"
	# export transcribeme password for script to use
	export transcribeme_password
	# run script
	bash "$repo_root"/individual_modules/run_transcription_push.sh
	# clear out the password and unset now that script done
	export transcribeme_password=""
	unset transcribeme_password
	echo ""

	# add current time for runtime tracking purposes
	now=$(date +"%T")
	echo "Current time: ${now}"
	echo ""

	# initialize txt files for email bodies
	echo "Audio Push Updates for ${study}:" > "$repo_root"/audio_lab_email_body.txt
	echo "Hi," > "$repo_root"/audio_transcribeme_email_body.txt

	# call script to fill in rest of email bodies
	echo "Preparing information for automated emails"
	bash "$repo_root"/individual_modules/run_email_writer.sh
	echo ""

	# add current time for runtime tracking purposes
	now=$(date +"%T")
	echo "Current time: ${now}"
	echo ""

	# now actually send the email notifying lab members about audio files successfully pushed, with info about any errors or excluded files. 
	echo "Emailing status update to lab"
	mail -s "[Phone Diary Pipeline Updates] New Audio Uploaded to TranscribeMe" "$lab_email_list" < "$repo_root"/audio_lab_email_body.txt
	rm "$repo_root"/audio_lab_email_body.txt # this will be created by email alert script above, cleared out here after email sent
	# in future will want to improve how we implement the email list, may be different for different studies
	# also may want to improve how we do the subject line so it's less repetitive (include date info possibly? and/or give info on total number of new transcripts? even just study name?)
	# additionally, probably don't want to remove the email text right away - maybe instead move it to a temporary folder like where logs go, could then periodically clear that folder as part of clean up utility
	# (don't want to accidentally resend an old email though, so perhaps rename? test what mail command does if given a bad file path)
	echo ""

	# finally, send an email to TranscribeMe so they know new audio has been uploaded and how much - but of course only if there was some new audio uploaded
	if [[ -e "$repo_root"/audio_transcribeme_email_body.txt ]]; then 
		echo "Sending email alert to TranscribeMe"
		# use -r as part of the email command for this one so TranscribeMe will see reply address as mennis@g.harvard.edu
		mail -s "[Baker Lab] New Audio to Transcribe" -r "Michaela Ennis <mennis@g.harvard.edu>" "$transcribeme_email_list" < "$repo_root"/audio_transcribeme_email_body.txt
		rm "$repo_root"/audio_transcribeme_email_body.txt # this will also be created by email alert script above, cleared out here after email sent
	else # if email file doesn't exist in pipeline means no new audio pushed
		echo "No new audios uploaded, so no alert to send to TranscribeMe"
	fi	
	echo ""
fi

# delete the unused decrypted audios when done. 
# audio files sent will be deleted from pending_audio as their corresponding transcripts are pulled
# so if auto send is off, will need to deal with deleting decrypted audio (left in to_send) manually once done with them
# note though that any audio files recorded after the first in a given day will be deleted here even when auto send is off, as they don't get moved to to_send
echo "Clearing unnecessary decrypted audio files"
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
rm -rf */phone/processed/audio/decrypted_files
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# script wrap up - unset environment variables so doesn't mess with future scripts
unset study
unset repo_root
echo "Script completed!"
