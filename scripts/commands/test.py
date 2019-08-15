import logging
import os
import subprocess
import uuid


logger = logging.getLogger("Main")


def configure_argument_parser(environment, configuration, subparsers): # pylint: disable = unused-argument
	parser = subparsers.add_parser("test", help = "run the test suite")
	parser.add_argument("--filter", help = "specify a string expression to select tests to run")
	return parser


def run(environment, configuration, arguments): # pylint: disable = unused-argument
	test(environment, arguments.filter, arguments.simulate)


def test(environment, filter_expression, simulate):
	run_identifier = uuid.uuid4()

	logger.info("Running test suite (RunIdentifier: %s)", run_identifier)

	os.makedirs("test_results", exist_ok = True)

	pytest_command = [ environment["python3_executable"], "-m", "pytest", "test", "--verbose" ]
	pytest_command += [ "--collect-only" ] if simulate else []
	pytest_command += [ "--basetemp", os.path.join("test_results", str(run_identifier)) ]
	pytest_command += [ "--json", os.path.join("test_results", str(run_identifier) + ".json") ]
	pytest_command += [ "-k", filter_expression ] if filter_expression else []

	logger.info("+ %s", " ".join(pytest_command))
	subprocess.check_call(pytest_command)
