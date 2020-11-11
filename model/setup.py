import os
import sys

import setuptools

sys.path.insert(0, os.path.join(sys.path[0], ".."))

import development.configuration # pylint: disable = import-error, wrong-import-position
import development.environment # pylint: disable = import-error, wrong-import-position


environment_instance = development.environment.load_environment()
configuration_instance = development.configuration.load_configuration(environment_instance)
parameters = development.configuration.get_setuptools_parameters(configuration_instance)


parameters.update({
	"name": "bhamon-orchestra-model",
	"description": "Model library for Job Orchestra",

	"packages": [
		"bhamon_orchestra_model",
		"bhamon_orchestra_model/database",
		"bhamon_orchestra_model/network",
		"bhamon_orchestra_model/revision_control",
		"bhamon_orchestra_model/serialization",
	],

	"python_requires": "~= 3.7",
	"install_requires": [ "filelock ~= 3.0", "python-dateutil ~= 2.8" ],
})

setuptools.setup(**parameters)
