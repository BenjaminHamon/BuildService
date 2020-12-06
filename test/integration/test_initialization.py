""" Integration tests for initialization """

import time

import pytest

import bhamon_orchestra_master
import bhamon_orchestra_worker

from .. import assert_extensions
from . import context
from . import environment


log_format = environment.load_environment()["logging_stream_format"]


@pytest.mark.parametrize("database_type", environment.get_all_database_types())
def test_master(tmpdir, database_type):
	""" Test if the master starts successfully """

	application_title = bhamon_orchestra_master.__product__ + " " + "Master"
	application_version = bhamon_orchestra_master.__version__

	with context.OrchestraContext(tmpdir, database_type) as context_instance:
		master_process = context_instance.invoke_master()

	master_expected_messages = [
		{ "level": "Info", "logger": "Application", "message": "%s %s" % (application_title, application_version) },
		{ "level": "Info", "logger": "Supervisor", "message": "Listening for workers on '127.0.0.1:5901'" },
		{ "level": "Info", "logger": "Application", "message": "Exit with code 0" },
	]

	assert_extensions.assert_multi_process([
		{ "process": master_process, "expected_result_code": 0, "log_format": log_format, "expected_messages": master_expected_messages },
	])


@pytest.mark.parametrize("database_type", environment.get_all_database_types())
def test_worker(tmpdir, database_type):
	""" Test if the worker starts successfully """

	application_title = bhamon_orchestra_worker.__product__ + " " + "Worker"
	application_version = bhamon_orchestra_worker.__version__

	with context.OrchestraContext(tmpdir, database_type) as context_instance:
		context_instance.configure_worker_authentication([ "worker" ])
		worker_process = context_instance.invoke_worker("worker")

		time.sleep(2) # Wait for the connection to fail

	worker_expected_messages = [
		{ "level": "Info", "logger": "Application", "message": "%s %s" % (application_title, application_version) },
		{ "level": "Error", "logger": "WebSocket", "message": "Failed to connect to master" },
		{ "level": "Info", "logger": "Application", "message": "Exit with code 0" },
	]

	assert_extensions.assert_multi_process([
		{ "process": worker_process, "expected_result_code": 0, "log_format": log_format, "expected_messages": worker_expected_messages },
	])


def test_executor(tmpdir):
	""" Test if the executor starts successfully """

	run_request = {
		"project_identifier": "my_project",
		"job_identifier": "my_job",
		"run_identifier": "my_run",

		"job_definition": {
			"commands": [],
		},

		"parameters": {},
	}

	with context.OrchestraContext(tmpdir, None) as context_instance:
		executor_process = context_instance.invoke_executor("worker", run_request)

	assert_extensions.assert_multi_process([
		{ "process": executor_process, "expected_result_code": 0, "log_format": log_format, "expected_messages": [] },
	])


@pytest.mark.parametrize("database_type", environment.get_all_database_types())
def test_service(tmpdir, database_type):
	""" Test if the service starts successfully """

	with context.OrchestraContext(tmpdir, database_type) as context_instance:
		service_process = context_instance.invoke_service()

	assert_extensions.assert_multi_process([
		{ "process": service_process, "expected_result_code": assert_extensions.get_flask_exit_code(), "log_format": log_format, "expected_messages": [] },
	])


def test_website(tmpdir):
	""" Test if the website starts successfully """

	with context.OrchestraContext(tmpdir, None) as context_instance:
		website_process = context_instance.invoke_website()

	assert_extensions.assert_multi_process([
		{ "process": website_process, "expected_result_code": assert_extensions.get_flask_exit_code(), "log_format": log_format, "expected_messages": [] },
	])
