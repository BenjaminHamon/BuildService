import logging

from typing import List, Optional, Tuple

from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.date_time_provider import DateTimeProvider
from bhamon_orchestra_model.run_provider import RunProvider


logger = logging.getLogger("WorkerProvider")


class WorkerProvider:


	def __init__(self, date_time_provider: DateTimeProvider) -> None:
		self.date_time_provider = date_time_provider
		self.table = "worker"


	def count(self, database_client: DatabaseClient, owner: Optional[str] = None) -> int:
		filter = { "owner": owner } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.count(self.table, filter)


	def get_list(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			owner: Optional[str] = None, skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:

		filter = { "owner": owner } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.find_many(self.table, filter, skip = skip, limit = limit, order_by = order_by)


	def get(self, database_client: DatabaseClient, worker_identifier: str) -> Optional[dict]:
		return database_client.find_one(self.table, { "identifier": worker_identifier })


	def create(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			worker_identifier: str, owner: str, version: str, display_name: str) -> dict:

		now = self.date_time_provider.now()

		worker = {
			"identifier": worker_identifier,
			"owner": owner,
			"version": version,
			"display_name": display_name,
			"properties": {},
			"is_enabled": True,
			"is_active": False,
			"should_disconnect": False,
			"creation_date": now,
			"update_date": now,
		}

		database_client.insert_one(self.table, worker)
		return worker


	def update_status(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			worker: dict, is_active: Optional[bool] = None, is_enabled: Optional[bool] = None, should_disconnect: Optional[bool] = None) -> None:

		now = self.date_time_provider.now()

		update_data = {
			"is_active": is_active,
			"is_enabled": is_enabled,
			"should_disconnect": should_disconnect,
			"update_date": now,
		}

		update_data = { key: value for key, value in update_data.items() if value is not None }

		worker.update(update_data)
		database_client.update_one(self.table, { "identifier": worker["identifier"] }, update_data)


	def update_properties(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			worker: dict, version: Optional[str] = None, display_name: Optional[str] = None, properties: Optional[dict] = None) -> None:

		now = self.date_time_provider.now()

		update_data = {
			"version": version,
			"display_name": display_name,
			"properties": properties,
			"update_date": now,
		}

		update_data = { key: value for key, value in update_data.items() if value is not None }

		worker.update(update_data)
		database_client.update_one(self.table, { "identifier": worker["identifier"] }, update_data)


	def delete(self, database_client: DatabaseClient, worker_identifier: str, run_provider: RunProvider) -> None:
		worker_record = self.get(database_client, worker_identifier)
		if worker_record is None:
			raise ValueError("Worker '%s' does not exist" % worker_identifier)

		if worker_record["is_enabled"]:
			raise ValueError("Worker '%s' is enabled" % worker_identifier)
		if worker_record["is_active"]:
			raise ValueError("Worker '%s' is active" % worker_identifier)

		if run_provider.count(worker = worker_identifier, status = "pending") > 0:
			raise ValueError("Worker '%s' has pending runs" % worker_identifier)
		if run_provider.count(worker = worker_identifier, status = "running") > 0:
			raise ValueError("Worker '%s' has running runs" % worker_identifier)

		database_client.delete_one(self.table, { "identifier": worker_identifier })
