import logging

from typing import List, Optional, Tuple

from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.date_time_provider import DateTimeProvider


logger = logging.getLogger("JobProvider")


class JobProvider:


	def __init__(self,  date_time_provider: DateTimeProvider) -> None:
		self.date_time_provider = date_time_provider
		self.table = "job"


	def count(self, database_client: DatabaseClient, project: Optional[str] = None) -> int:
		filter = { "project": project } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.count(self.table, filter)


	def get_list(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: Optional[str] = None, skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:

		filter = { "project": project } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.find_many(self.table, filter, skip = skip, limit = limit, order_by = order_by)


	def get(self, database_client: DatabaseClient, project: str, job_identifier: str) -> Optional[dict]:
		return database_client.find_one(self.table, { "project": project, "identifier": job_identifier })


	def create_or_update(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			job_identifier: str, project: str, display_name: str, description: str,
			workspace: str, steps: list, parameters: list, properties: dict) -> dict:

		now = self.date_time_provider.now()
		job = self.get(database_client, project, job_identifier)

		if job is None:
			job = {
				"project": project,
				"identifier": job_identifier,
				"display_name": display_name,
				"description": description,
				"workspace": workspace,
				"steps": steps,
				"parameters": parameters,
				"properties": properties,
				"is_enabled": True,
				"creation_date": now,
				"update_date": now,
			}

			database_client.insert_one(self.table, job)

		else:
			update_data = {
				"display_name": display_name,
				"description": description,
				"workspace": workspace,
				"steps": steps,
				"parameters": parameters,
				"properties": properties,
				"update_date": now,
			}

			job.update(update_data)
			database_client.update_one(self.table, { "project": project, "identifier": job_identifier }, update_data)

		return job


	def update_status(self, database_client: DatabaseClient, job: dict, is_enabled: Optional[bool] = None) -> None:
		now = self.date_time_provider.now()

		update_data = {
			"is_enabled": is_enabled,
			"update_date": now,
		}

		update_data = { key: value for key, value in update_data.items() if value is not None }

		job.update(update_data)
		database_client.update_one(self.table, { "project": job["project"], "identifier": job["identifier"] }, update_data)


	def delete(self, database_client: DatabaseClient, project: str, job_identifier: str) -> None:
		database_client.delete_one(self.table, { "project": project, "identifier": job_identifier })
