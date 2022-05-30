#!/bin/bash

# This script makes sure latest transript-related results are synced to the BLS Dropbox PUSH
# Set up in shell because will be called via cron weekly over the summer
shopt -s expand_aliases
source ~/.bash_profile

server_account=me741@door.nmr.mgh.harvard.edu # using nmr by default because doesn't require VPN, but if this breaks can switch to ERIS
results_folder_path=/Users/mennis/Dropbox\ \(Partners\ HealthCare\)/BakerLab/Pushes/PHOENIX_PUSH_onsite_interview_BLS/BLS-phoneDiaryVisualizationOutputs-5.2022

# first sync the study-wide distribution info into top level folder (CSVs and PDFs)
rsync -a "$server_account":/data/sbdp/Distributions/phone/voiceRecording/BLS-* "$results_folder_path"/

# sync the CSV with day by day NLP related features per patient
rsync -a "$server_account":/data/sbdp/PHOENIX/PROTECTED/BLS/*/phone/processed/audio/*_phone_transcript_NLPFeaturesSummary.csv "$results_folder_path"/patient-nlp-csvs/

# also sync DPDash CSVs
rsync -a "$server_account":/data/sbdp/PHOENIX/PROTECTED/BLS/*/phone/processed/audio/*QC-day*.csv "$results_folder_path"/patient-dpdash-csvs/

# then sync the patient distributions (PDFs only)
rsync -a "$server_account":/data/sbdp/PHOENIX/PROTECTED/BLS/*/phone/processed/audio/*-distributionPlots.pdf "$results_folder_path"/patient-distributions/

# then the heatmaps
rsync -a "$server_account":/data/sbdp/PHOENIX/PROTECTED/BLS/*/phone/processed/audio/heatmaps/ "$results_folder_path"/patient-heatmaps/

# then the wordclouds
rsync -a "$server_account":/data/sbdp/PHOENIX/PROTECTED/BLS/*/phone/processed/audio/wordclouds/ "$results_folder_path"/transcript-wordclouds/

# note the audio-only related features are already fully up to date for BLS, so don't need to include here
# note also the old sync scripts will no longer work locally as I renamed the Dropbox folder recently (settings would need to be changed, but no need to use it anyway)