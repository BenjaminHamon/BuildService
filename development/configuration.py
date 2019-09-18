import datetime
import glob
import importlib
import os
import subprocess
import sys


def load_configuration(environment):
	configuration = {
		"project": "bhamon-build",
		"project_name": "Build Service",
		"project_version": { "identifier": "1.0" },
	}

	branch = subprocess.check_output([ environment["git_executable"], "rev-parse", "--abbrev-ref", "HEAD" ]).decode("utf-8").strip()
	revision = subprocess.check_output([ environment["git_executable"], "rev-parse", "--short=10", "HEAD" ]).decode("utf-8").strip()
	revision_date = int(subprocess.check_output([ environment["git_executable"], "show", "--no-patch", "--format=%ct", revision ]).decode("utf-8").strip())
	revision_date = datetime.datetime.utcfromtimestamp(revision_date).replace(microsecond = 0).isoformat() + "Z"

	configuration["project_version"]["branch"] = branch
	configuration["project_version"]["revision"] = revision
	configuration["project_version"]["date"] = revision_date
	configuration["project_version"]["numeric"] = "{identifier}".format(**configuration["project_version"])
	configuration["project_version"]["full"] = "{identifier}+{revision}".format(**configuration["project_version"])

	configuration["author"] = "Benjamin Hamon"
	configuration["author_email"] = "hamon.benjamin@gmail.com"
	configuration["project_url"] = "https://github.com/BenjaminHamon/BuildService"
	configuration["copyright"] = "Copyright (c) 2019 Benjamin Hamon"

	configuration["development_toolkit"] = "git+https://github.com/BenjaminHamon/DevelopmentToolkit@{revision}#subdirectory=toolkit"
	configuration["development_toolkit_revision"] = "ccaa3b07938c45f0700c277f5a079dcf02bd79fa"
	configuration["development_dependencies"] = [ "pylint", "pymongo", "pytest", "pytest-asyncio", "pytest-json", "wheel" ]

	configuration["components"] = [
		{ "name": "bhamon-build-cli", "path": "cli", "packages": [ "bhamon_build_cli" ] },
		{ "name": "bhamon-build-master", "path": "master", "packages": [ "bhamon_build_master" ] },
		{ "name": "bhamon-build-model", "path": "model", "packages": [ "bhamon_build_model" ] },
		{ "name": "bhamon-build-service", "path": "service", "packages": [ "bhamon_build_service" ] },
		{ "name": "bhamon-build-website", "path": "website", "packages": [ "bhamon_build_website" ] },
		{ "name": "bhamon-build-worker", "path": "worker", "packages": [ "bhamon_build_worker" ] },
	]

	configuration["project_identifier_for_artifact_server"] = "BuildService"

	configuration["filesets"] = {
		"distribution": {
			"path_in_workspace": os.path.join(".artifacts", "distributions", "{component}"),
			"file_functions": [ _list_distribution_files ],
		},
	}

	configuration["artifacts"] = {
		"package": {
			"file_name": "{project}_{version}_package",
			"installation_directory": ".artifacts/distributions",
			"path_in_repository": "packages",
			"filesets": [
				{ "identifier": "distribution", "path_in_archive": "bhamon-build-cli", "parameters": { "component": "bhamon-build-cli" } },
				{ "identifier": "distribution", "path_in_archive": "bhamon-build-master", "parameters": { "component": "bhamon-build-master" } },
				{ "identifier": "distribution", "path_in_archive": "bhamon-build-model", "parameters": { "component": "bhamon-build-model" } },
				{ "identifier": "distribution", "path_in_archive": "bhamon-build-service", "parameters": { "component": "bhamon-build-service" } },
				{ "identifier": "distribution", "path_in_archive": "bhamon-build-website", "parameters": { "component": "bhamon-build-website" } },
				{ "identifier": "distribution", "path_in_archive": "bhamon-build-worker", "parameters": { "component": "bhamon-build-worker" } },
			],
		},
	}

	return configuration


def get_setuptools_parameters(configuration):
	return {
		"version": configuration["project_version"]["full"],
		"author": configuration["author"],
		"author_email": configuration["author_email"],
		"url": configuration["project_url"],
	}


def list_package_data(package, pattern_collection):
	all_files = []
	for pattern in pattern_collection:
		all_files += glob.glob(package + "/" + pattern, recursive = True)
	return [ os.path.relpath(path, package) for path in all_files ]


def load_commands():
	all_modules = [
		"development.commands.artifact",
		"development.commands.clean",
		"development.commands.develop",
		"development.commands.distribute",
		"development.commands.lint",
		"development.commands.release",
		"development.commands.test",
	]

	return [ import_command(module) for module in all_modules ]


def import_command(module_name):
	try:
		return {
			"module_name": module_name,
			"module": importlib.import_module(module_name),
		}

	except ImportError:
		return {
			"module_name": module_name,
			"exception": sys.exc_info(),
		}


def _list_distribution_files(path_in_workspace, parameters):
	archive_name = "{component}-{version}-py3-none-any.whl"
	archive_name = archive_name.format(component = parameters["component"].replace("-", "_"), version = parameters["version"])
	return [ os.path.join(path_in_workspace, archive_name) ]