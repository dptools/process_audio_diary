#!/bin/bash

# this is a wrapping bash script that runs OpenSMILE on newly decrypted audio files for all patients in a given study
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

	echo ""
	echo "Beginning script for study:"
	echo "$study"
	echo ""
fi

# body:
# actually start running the main computations
cd /data/sbdp/PHOENIX/PROTECTED/"$study"
for p in *; do # loop over all patients in the specified study folder on PHOENIX
	# first check that it is truly an OLID, that has phone audio data
	if [[ ! -d $p/phone/processed/audio ]]; then
		continue
	fi
	cd "$p"/phone/processed/audio

	# then check that there are some decrypted files available for OpenSMILE to run on this round
	if [ -z "$(ls -A decrypted_files)" ]; then
		cd /data/sbdp/PHOENIX/PROTECTED/"$study" # back out of folder before skipping over patient
		continue
	fi

	# now actually begin script
	echo "OpenSMILE on patient ${p}"
	if [[ ! -d opensmile_feature_extraction ]]; then
		mkdir opensmile_feature_extraction # make subfolder in case it doesn't already exist
	fi

 	# loop through the wav files in decrypted_files to run OpenSMILE
 	# note that each OpenSMILE CSV output is named using the input WAV filename as is - so it will reflect naming convention used in decrypted_files
 	# when run using pipeline tools, this will be just a slight modification (removing spaces) to the raw audio file naming coming from Beiwe
 	# makes it easier to track which files have already been processed this way, and the corresponding metadata and transcript name (if available) can be found by referring to the DPDash formatted outputs the pipeline creates
 	# (see the "filename" column in the DPDash formatted AudioQC output for a given patient to match to the OpenSMILE output names)
 	# future steps of the pipeline that summarize OpenSMILE results will move away from this convention and focus on day numbers however
 	# may also add a utility in the future for sharing raw OpenSMILE outputs (as we deem those non-PII) by simply copying/renaming all the existing OpenSMILE outputs into a new folder, transferring that folder using input SFTP settings, and then deleting it locally.
	cd decrypted_files
	for file in *.wav; do
		if [[ ! -e $file ]]; then # avoid error message for when file doesn't exist
			continue
		fi
		name=$(echo "$file" | awk -F '.' '{print $1}')
		SMILExtract -C /data/sbdp/opensmile/opensmile-2.3.0/config/gemaps/GeMAPSv01a.conf -I "$file" --lldcsvoutput ../opensmile_feature_extraction/"$name".csv &> /dev/null
	done

	# at end of iteration for this pt go back to top
	cd /data/sbdp/PHOENIX/PROTECTED/"$study"
done