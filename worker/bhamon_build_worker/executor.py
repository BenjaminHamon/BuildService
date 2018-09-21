import logging
import os
import signal
import subprocess
import time

import bhamon_build_worker.worker_storage as worker_storage


logger = logging.getLogger("Executor")

termination_timeout_seconds = 30

should_exit = False


def run(job_identifier, build_identifier, environment):
	signal.signal(signal.SIGINT, _handle_termination)
	signal.signal(signal.SIGBREAK, _handle_termination)
	signal.signal(signal.SIGTERM, _handle_termination)

	logger.info("(%s) Executing %s", build_identifier, job_identifier)
	build_request = worker_storage.load_request(job_identifier, build_identifier)

	build_status = {
		"job_identifier": build_request["job_identifier"],
		"build_identifier": build_request["build_identifier"],
		"workspace": os.path.join("workspaces", build_request["job"]["workspace"]),
		"environment": environment,
		"parameters": build_request["parameters"],
		"status": "running",
		"steps": [
			{
				"index": step_index,
				"name": step["name"],
				"command": step["command"],
				"status": "pending",
			}
			for step_index, step in enumerate(build_request["job"]["steps"])
		],
	}

	logger.info("(%s) Build is starting", build_identifier)

	try:
		worker_storage.save_status(job_identifier, build_identifier, build_status)

		if not os.path.exists(build_status["workspace"]):
			os.makedirs(build_status["workspace"])

		build_final_status = "succeeded"
		is_skipping = False

		for step_index, step in enumerate(build_request["job"]["steps"]):
			if not is_skipping and should_exit:
				build_final_status = "aborted"
				is_skipping = True
			_execute_step(job_identifier, build_identifier, build_status, step_index, step, is_skipping)
			if not is_skipping and step["status"] != "succeeded":
				build_final_status = step["status"]
				is_skipping = True

		build_status["status"] = build_final_status
		worker_storage.save_status(job_identifier, build_identifier, build_status)

	except:
		logger.error("(%s) Build raised an exception", build_identifier, exc_info = True)
		build_status["status"] = "exception"
		worker_storage.save_status(job_identifier, build_identifier, build_status)

	logger.info("(%s) Build completed with status %s", build_identifier, build_status["status"])


def _execute_step(job_identifier, build_identifier, build_status, step_index, step, is_skipping):
	logger.info("(%s) Step %s is starting", build_identifier, step["name"])

	try:
		step["status"] = "running"
		worker_storage.save_status(job_identifier, build_identifier, build_status)

		log_file_path = worker_storage.get_log_path(job_identifier, build_identifier, step_index, step["name"])
		result_file_path = os.path.join(".build_results", job_identifier + "_" + build_identifier, "results.json")

		if is_skipping:
			step["status"] = "skipped"

		else:
			step_parameters = {
				"environment": build_status["environment"],
				"parameters": build_status["parameters"],
				"result_file_path": result_file_path,
			}

			step_command = [ argument.format(**step_parameters) for argument in step["command"] ]
			logger.info("(%s) + %s", build_identifier, " ".join(step_command))

			with open(log_file_path, "w") as log_file:
				child_process = subprocess.Popen(
					step_command, cwd = build_status["workspace"],
					stdout = log_file, stderr = subprocess.STDOUT,
					creationflags = subprocess.CREATE_NEW_PROCESS_GROUP)
				step["status"] = _wait_process(build_identifier, child_process)

		if os.path.isfile(os.path.join(build_status["workspace"], result_file_path)):
			worker_storage.save_results(job_identifier, build_identifier, os.path.join(build_status["workspace"], result_file_path))
		worker_storage.save_status(job_identifier, build_identifier, build_status)

	except:
		logger.error("(%s) Step %s raised an exception", build_identifier, step["name"], exc_info = True)
		step["status"] = "exception"
		worker_storage.save_status(job_identifier, build_identifier, build_status)

	logger.info("(%s) Step %s completed with status %s", build_identifier, step["name"], step["status"])


def _wait_process(build_identifier, child_process):
	result = None
	while result is None:
		if should_exit:
			logger.info("(%s) Terminating child process", build_identifier)
			os.kill(child_process.pid, signal.CTRL_BREAK_EVENT)
			try:
				result = child_process.wait(timeout = termination_timeout_seconds)
			except subprocess.TimeoutExpired:
				logger.warning("(%s) Terminating child process (force)", build_identifier)
				child_process.kill()
			return "aborted"
		time.sleep(1)
		result = child_process.poll()
	return "succeeded" if result == 0 else "failed"


def _handle_termination(signal_number, frame):
	global should_exit
	should_exit = True
