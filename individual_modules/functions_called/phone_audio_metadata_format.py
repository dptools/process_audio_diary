#!/usr/bin/env python

import pandas as pd
import numpy as np
import math
import os
import sys
from datetime import date, timedelta, datetime
import pytz

# https://stackoverflow.com/questions/2881025/python-daylight-savings-time -> I do assume he is always in eastern time! could eventuall work in gps for travel accounting but not worth it now. I dont think he travels a lot anyway
def is_dst(dt, timezone="US/Eastern"):
    timezone = pytz.timezone(timezone)
    timezone_aware_date = timezone.localize(dt, is_dst=None)
    return timezone_aware_date.tzinfo._dst.seconds != 0

def create_eastern_time_filemap(study, OLID):
	oneday=timedelta(days=1)
	days = {}
	cur_day = ""
	cur_recording_number = 1

	try:
		os.chdir("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/raw")
	except:
		# either patient has no phone data, or something is wrong with the input - just exit if so
		print("No raw phone data exists for input OLID " + OLID + ", continuing") # provide info on why function exited, in case called from outside pipeline
		return

	folders=os.listdir(".")
	files = []
	files_absolute = []
	for folder in folders:
		try: # some phones have no audio recording at all! prevent script from crashing though in case another phone does have some files
			files_test = os.listdir(os.path.join(folder,"audio_recordings"))
		except:
			continue
		files_true = [x for x in files_test if x.endswith(".lock")]
		files.extend(files_true)
		files_true_absolute = [os.path.join(folder,"audio_recordings",x) for x in files_true]
		files_absolute.extend(files_true_absolute)
		# this does assume that anything not ending in .lock is a folder, but that historically holds true for Beiwe audio, shouldn't be a problem
		subfolders_true = [x for x in files_test if not x.endswith(".lock")] 
		for subfolder in subfolders_true:
			files_sub = os.listdir(os.path.join(folder,"audio_recordings",subfolder))
			files.extend(files_sub)
			files_sub_absolute = [os.path.join(folder,"audio_recordings",subfolder,x) for x in files_sub]
			files_absolute.extend(files_sub_absolute) 
	if len(files) == 0:
		print("No phone audio data exists for input OLID " + OLID + ", continuing") # provide info on why function exited, in case called from outside pipeline
		return
	indices_sorted = sorted(range(len(files)), key=lambda k: files[k])
	file_paths_final = [files_absolute[i] for i in indices_sorted]
	
	for f in range(len(file_paths_final)):
		file_real = file_paths_final[f]
		file = file_paths_final[f].split("/")[-1] # remove the absolute path info for following part
		try:
			name = file.split(".")[0]
			date_str = name.split(" ")[0]
			year = int(date_str.split("-")[0])
			month = int(date_str.split("-")[1])
			day = int(date_str.split("-")[2])
			time = name.split(" ")[1]
			hour = int(time.split("_")[0])
			minsec = time.split("_")[1] + "_" + time.split("_")[2]
			try: 
				dst_bool = is_dst(datetime(year=year,month=month,day=day,hour=hour))
				if dst_bool:
					hour = hour - 4
				else:
					hour = hour - 5
			except:
				hour = hour - 4
			hour_date = hour - 4 # if answers prior to 4 am, count it as previous day! -> hours will range from 4 to 27 instead of 0 to 23
			date_form = date(year,month,day)
			if hour_date < 0:
				hour = hour + 24
				true_date = date_form - oneday
				date_str = true_date.isoformat()	
		except:
			print("Name formatted incorrectly for: " + file + ", ignoring") # even for pipeline purposes will want to know if a file is found in raw not matching expected naming conventions
			cur_recording_number = cur_recording_number + 1
			continue

		if cur_day == date_str:
			# duplicate days also means we need to skip over it - but no need to log that info here, will be clear from other steps of pipeline.
			cur_recording_number = cur_recording_number + 1
			continue

		if cur_day != "":
			year = int(date_str.split("-")[0])
			month = int(date_str.split("-")[1])
			day = int(date_str.split("-")[2])
			date_form = date(year,month,day)
			prev_year = int(cur_day.split("-")[0])
			prev_month = int(cur_day.split("-")[1])
			prev_day = int(cur_day.split("-")[2])
			prev_date_form = date(prev_year,prev_month,prev_day)
			if date_form - prev_date_form != oneday:
				days_gap = int((date_form - prev_date_form).days)
				for d in range(1,days_gap):
					missing_day = prev_date_form + timedelta(days=d)
					missing_day_str = missing_day.isoformat()
					days[missing_day_str] = 0
		cur_day = date_str
		days[cur_day] = (str(hour)+"_"+minsec, file_real, cur_recording_number)
		cur_recording_number = cur_recording_number + 1

	df_columns = ["iso_date", "year_int", "month_int", "day_int", "survey_answer_available", "ET_hour_int_formatted", "ET_time_formatted_string", "original_filepath", "new_filename", "recording_number"]
	iso_dates = days.keys()
	iso_dates.sort()
	years = []
	months = []
	days_list = []
	surveys_available = []
	hours_int_list = []
	time_str_list = []
	files_list = []
	filenames = []
	recording_numbers = []
	for d in iso_dates:
		years.append(int(d.split("-")[0]))
		months.append(int(d.split("-")[1]))
		days_list.append(int(d.split("-")[2]))
		if days[d] == 0:
			surveys_available.append(0)
			hours_int_list.append(np.nan)
			time_str_list.append("")
			files_list.append("")
			filenames.append("")
			recording_numbers.append(np.nan)
		else:
			surveys_available.append(1)
			ans_tuple = days[d]
			hours_int_list.append(int(ans_tuple[0].split("_")[0]))
			time_str_list.append(ans_tuple[0])
			files_list.append(ans_tuple[1])
			file_formatted = ans_tuple[1].split("/")[-1].split(".")[0]
			filenames.append(file_formatted.split(" ")[0] + "+" + file_formatted.split(" ")[1])
			recording_numbers.append(ans_tuple[2])
	df_vals = [iso_dates, years, months, days_list, surveys_available, hours_int_list, time_str_list, files_list, filenames, recording_numbers]

	map_csv = pd.DataFrame()
	for i in range(len(df_columns)):
		label = df_columns[i]
		value = df_vals[i]
		map_csv[label] = value
	map_csv.to_csv("/data/sbdp/PHOENIX/PROTECTED/" + study + "/" + OLID + "/phone/processed/audio/" + study + "_" + OLID + "_phone_audio_ETFileMap.csv", index=False)

if __name__ == '__main__':
    # Map command line arguments to function arguments.
    create_eastern_time_filemap(sys.argv[1], sys.argv[2])
