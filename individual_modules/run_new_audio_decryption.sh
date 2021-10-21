#!/bin/bash

# this is a wrapping bash scripts that decrypts any new audio files for all patients in a given study
# (new is defined by not having any OpenSMILE output corresponding to that file yet)
# it is called by the main pipeline, but can also be used in a modular fashion, going along with the python script wrappers
# this script could be modified to run on only a subset of patients by adding additional checks into the loop over patients below

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
# similarly, need to check for repo path, use it to define expected path to decryption helper utility - crypt_exp will be under the functions_called subfolder
if [[ -z "${repo_root}" ]]; then
	# if don't have the variable, repeat similar process to get directory this script is in, which should be under individual_modules subfolder of the repo
	full_path=$(realpath $0)
	repo_root=$(dirname $full_path)
	func_root="$repo_root"/functions_called
else
	func_root="$repo_root"/individual_modules/functions_called
fi
# finally, need to collect decryption password if don't have it
if [[ -z "${password}" ]]; then
	echo "Study passphrase?"
	read -s password
	
	# notify user script is starting
	echo ""
	echo "Beginning script for study:"
	echo "$study"
	echo ""
fi

# body:
# actually start running the main computations
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
for p in *; do # loop over all patients in the specified study folder on PHOENIX
	# first check that it is truly an OLID, that has phone data
	if [[ ! -d $p/phone ]]; then
		continue
	fi
	# now begin on this patient
	cd "$p"
	echo "On participant ${p}"
	# create temporary folder for the decrypted files
	mkdir phone/processed/audio/decrypted_files

	# some raw files are directly in audio_recordings subfolder
	for file in phone/raw/*/audio_recordings/*.mp4.lock; do 
		# get metadata info
		nameint=$(echo "$file" | awk -F '/' '{print $5}') 
		name=$(echo "$nameint" | awk -F '.' '{print $1}') 
		date=$(echo "$name" | awk -F ' ' '{print $1}')
		time=$(echo "$name" | awk -F ' ' '{print $2}')
		hour=$(echo "$time" | awk -F '_' '{print $1}')

		if [[ -e phone/processed/audio/decrypted_files/"$date"+"$time".mp4 ]]; then
			# don't redecrypt if already decrypted for this batch! (in case resuming code after some disruption for example)
			continue
		fi

		# decrypt if new
		if [[ ! -e phone/processed/audio/opensmile_feature_extraction/"$date"+"$time".csv ]]; then
			"$func_root"/crypt_exp "$password" phone/processed/audio/decrypted_files/"$date"+"$time".mp4 "$file" > /dev/null 
		fi
	done

	# some files are under additional subfolder - repeat similar process
	for file in phone/raw/*/audio_recordings/*/*.mp4.lock; do 
		# get metadata info
		nameint=$(echo "$file" | awk -F '/' '{print $6}') 
		name=$(echo "$nameint" | awk -F '.' '{print $1}') 
		date=$(echo "$name" | awk -F ' ' '{print $1}')
		time=$(echo "$name" | awk -F ' ' '{print $2}')
		hour=$(echo "$time" | awk -F '_' '{print $1}')

		if [[ -e phone/processed/audio/decrypted_files/"$date"+"$time".mp4 ]]; then
			# don't redecrypt if already decrypted for this batch!
			# especially relevant this time because bad folder organization with the two different folder levels occasionally leads to duplicate files
			continue
		fi

		# decrypt if new
		if [[ ! -e phone/processed/audio/opensmile_feature_extraction/"$date"+"$time".csv ]]; then
			"$func_root"/crypt_exp "$password" phone/processed/audio/decrypted_files/"$date"+"$time".mp4 "$file" > /dev/null 
		fi
	done

	# once all decrypted convert to wav and remove mp4s
	cd phone/processed/audio/decrypted_files
	# instead of printing file not found error message when there are no mp4's, print custom message indicating there was no new audio for this patient this round
	# (which will be last time patient is mentioned in these logs)	
	if [ ! -z "$(ls -A *.mp4 2>/dev/null)" ]; then # need to redirect error from within the command
		for file in *.mp4; do
			name=$(echo "$file" | awk -F '.' '{print $1}')
			ffmpeg -i "$file" "$name".wav &> /dev/null
		done
		rm *.mp4
	else
		echo "No new audio diary submissions for this participant"
	fi

	# back out of pt folder when done
	cd /data/sbdp/PHOENIX/PROTECTED/"$study"
done