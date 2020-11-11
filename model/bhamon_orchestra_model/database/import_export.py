import logging
import os

from typing import List

from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.serialization.iserializer import ISerializer


logger = logging.getLogger("Database")


def import_database(database_client: DatabaseClient, serializer: ISerializer, source_directory: str, simulate: bool = False) -> None:
	logger.info("Importing database")

	if not os.path.exists(source_directory):
		raise ValueError("Source directory does not exist: '%s'" % source_directory)

	all_tables = []
	all_tables += [ "user", "user_authentication" ]
	all_tables += [ "project", "job", "run", "schedule", "worker" ]

	check_if_empty(database_client, all_tables)

	for table in all_tables:
		import_table(database_client, serializer, table, source_directory, simulate = simulate)


def check_if_empty(database_client: DatabaseClient, all_tables: List[str]) -> None:
	is_empty = True

	for table in all_tables:
		if database_client.find_one(table, {}) is not None:
			is_empty = False
			logger.error("Table '%s' is not empty", table)

	if not is_empty:
		raise ValueError("Database is not empty")


def import_table(database_client: DatabaseClient, serializer: ISerializer, table: str, source_directory: str, simulate: bool = False) -> None:
	logger.info("Importing table '%s'", table)

	source_file_path = os.path.join(source_directory, table + serializer.get_file_extension())
	dataset = serializer.deserialize_from_file(source_file_path)

	if not simulate:
		if len(dataset) > 0:
			database_client.insert_many(table, dataset)


def export_database(database_client: DatabaseClient, serializer: ISerializer, output_directory: str, simulate: bool = False) -> None:
	logger.info("Exporting database")

	if os.path.exists(output_directory):
		raise ValueError("Output directory already exists: '%s'" % output_directory)

	if not simulate:
		os.makedirs(output_directory)

	all_tables = [ "project", "job", "schedule", "run", "worker" ]
	all_tables += [ "user", "user_authentication" ]

	for table in all_tables:
		export_table(database_client, serializer, table, output_directory, simulate = simulate)


def export_table(database_client: DatabaseClient, serializer: ISerializer, table: str, output_directory: str, simulate: bool = False) -> None:
	logger.info("Exporting table '%s'", table)

	dataset = database_client.find_many(table, {})
	output_file_path = os.path.join(output_directory, table + serializer.get_file_extension())

	if not simulate:
		serializer.serialize_to_file(output_file_path, dataset)
