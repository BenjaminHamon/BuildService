import os
import signal
import subprocess
import sys
import time

import bhamon_build_model.build_provider as build_provider
import bhamon_build_model.file_storage as file_storage
import bhamon_build_model.job_provider as job_provider
import bhamon_build_model.json_database_client as json_database_client
import bhamon_build_model.task_provider as task_provider
import bhamon_build_model.worker_provider as worker_provider


class Context:


	def __init__(self, temporary_directory):
		self.temporary_directory = temporary_directory
		self.master_address = "localhost"
		self.master_port = 8765
		self.service_address = "localhost"
		self.service_port = 5100
		self.process_collection = []


	def __enter__(self):
		return self


	def __exit__(self, exception_type, exception_value, traceback):
		for process in self.process_collection:
			os.kill(process.pid, signal.CTRL_BREAK_EVENT)
			try:
				process.wait(5)
			except subprocess.TimeoutExpired:
				process.kill()
		self.process_collection.clear()


	def invoke_master(self):
		return self.invoke(
			script = "master_main.py",
			arguments = [ "--address", self.master_address, "--port", str(self.master_port) ],
			workspace = os.path.join(self.temporary_directory, "master"),
		)


	def invoke_worker(self, identifier):
		return self.invoke(
			script = "worker_main.py",
			arguments = [ "--identifier", identifier, "--master-uri", "ws://%s:%s" % (self.master_address, self.master_port) ],
			workspace = os.path.join(self.temporary_directory, identifier),
		)


	def invoke_service(self):
		return self.invoke(
			script = "service_main.py",
			arguments = [ "--address", self.service_address, "--port", str(self.service_port) ],
			workspace = os.path.join(self.temporary_directory, "master"),
		)


	def invoke(self, script, arguments, workspace):
		script_root = os.path.dirname(os.path.realpath(__file__))
		command = [ sys.executable, os.path.join(script_root, script) ] + arguments

		os.makedirs(workspace, exist_ok = True)

		process = subprocess.Popen(
			command,
			cwd = workspace,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,
			creationflags = subprocess.CREATE_NEW_PROCESS_GROUP,
		)

		self.process_collection.append(process)

		time.sleep(1) # Wait for initialization

		return process


def instantiate_providers(temporary_directory):
	database_client_instance = json_database_client.JsonDatabaseClient(os.path.join(temporary_directory, "master"))
	file_storage_instance = file_storage.FileStorage(os.path.join(temporary_directory, "master"))

	return {
		"build": build_provider.BuildProvider(database_client_instance, file_storage_instance),
		"job": job_provider.JobProvider(database_client_instance),
		"task": task_provider.TaskProvider(database_client_instance),
		"worker": worker_provider.WorkerProvider(database_client_instance),
	}