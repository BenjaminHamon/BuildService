import argparse
import copy
import filecmp
import glob
import logging
import os

import bhamon_development_toolkit.artifacts
import bhamon_development_toolkit.workspace


logger = logging.getLogger("Main")


def configure_argument_parser(environment, configuration, subparsers): # pylint: disable = unused-argument

	available_commands = [ "show", "package", "verify", "upload", "download", "install" ]

	def parse_command_parameter(argument_value):
		command_list = argument_value.split("+")
		for command in command_list:
			if command not in available_commands:
				raise argparse.ArgumentTypeError("invalid artifact command: '%s'" % command)
		return command_list

	def parse_key_value_parameter(argument_value):
		key_value = argument_value.split("=")
		if len(key_value) != 2:
			raise argparse.ArgumentTypeError("invalid key value parameter: '%s'" % argument_value)
		return (key_value[0], key_value[1])

	parser = subparsers.add_parser("artifact",
		help = "execute commands related to build artifacts")
	parser.add_argument("artifact_commands", type = parse_command_parameter,
		metavar = "<command[+command]>", help = "set the command(s) to execute for the artifact, separated by '+' (%s)" % ", ".join(available_commands))
	parser.add_argument("artifact", choices = configuration["artifacts"].keys(),
		metavar = "<artifact>", help = "set an artifact definition to use for the commands")
	parser.add_argument("--installation-directory",
		help = "set the installation directory")
	parser.add_argument("--parameters", nargs = "*", type = parse_key_value_parameter, default = [],
		metavar = "<key=value>", help = "set parameters for the artifact")
	parser.add_argument("--overwrite", action = "store_true",
		help = "overwrite existing artifact on upload")
	return parser


def run(environment, configuration, arguments): # pylint: disable = unused-argument
	parameters = {
		"project": configuration["project"],
		"version": configuration["project_version"]["full"],
	}

	parameters.update(arguments.parameters)

	artifact = configuration["artifacts"][arguments.artifact]
	artifact_name = artifact["file_name"].format(**parameters)

	artifact_repository = bhamon_development_toolkit.artifacts.ArtifactRepository(".artifacts", configuration["project_identifier_for_artifact_server"])
	if environment.get("artifact_server_url", None) is not None:
		artifact_server_url = environment["artifact_server_url"]
		artifact_server_parameters = environment.get("artifact_server_parameters", {})
		artifact_repository.server_client = bhamon_development_toolkit.artifacts.create_artifact_server_client(artifact_server_url, artifact_server_parameters, environment)

	if "upload" in arguments.artifact_commands and artifact_repository.server_client is None:
		raise ValueError("Upload command requires an artifact server")

	if "show" in arguments.artifact_commands:
		artifact_files = list_artifact_files(artifact, configuration, parameters)
		artifact_repository.show(artifact_name, artifact_files)
		print("")

	if "package" in arguments.artifact_commands:
		artifact_files = merge_artifact_mapping(map_artifact_files(artifact, configuration, parameters))
		artifact_repository.package(artifact["path_in_repository"], artifact_name, artifact_files, arguments.simulate)
		print("")
	if "verify" in arguments.artifact_commands:
		artifact_repository.verify(artifact["path_in_repository"], artifact_name, arguments.simulate)
		print("")
	if "upload" in arguments.artifact_commands:
		artifact_repository.upload(artifact["path_in_repository"], artifact_name, arguments.overwrite, arguments.simulate)
		save_upload_results(artifact_name, arguments.artifact, arguments.results, arguments.simulate)
		print("")

	if "download" in arguments.artifact_commands:
		artifact_repository.download(artifact["path_in_repository"], artifact_name, arguments.simulate)
		print("")
	if "install" in arguments.artifact_commands:
		installation_directory = arguments.installation_directory if arguments.installation_directory else artifact["installation_directory"]
		artifact_repository.install(artifact["path_in_repository"], artifact_name, installation_directory, arguments.simulate)
		print("")


def save_upload_results(artifact_name, artifact_type, result_file_path, simulate):
	artifact_information = {
		"name": artifact_name,
		"type": artifact_type,
	}

	if result_file_path:
		results = bhamon_development_toolkit.workspace.load_results(result_file_path)
		results["artifacts"] = results.get("artifacts", [])
		results["artifacts"].append(artifact_information)
		if not simulate:
			bhamon_development_toolkit.workspace.save_results(result_file_path, results)


def list_artifact_files(artifact, configuration, parameters):
	all_files = []

	for fileset_options in artifact["filesets"]:
		fileset = configuration["filesets"][fileset_options["identifier"]]
		fileset_parameters = copy.deepcopy(fileset_options.get("parameters", {}))
		fileset_parameters.update(parameters)

		all_files += load_fileset(fileset, fileset_parameters)

	all_files.sort()

	return all_files


def map_artifact_files(artifact, configuration, parameters):
	all_files = []

	for fileset_options in artifact["filesets"]:
		fileset = configuration["filesets"][fileset_options["identifier"]]
		fileset_parameters = copy.deepcopy(fileset_options.get("parameters", {}))
		fileset_parameters.update(parameters)

		path_in_workspace = fileset["path_in_workspace"].format(**fileset_parameters)
		for source in load_fileset(fileset, fileset_parameters):
			destination = source
			if "path_in_archive" in fileset_options:
				destination = os.path.join(fileset_options["path_in_archive"], os.path.relpath(source, path_in_workspace))
			all_files.append((source, destination.replace("\\", "/")))

	all_files.sort()

	return all_files


def merge_artifact_mapping(artifact_files):
	merged_files = []
	has_conflicts = False

	for destination in set(dst for src, dst in artifact_files):
		source_collection = [ src for src, dst in artifact_files if dst == destination ]
		for source in source_collection[1:]:
			if not filecmp.cmp(source_collection[0], source):
				has_conflicts = True
				logger.error("Mapping conflict: %s, %s => %s", source_collection[0], source, destination)
		merged_files.append((source_collection[0], destination))

	if has_conflicts:
		raise ValueError("Artifact mapper has conflicts")

	merged_files.sort()

	return merged_files


def load_fileset(fileset, parameters):
	matched_files = []
	path_in_workspace = fileset["path_in_workspace"].format(**parameters)

	for file_function in fileset.get("file_functions", []):
		matched_files += file_function(path_in_workspace, parameters)
	for file_pattern in fileset.get("file_patterns", []):
		matched_files += glob.glob(os.path.join(path_in_workspace, file_pattern.format(**parameters)), recursive = True)

	selected_files = []
	for file_path in matched_files:
		file_path = file_path.replace("\\", "/")
		if os.path.isfile(file_path):
			selected_files.append(file_path)

	selected_files.sort()
	return selected_files