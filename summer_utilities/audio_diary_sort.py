# script to move eligible files from decrypted_files to to_send folder to prep for TranscribeMe SFTP
# will make sure they are renamed correctly, and delete any files that get rejected (db < 40, already transcribed, or failed to find in metadata)

import os
import glob
import pandas as pd

study="BLS"

os.chdir(os.path.join("/data/sbdp/PHOENIX/PROTECTED",study))
pt_list = os.listdir(".")

for pt in pt_list:
	try:
		os.chdir(os.path.join(pt,"phone/processed/audio"))
	except:
		continue

	if not os.path.exists("decrypted_files"):
		os.chdir(os.path.join("/data/sbdp/PHOENIX/PROTECTED",study))
		continue

	audio_dpdash = glob.glob(study + "-" + pt + "-phoneAudioQC-day*.csv")
	if len(audio_dpdash) != 1:
		os.chdir(os.path.join("/data/sbdp/PHOENIX/PROTECTED",study))
		continue

	audio_df = pd.read_csv(audio_dpdash[0])

	try:
		os.mkdir("to_send")
	except:
		pass

	os.chdir("decrypted_files")
	cur_decrypted_list = os.listdir(".")

	for filen in cur_decrypted_list:
		cur_df = audio_df[audio_df["filename"]==filen]
		if cur_df.empty:
			continue
		if cur_df.shape[0] != 1:
			continue

		cur_db = cur_df["overall_db"].tolist()[0]
		if cur_db <= 40:
			continue

		cur_trans_name = cur_df["transcript_name"].tolist()[0]
		if isinstance(cur_trans_name, str) and cur_trans_name != "" and cur_trans_name.endswith(".csv"):
			continue

		cur_day = int(cur_df["day"].tolist()[0])
		if cur_day <= 0 or cur_day >= 4000:
			continue

		new_name = study + "_" + pt + "_phone_audioTranscript_day" + str(cur_day).zfill(4) + ".wav"
		os.rename(filen,"../to_send/" + new_name)

	os.chdir(os.path.join("/data/sbdp/PHOENIX/PROTECTED",study))

# deleting of the decrypted_files folders that remain should occur outside this script!