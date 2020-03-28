import json
import logging
import os
import platform
import sys


default_log_format = "[{levelname}][{name}] {message}"
file_log_format = "{asctime} [{levelname}][{name}] {message}"
date_format = "%Y-%m-%dT%H:%M:%S"


def configure_logging(log_level):
	logging.root.setLevel(log_level)

	logging.addLevelName(logging.DEBUG, "Debug")
	logging.addLevelName(logging.INFO, "Info")
	logging.addLevelName(logging.WARNING, "Warning")
	logging.addLevelName(logging.ERROR, "Error")
	logging.addLevelName(logging.CRITICAL, "Critical")

	formatter = logging.Formatter(default_log_format, date_format, "{")
	stream_handler = logging.StreamHandler(sys.stdout)
	stream_handler.setLevel(log_level)
	stream_handler.formatter = formatter
	logging.root.addHandler(stream_handler)


def configure_log_file(log_level, log_file):
	formatter = logging.Formatter(file_log_format, date_format, "{")
	file_handler = logging.FileHandler(log_file, mode = "w")
	file_handler.setLevel(log_level)
	file_handler.formatter = formatter
	logging.root.addHandler(file_handler)


def create_default_environment():
	return {
		"git_executable": "git",
		"python3_executable": sys.executable,
		"python3_system_executable": find_system_python(),
		"scp_executable": "scp",
		"ssh_executable": "ssh",
	}


def load_environment():
	env = create_default_environment()
	env.update(_load_environment_transform(os.path.join(os.path.expanduser("~"), "environment.json")))
	env.update(_load_environment_transform("environment.json"))
	return env


def _load_environment_transform(transform_file_path):
	if not os.path.exists(transform_file_path):
		return {}
	with open(transform_file_path) as transform_file:
		return json.load(transform_file)


def find_system_python():
	if platform.system() == "Linux":
		return "/usr/bin/python3"

	if platform.system() == "Windows":
		possible_paths = [
			os.path.join(os.environ["SystemDrive"] + "\\", "Python38", "python.exe"),
			os.path.join(os.environ["ProgramFiles"], "Python38", "python.exe"),
			os.path.join(os.environ["SystemDrive"] + "\\", "Python37", "python.exe"),
			os.path.join(os.environ["ProgramFiles"], "Python37", "python.exe"),
			os.path.join(os.environ["SystemDrive"] + "\\", "Python36", "python.exe"),
			os.path.join(os.environ["ProgramFiles"], "Python36", "python.exe"),
			os.path.join(os.environ["SystemDrive"] + "\\", "Python35", "python.exe"),
			os.path.join(os.environ["ProgramFiles"], "Python35", "python.exe"),
		]

		for path in possible_paths:
			if os.path.exists(path):
				return path

		return None

	raise ValueError("Unsupported platform: '%s'" % platform.system())
