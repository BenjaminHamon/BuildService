import json
import logging
import os
import subprocess


logger = logging.getLogger("Executor")


def run(build_identifier, environment):
	logger.info("Executing %s", build_identifier)
	build_directory = os.path.join("builds", build_identifier)
	with open(os.path.join(build_directory, "request.json")) as build_request_file:
		build_request = json.load(build_request_file)

	build_status = {
		"job_identifier": build_request["job_identifier"],
		"build_identifier": build_request["build_identifier"],
		"status": "running",
		"steps": [],
	}
	for step_index, step in enumerate(build_request["job"]["steps"]):
		build_status["steps"].append({
			"index": step_index,
			"name": step["name"],
			"command": step["command"],
			"status": "pending",
		})
	_save_status(build_directory, build_status)

	try:

		workspace = os.path.join("workspaces", build_request["job"]["workspace"])
		if not os.path.exists(workspace):
			os.makedirs(workspace)

		def update_step_status(step_index, status):
			build_status["steps"][step_index]["status"] = status
			_save_status(build_directory, build_status)

		build_final_status = "succeeded"
		is_skipping = False
		for step_index, step in enumerate(build_request["job"]["steps"]):
			step_status = _execute_step(environment, build_directory, workspace, step_index, step, is_skipping, update_step_status)
			if not is_skipping and step_status in [ "failed", "exception" ]:
				build_final_status = step_status
				is_skipping = True
		build_status["status"] = build_final_status
		_save_status(build_directory, build_status)

	except:
		logger.error("Failed to execute build", exc_info = True)
		build_status["status"] = "exception"
		_save_status(build_directory, build_status)

	logger.info("Build completed with status %s", build_status["status"])


def _execute_step(environment, build_directory, workspace, step_index, step, is_skipping, update_status_handler):
	logger.info("Step %s running", step["name"])
	step_status = "running"
	update_status_handler(step_index, step_status)

	log_file_name = "step_{index}_{name}.log".format(index = step_index, name = step["name"])

	try:
		if is_skipping:
			step_status = "skipped"
		else:
			step_command = [ argument.format(env = environment) for argument in step["command"] ]
			logger.info("Step command: %s", " ".join(step_command))
			with open(os.path.join(build_directory, log_file_name), "w") as log_file:
				result = subprocess.call(step_command, cwd = workspace, stdout = log_file, stderr = subprocess.STDOUT)
			step_status = "succeeded" if result == 0 else "failed"
	except:
		logger.error("Failed to execute step", exc_info = True)
		step_status = "exception"

	update_status_handler(step_index, step_status)
	logger.info("Step %s completed with status %s", step["name"], step_status)
	return step_status


def _save_status(build_directory, build_status):
	status_file_path = os.path.join(build_directory, "status.json")
	with open(status_file_path + ".tmp", "w") as status_file:
		json.dump(build_status, status_file, indent = 4)
	if os.path.exists(status_file_path):
		os.remove(status_file_path)
	os.rename(status_file_path + ".tmp", status_file_path)
