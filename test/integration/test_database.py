""" Integration tests for database clients """

import os

import pytest

import bhamon_orchestra_model.database.import_export as database_import_export

from . import context
from . import environment


@pytest.mark.parametrize("database_type", environment.get_all_database_types())
def test_single(tmpdir, database_type):
	""" Test database operations with a single record """

	table = "record"
	record = { "id": 1, "key": "value" }

	with context.DatabaseContext(tmpdir, database_type) as context_instance:
		assert context_instance.database_client.count(table, {}) == 0

		context_instance.database_client.insert_one(table, record)
		assert context_instance.database_client.count(table, {}) == 1

		context_instance.database_client.delete_one(table, record)
		assert context_instance.database_client.count(table, {}) == 0


@pytest.mark.parametrize("database_type", environment.get_all_database_types())
def test_many(tmpdir, database_type):
	""" Test database operations with several records """

	table = "record"
	first_record = { "id": 1, "key": "first" }
	second_record = { "id": 2, "key": "second" }
	third_record = { "id": 3, "key": "third" }

	with context.DatabaseContext(tmpdir, database_type) as context_instance:
		assert context_instance.database_client.count(table, {}) == 0

		context_instance.database_client.insert_many(table, [ first_record, second_record, third_record ])
		assert context_instance.database_client.find_many(table, {}) == [ first_record, second_record, third_record ]
		assert context_instance.database_client.count(table, {}) == 3

		context_instance.database_client.delete_one(table, third_record)
		assert context_instance.database_client.find_many(table, {}) == [ first_record, second_record ]
		assert context_instance.database_client.count(table, {}) == 2


@pytest.mark.parametrize("database_type", environment.get_all_database_types())
def test_index(tmpdir, database_type):
	""" Test database operations on a table with an index """

	table = "record"
	first_record = { "id": 1, "key": "first" }
	second_record = { "id": 2, "key": "second" }
	third_record = { "id": 3, "key": "third" }

	with context.DatabaseContext(tmpdir, database_type) as context_instance:
		context_instance.database_administration.create_index(table, "id_unique", [ ("id", "ascending") ], is_unique = True)

		assert context_instance.database_client.count(table, {}) == 0

		context_instance.database_client.insert_one(table, first_record)
		assert context_instance.database_client.count(table, {}) == 1

		with pytest.raises(Exception):
			context_instance.database_client.insert_one(table, first_record)
		assert context_instance.database_client.count(table, {}) == 1

		with pytest.raises(Exception):
			context_instance.database_client.insert_many(table, [ first_record, second_record, third_record ])
		assert context_instance.database_client.count(table, {}) == 1


@pytest.mark.parametrize("database_type_source", environment.get_all_database_types())
@pytest.mark.parametrize("database_type_target", environment.get_all_database_types())
def test_import_export(tmpdir, database_type_source, database_type_target):
	""" Test exporting and re-importing a database """

	intermediate_directory = os.path.join(str(tmpdir), "export")

	with context.OrchestraContext(tmpdir, database_type_source, "source") as context_instance:
		context_instance.project_provider.create_or_update("my-project", None, None)
		context_instance.job_provider.create_or_update("my-job", "my-project", None, None, None, None, None, None)
		run = context_instance.run_provider.create("my-project", "my-job", None, None)

		database_import_export.export_database(context_instance.database_client, intermediate_directory)

	with context.OrchestraContext(tmpdir, database_type_target, "target") as context_instance:
		database_import_export.import_database(context_instance.database_client, intermediate_directory)

		assert len(context_instance.project_provider.get_list()) == 1
		assert context_instance.project_provider.get_list()[0]["identifier"] == "my-project"
		assert len(context_instance.job_provider.get_list()) == 1
		assert context_instance.job_provider.get_list()[0]["identifier"] == "my-job"
		assert len(context_instance.run_provider.get_list()) == 1
		assert context_instance.run_provider.get_list()[0]["identifier"] == run["identifier"]
