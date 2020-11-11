import logging
import os
from typing import List, Tuple

from bhamon_orchestra_model.serialization.json_serializer import JsonSerializer


logger = logging.getLogger("JsonDatabaseAdministration")


class JsonDatabaseAdministration:
	""" Administration client for a database storing data as json files, intended for development only. """


	def __init__(self, serializer: JsonSerializer, data_directory: str) -> None:
		self.serializer = serializer
		self._data_directory = data_directory


	def __enter__(self):
		return self


	def __exit__(self, exception_type, exception_value, traceback):
		self.close()


	def initialize(self, simulate: bool = False) -> None:
		logger.info("Initializing (Path: '%s')" + (" (simulation)" if simulate else ""), self._data_directory) # pylint: disable = logging-not-lazy

		logger.info("Creating run index")
		if not simulate:
			self.create_index("run", "identifier_unique", [ ("project", "ascending"), ("identifier", "ascending") ], is_unique = True)

		logger.info("Creating job index")
		if not simulate:
			self.create_index("job", "identifier_unique", [ ("project", "ascending"), ("identifier", "ascending") ], is_unique = True)

		logger.info("Creating schedule index")
		if not simulate:
			self.create_index("schedule", "identifier_unique", [ ("project", "ascending"), ("identifier", "ascending") ], is_unique = True)

		logger.info("Creating user index")
		if not simulate:
			self.create_index("user", "identifier_unique", [ ("identifier", "ascending") ], is_unique = True)

		logger.info("Creating worker index")
		if not simulate:
			self.create_index("worker", "identifier_unique", [ ("identifier", "ascending") ], is_unique = True)


	def upgrade(self, simulate: bool = False) -> None:
		raise NotImplementedError("Upgrading a JSON database is not supported")


	def create_index(self, table: str, identifier: str, field_collection: List[Tuple[str,str]], is_unique: bool = False) -> None:
		field_collection = [ field for field, direction in field_collection ]

		administration_data = self._load()

		existing_index = next(( index for index in administration_data["indexes"] if index["table"] == table and index["identifier"] == identifier ), None)
		if existing_index is not None:
			raise ValueError("Index '%s' already exists for table '%s'" % (identifier, table))

		administration_data["indexes"].append(
			{
				"table": table,
				"identifier": identifier,
				"field_collection": field_collection,
				"is_unique": is_unique,
			}
		)

		self._save(administration_data)


	def close(self) -> None:
		pass


	def _load(self) -> dict:
		file_path = os.path.join(self._data_directory, "admin.json")

		administration_data = None

		try:
			administration_data = self.serializer.deserialize_from_file(file_path)
		except FileNotFoundError:
			pass

		if administration_data is None:
			administration_data = { "indexes": [] }
		return administration_data


	def _save(self, administration_data: dict) -> None:
		file_path = os.path.join(self._data_directory, "admin.json")
		if not os.path.exists(os.path.dirname(file_path)):
			os.makedirs(os.path.dirname(file_path))
		self.serializer.serialize_to_file(file_path, administration_data)
