import json
import os
import shutil


def load_results(result_file_path):
	if not os.path.isfile(result_file_path):
		return {}
	with open(result_file_path, "r") as result_file:
		return json.load(result_file)


def save_results(result_file_path, results):
	os.makedirs(os.path.dirname(result_file_path), exist_ok = True)
	with open(result_file_path + ".tmp", "w") as result_file:
		json.dump(results, result_file, indent = 4)
	if os.path.isfile(result_file_path):
		os.remove(result_file_path)
	shutil.move(result_file_path + ".tmp", result_file_path)
