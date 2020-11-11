import json
import logging
import os
import platform
import signal
import subprocess
import time
import traceback
from typing import List

from bhamon_orchestra_model.date_time_provider import DateTimeProvider
from bhamon_orchestra_worker.worker_storage import WorkerStorage


logger = logging.getLogger("Executor")

shutdown_signal = signal.CTRL_BREAK_EVENT if platform.system() == "Windows" else signal.SIGINT # pylint: disable = no-member
subprocess_flags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0


class Executor: # pylint: disable = too-few-public-methods


	def __init__(self, storage: WorkerStorage, date_time_provider: DateTimeProvider, run_identifier: str) -> None:
		self._storage = storage
		self._date_time_provider = date_time_provider
		self.run_identifier = run_identifier

		self._run_status = None
		self._should_shutdown = False
		self.termination_timeout_seconds = 30


	def run(self, environment: dict) -> None:
		if platform.system() == "Windows":
			signal.signal(signal.SIGBREAK, lambda signal_number, frame: self._shutdown()) # pylint: disable = no-member
		signal.signal(signal.SIGINT, lambda signal_number, frame: self._shutdown())
		signal.signal(signal.SIGTERM, lambda signal_number, frame: self._shutdown())

		logger.info("(%s) Starting executor", self.run_identifier)

		# Prevent executor pyvenv from overriding a python executable specified in a command
		if "__PYVENV_LAUNCHER__" in os.environ:
			del os.environ["__PYVENV_LAUNCHER__"]

		self._initialize(environment)
		self._run_internal()

		logger.info("(%s) Exiting executor", self.run_identifier)


	def _shutdown(self) -> None:
		self._should_shutdown = True


	def _initialize(self, environment: dict) -> None:
		run_request = self._storage.load_request(self.run_identifier)

		self._run_status = {
			"project_identifier": run_request["job"]["project"],
			"job_identifier": run_request["job"]["identifier"],
			"run_identifier": run_request["run_identifier"],
			"workspace": os.path.join("workspaces", run_request["job"]["workspace"]),
			"environment": environment,
			"parameters": run_request["parameters"],

			"status": "running",

			"steps": [
				{
					"index": step_index,
					"name": step["name"],
					"command": step["command"],
					"status": "pending",
				}
				for step_index, step in enumerate(run_request["job"]["steps"])
			],

			"start_date": self._date_time_provider.now(),
			"completion_date": None,
		}

		self._storage.save_status(self.run_identifier, self._run_status)


	def _run_internal(self) -> None:
		logger.info("(%s) Run is starting for project '%s' and job '%s'", self.run_identifier, self._run_status["project_identifier"], self._run_status["job_identifier"])

		try:
			self._run_status["start_date"] = self._date_time_provider.now()
			self._storage.save_status(self.run_identifier, self._run_status)

			if not os.path.exists(self._run_status["workspace"]):
				os.makedirs(self._run_status["workspace"])

			run_final_status = "succeeded"
			is_skipping = False

			for step in self._run_status["steps"]:
				if not is_skipping and self._should_shutdown:
					run_final_status = "aborted"
					is_skipping = True
				self._execute_step(step, is_skipping)
				if not is_skipping and step["status"] != "succeeded":
					run_final_status = step["status"]
					is_skipping = True

			self._run_status["status"] = run_final_status
			self._run_status["completion_date"] = self._date_time_provider.now()
			self._storage.save_status(self.run_identifier, self._run_status)

		except: # pylint: disable = bare-except
			logger.error("(%s) Run raised an exception", self.run_identifier, exc_info = True)
			self._run_status["status"] = "exception"
			self._run_status["completion_date"] = self._date_time_provider.now()
			self._storage.save_status(self.run_identifier, self._run_status)

		logger.info("(%s) Run completed with status %s", self.run_identifier, self._run_status["status"])


	def _execute_step(self, step: dict, is_skipping: bool) -> None:
		logger.info("(%s) Step %s is starting", self.run_identifier, step["name"])

		try:
			step["status"] = "running"
			self._storage.save_status(self.run_identifier, self._run_status)

			log_file_path = self._storage.get_log_path(self.run_identifier, step["index"], step["name"])
			result_file_path = os.path.join(self._run_status["workspace"], ".orchestra", "runs", self.run_identifier, "results.json")

			if is_skipping:
				step["status"] = "skipped"

			else:
				step_command = self._format_command(step["command"], result_file_path, log_file_path)
				logger.info("(%s) + %s", self.run_identifier, " ".join(step_command))
				step["status"] = self._execute_command(step_command, log_file_path)

				if os.path.isfile(result_file_path):
					with open(result_file_path, mode = "r", encoding = "utf-8") as result_file:
						results = json.load(result_file)
					self._storage.save_results(self.run_identifier, results)

			self._storage.save_status(self.run_identifier, self._run_status)

		except: # pylint: disable = bare-except
			logger.error("(%s) Step %s raised an exception", self.run_identifier, step["name"], exc_info = True)
			step["status"] = "exception"
			self._storage.save_status(self.run_identifier, self._run_status)

		logger.info("(%s) Step %s completed with status %s", self.run_identifier, step["name"], step["status"])


	def _format_command(self, command: List[str], result_file_path: str, log_file_path: str) -> List[str]:
		results = {}
		if os.path.isfile(result_file_path):
			with open(result_file_path, mode = "r", encoding = "utf-8") as result_file:
				results = json.load(result_file)

		format_parameters = {
			"project_identifier": self._run_status["project_identifier"],
			"job_identifier": self._run_status["job_identifier"],
			"run_identifier": self._run_status["run_identifier"],
			"environment": self._run_status["environment"],
			"parameters": self._run_status["parameters"],
			"results": results,
			"result_file_path": os.path.relpath(result_file_path, self._run_status["workspace"]),
		}

		try:
			return [ argument.format(**format_parameters) for argument in command ]
		except KeyError:
			with open(log_file_path, mode = "w", encoding = "utf-8") as log_file:
				log_file.write("# Workspace: %s\n" % os.path.abspath(self._run_status["workspace"]))
				log_file.write("# Command: %s\n" % " ".join(command))
				log_file.write("\n")
				log_file.write("Exception while formatting the step command\n")
				log_file.write("\n")
				log_file.write(traceback.format_exc())
			raise


	def _execute_command(self, command: List[str], log_file_path: str) -> None:
		with open(log_file_path, mode = "w", encoding = "utf-8") as log_file:
			log_file.write("# Workspace: %s\n" % os.path.abspath(self._run_status["workspace"]))
			log_file.write("# Command: %s\n" % " ".join(command))
			log_file.write("\n")
			log_file.flush()

			executor_directory = os.getcwd()
			os.chdir(self._run_status["workspace"])

			try:
				child_process = subprocess.Popen(command, stdout = log_file, stderr = subprocess.STDOUT, creationflags = subprocess_flags)
			finally:
				os.chdir(executor_directory)

			return self._wait_process(child_process)


	def _wait_process(self, child_process: subprocess.Popen) -> str:
		result = None
		while result is None:
			if self._should_shutdown:
				logger.info("(%s) Terminating child process", self.run_identifier)
				os.kill(child_process.pid, shutdown_signal)
				try:
					result = child_process.wait(timeout = self.termination_timeout_seconds)
				except subprocess.TimeoutExpired:
					logger.warning("(%s) Terminating child process (force)", self.run_identifier)
					child_process.kill()
				return "aborted"
			time.sleep(1)
			result = child_process.poll()
		return "succeeded" if result == 0 else "failed"
