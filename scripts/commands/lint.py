import logging
import subprocess


logger = logging.getLogger("Main")


def configure_argument_parser(environment, configuration, subparsers): # pylint: disable = unused-argument
	return subparsers.add_parser("lint", help = "run linter")


def run(environment, configuration, arguments): # pylint: disable = unused-argument
	lint(environment["python3_executable"], configuration["components"])


def lint(python_executable, component_collection):
	logger.info("Running linter")

	pylint_command = [ python_executable, "-m", "pylint" ]
	pylint_command += [ component["path"] for component in component_collection ] + [ "test" ]

	logger.info("+ %s", " ".join(pylint_command))
	subprocess.check_call(pylint_command)
