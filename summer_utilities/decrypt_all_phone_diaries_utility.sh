#!/bin/bash

# Script to redecrypt all audio diaries for a particular study on PHOENIX, in case they need to be reviewed or additional processing needs to be run

# get study input
echo "Study of interest?"
echo "(should match PHOENIX study name, validated options are BLS and DPBPD)"
read study

# check study folder is real before continuing
cd /data/sbdp/PHOENIX/PROTECTED
if [[ ! -d $study ]]; then
	echo "invalid study id"
	exit
fi
cd "$study" # switch to study folder for first loop over patient list

# get password for decryption
echo "Study passphrase?"
read -s password

# get desired name for folder that will be used for the outputs under each patient folder
echo "What subfolder name should be used to contain the resulting decrypted phone diaries?"
echo "(each patient in this study will end up with their own version of this folder under their respective phone/processed/audio folder)"
echo "To interface with existing pipeline the name should be decrypted_files - but this could cause unexpected behavior if not careful, so use a different name if unsure of exact plan for these files"
read decryption_subfolder_name

echo ""
echo "Beginning script - phone audio decryption of all files in study:"
echo "$study"
echo ""

# now start looping through patients
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
for p in *; do
	# first check that it is truly an OLID that has prior phone data
	if [[ ! -d $p/phone/processed/audio ]]; then
		echo "${p} either has no phone data or is a brand new patient that has not yet had any processing run, skipping."
		echo ""
		continue
	fi
	cd "$p"

	# check whether all files for this pt already decrypted, by checking for existence of "$decryption_subfolder_name" folder already. 
	# allows script to be easily requeued if stopped mid-study, and avoids any potential confusion with unintended subfolder naming conflicts.
	# however if there was a mid-patient interruption of a previous run, will have to clear that particular output folder before rerunning (or comment out this part).
	if [[ -d phone/processed/audio/"$decryption_subfolder_name" ]]; then
		# avoid skipping if the folder is entirely empty though
		cd phone/processed/audio
		if [ -z "$(ls -A ${decryption_subfolder_name})" ]; then
			rm -rf "$decryption_subfolder_name"
			cd ../../..
		else
			echo "${p} already has a ${decryption_subfolder_name} folder, skipping. Please choose a different name or clear out old folders if this was unexpected."
			echo ""
			cd ../../../..
			continue
		fi
	fi

	# now can begin on this patient
	echo "Beginning decryption for ${p}"

	# create temporary folder for the decrypted files now, using the specified name
	mkdir phone/processed/audio/"$decryption_subfolder_name"

	# some raw files are directly in audio_recordings subfolder
	for file in phone/raw/*/audio_recordings/*.mp4.lock; do 
		# get metadata info
		nameint=$(echo "$file" | awk -F '/' '{print $5}') 
		name=$(echo "$nameint" | awk -F '.' '{print $1}') 
		date=$(echo "$name" | awk -F ' ' '{print $1}')
		time=$(echo "$name" | awk -F ' ' '{print $2}')
		hour=$(echo "$time" | awk -F '_' '{print $1}')

		if [[ -e phone/processed/audio/"$decryption_subfolder_name"/"$date"+"$time".mp4 ]]; then
			# don't redecrypt if already decrypted this file for this batch! 
			# necessary because raw file organization in Beiwe sometimes leads to duplicate recording files (when there are files on multiple levels of folder heirarchy)
			# also if earlier patient level check is commented out, this will allow the code to resume running on a particular patient without issue
			continue
		fi

		# decrypt
		crypt_exp "$password" phone/processed/audio/"$decryption_subfolder_name"/"$date"+"$time".mp4 "$file" > /dev/null 
	done

	# some files are under additional subfolder - repeat similar process
	for file in phone/raw/*/audio_recordings/*/*.mp4.lock; do 
		# get metadata info
		nameint=$(echo "$file" | awk -F '/' '{print $6}') 
		name=$(echo "$nameint" | awk -F '.' '{print $1}') 
		date=$(echo "$name" | awk -F ' ' '{print $1}')
		time=$(echo "$name" | awk -F ' ' '{print $2}')
		hour=$(echo "$time" | awk -F '_' '{print $1}')

		if [[ -e phone/processed/audio/"$decryption_subfolder_name"/"$date"+"$time".mp4 ]]; then
			# don't redecrypt if already decrypted this file for this batch! 
			# necessary because raw file organization in Beiwe sometimes leads to duplicate recording files (when there are files on multiple levels of folder heirarchy)
			# also if earlier patient level check is commented out, this will allow the code to resume running on a particular patient without issue
			continue
		fi

		# decrypt
		crypt_exp "$password" phone/processed/audio/"$decryption_subfolder_name"/"$date"+"$time".mp4 "$file" > /dev/null 
	done

	# once all decrypted, convert to wav and remove mp4s
	cd phone/processed/audio/"$decryption_subfolder_name"
	for file in *.mp4; do
		if [[ ! -e $file ]]; then # avoid error message for when file doesn't exist
			continue
		fi
		name=$(echo "$file" | awk -F '.' '{print $1}')
		ffmpeg -i "$file" "$name".wav &> /dev/null
	done
	rm *.mp4

	# back out of pt folder when done
	cd /data/sbdp/PHOENIX/PROTECTED/"$study"
	echo "" # add blank line before next patient outputs
done