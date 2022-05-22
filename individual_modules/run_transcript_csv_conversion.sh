#!/bin/bash

# this is a wrapping bash scripts that converts raw TranscribeMe txt outputs to more easily processable CSVs, for all patients in a given study
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
	# first verify this is a patient folder w/ valid OLID
	if [[ ! -d $p ]]; then # needs to be directory
		continue
	fi
	if [[ ${#p} != 5 ]]; then # needs to be 5 characters
		continue
	fi
	# some patients may not yet have any transcripts available, check for this too
	if [[ ! -d "$p"/phone/processed/audio/transcripts ]]; then 
		continue
	fi
	# now that patient confirmed, get started
	cd "$p"/phone/processed/audio/transcripts
	if [[ ! -d csv ]]; then # make csv subfolder if this is the first transcript conversion for this patient
		mkdir csv 
	fi
	pt_has_new=false # only mention patients in log that had new transcripts to process, tracked with this Boolean
	encountered_non_ascii=false # similarly add a print to log at end if ever encountered non-ASCII characters
	# (latter just for main pipeline, as details of missed transcripts will only go in email alert in that case)

	# all text files on top level should be raw transcripts from TranscribeMe, loop through them
	for file in *.txt; do		
		# in the future may add additional checks to ensure only expected transcript files are in this folder?
		name=$(echo "$file" | awk -F '.' '{print $1}')
		
		[[ -e csv/"${name}".csv ]] && continue # if already have a formatted copy skip

		pt_has_new=true # so if get here means there is some new file to convert
		
		# ensure transcript is in ASCII encoding (sometimes they returned UTF-8, usually just a few offending characters that need to be fixed)
		typecheck=$(file -n "$file" | grep ASCII | wc -l)
		if [[ $typecheck == 0 ]]; then
			encountered_non_ascii=true

			# if it's not ASCII need to skip the file, setup error message
			# for now will need to manually fix any offending txt files and then rerun the conversion (and later pipeline steps) for those
			# hopefully in future will have a way to deal with it fully automatically
			if [[ ! -e "${repo_root}"/transcript_lab_email_body.txt ]]; then
				# if this module was called independently, just print error message
				echo "" # also add spacing around it because the grep output could end up being long
				echo "Found transcript that is not ASCII encoded, skipping for now. Please address the following portions of ${file}:"
				grep_out=$(grep -P '[^\x00-\x7f]' "$file")
				echo "$grep_out"
				echo ""
			else
				# if this module was called via the main pipeline, should add this info to the end of the email alert file (after a blank line)
				echo "" >> "$repo_root"/transcript_lab_email_body.txt
				echo "${file} is not ASCII encoded, so is not currently able to be processed. Please remove offending characters and then rerun processing steps on this transcript. The following command can be executed to identify the problematic parts:" >> "$repo_root"/transcript_lab_email_body.txt
				echo "​grep -P '[^\x00-\x7f]' /data/sbdp/PHOENIX/PROTECTED/${study}/${p}/phone/processed/audio/transcripts/${file}" >> "$repo_root"/transcript_lab_email_body.txt
				# not actually including the output here so that email won't ever accidentally include PII
			fi

			continue 
		fi

		# prep CSV with column headers
		# (no reason to have DPDash formatting for a transcript CSV, so I choose these columns)
		# (some of them are just for ease of future concat/merge operations)
		echo "study,patient,filename,subject,timefromstart,text" > csv/"$name".csv

		# check subject number format, as they've used a few different delimiters in the past
		# (this does assume they are consistent with one format throughout a single file though)
		subcheck=$(cat "$file" | grep S1: | wc -l) # subject 1 is guaranteed to appear at least once as it is the initial ID they assign 

		# in future may want to make the timestamp selection more flexible too? in past onsite interviews TranscribeMe was sometimes inconsistent: 
		# one batch they left off ms resolution on the timestamps, one batch they did not include the hour number in the timestamp formatting, etc. 
		# could imagine similar inconsistency problems cropping up here (although obviously don't expect hour number specifically to ever be reported for the diaries)
		# hopefully transcript QC/other sanity check measures will catch any issue with this if it ever arises though, so not a high priority at the moment

		# read in transcript line by line to convert to CSV rows
		while IFS='' read -r line || [[ -n "$line" ]]; do
			if [[ $subcheck == 0 ]]; then # subject ID always comes first, is sometimes followed by a colon
				sub=$(echo "$line" | awk -F ' ' '{print $1}') 
			else
				sub=$(echo "$line" | awk -F ': ' '{print $1}')
			fi
			time=$(echo "$line" | awk -F ' ' '{print $2}') # timestamp always comes second
			text=$(echo "$line" | awk -F '[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9] ' '{print $2}') # get text based on what comes after timestamp in expected format (MM:SS.milliseconds)
			# the above still works fine if hours are also provided, it just hinges on full minute digits and millisecond resolution being provided throughout the transcript
			[ -z "$text" ] && continue # skip over empty lines
			text=$(echo "$text" | tr -d '"') # remove extra characters at end of each sentence
			text=$(echo "$text" | tr -d '\r') # remove extra characters at end of each sentence
			echo "${study},${p},${name},${sub},${time},\"${text}\"" >> csv/"$name".csv # add the line to CSV
		done < "$file"
	done

	if [ "$pt_has_new" = true ]; then
		echo "Done converting new transcripts for ${p}"
	fi
	if [[ -e "${repo_root}"/transcript_lab_email_body.txt ]]; then # i.e. if was called via pipeline, so that error message above only went into email
		if [ "$encountered_non_ascii" = true ]; then
			echo "(note though that at least one file failed to convert for this patient due to non-ASCII characters, see bottom of email alert for more details)"
		fi
	fi

	cd /data/sbdp/PHOENIX/PROTECTED/"$study" # at end of patient reset to root study dir for next loop
done