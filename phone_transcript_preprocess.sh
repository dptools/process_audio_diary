#!/bin/bash

# test using console and log file simultaneously
exec >  >(tee -ia transcript.log)
exec 2> >(tee -ia transcript.log >&2)

# this script handles all preprocessing/metadata organization/raw feature extraction on the transcript end for phone diaries, beginning with pulling new transcripts from TranscribeMe. 
# for an ongoing study it will be run once weekly, on a separate schedule from the audio preprocess script 
# (for example this script could be run one day prior to future audio preprocess runs)

# hard code at the top the list of email recipients for now, just listing 3 main addresses
# (giving my Harvard one because mail command seems more finicky with sending to my partners address?)
email_list="mennis@g.harvard.edu,ELIEBENTHAL@MCLEAN.HARVARD.EDU,jtbaker@partners.org"

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

# now get password for transcribeme sftp - will always at least try to pull transcripts if there is anything in pending_audio subfolder for a given patient in the specified study
echo "TranscribeMe account password?"
read -s transcribeme_password

# let user know script is starting
echo ""
echo "Beginning script - phone transcript preprocessing for:"
echo "$study"
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# check for any new outputs from TranscribeMe, pulling any that exist and deleting the corresponding decrypted audio file from pending_audio upon successful pull
# (this will also track which files were successfully pulled and which remain pending, putting together a file for email which is saved temporarily in the repo folder)
echo "Pulling any newly available diary transcripts for this study from TranscribeMe"
# export transcribeme password for script to use
export transcribeme_password
# call script
bash "$repo_root"/individual_modules/run_transcription_pull.sh
# clear out the password and unset now that script done
export transcribeme_password=""
unset transcribeme_password
# if it becomes problematic to leave files decrypted while we are waiting on TranscribeMe's output, can consider adjusting how we handle the pending_audio folder
# however the file will be left decrypted on TranscribeMe's server until that time no matter what, so I suspect this shouldn't be a big deal
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# convert the provided transcript txt files to CSV format for processing
echo "Converting newly pulled transcripts to CSV"
bash "$repo_root"/individual_modules/run_transcript_csv_conversion.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# run transcript QC on all available transcripts for this study
echo "Running QC on all available transcripts for this study"
bash "$repo_root"/individual_modules/run_transcript_qc.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# run DPDash formatting script to create new DPDash formatted audioQC and transcriptQC outputs from the raw outputs of those scripts
# (this will include updating the transcript availability column of audioQC as well as the obvious updates to transcriptQC on DPDash)
echo "Creating DPDash formatted QC outputs"
bash "$repo_root"/individual_modules/run_dpdash_format.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# extract NLP features
echo "Extracting NLP features for all available transcripts"
bash "$repo_root"/individual_modules/run_transcript_nlp.sh
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# send email notifying lab members about transcripts successfully pulled/processed, and those we are still waiting on. 
echo "Emailing status update to lab"
mail -s "[Phone Diary Pipeline Updates] New Transcripts Received from TranscribeMe" "$email_list" < "$repo_root"/transcript_lab_email_body.txt
rm "$repo_root"/transcript_lab_email_body.txt # this will be created by wrapping transcript pull script, cleared out here after email sent
# in future will want to improve how we implement the email list, may be different for different studies
# also may want to improve how we do the subject line so it's less repetitive (include date info possibly? and/or give info on total number of new transcripts? even just study name?)
echo ""

# add current time for runtime tracking purposes
now=$(date +"%T")
echo "Current time: ${now}"
echo ""

# script wrap up - unset environment variables so doesn't mess with future scripts
unset study
unset repo_root
echo "Script completed"
