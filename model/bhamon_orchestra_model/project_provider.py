import logging

from typing import List, Optional, Tuple

from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.date_time_provider import DateTimeProvider


logger = logging.getLogger("ProjectProvider")


class ProjectProvider:


	def __init__(self, date_time_provider: DateTimeProvider) -> None:
		self.date_time_provider = date_time_provider
		self.table = "project"


	def count(self, database_client: DatabaseClient) -> int:
		return database_client.count(self.table, {})


	def get_list(self, database_client: DatabaseClient,
			skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:
		return database_client.find_many(self.table, {}, skip = skip, limit = limit, order_by = order_by)


	def get(self, database_client: DatabaseClient, project_identifier: str) -> Optional[dict]:
		return database_client.find_one(self.table, { "identifier": project_identifier })


	def create_or_update(self, database_client: DatabaseClient, project_identifier: str, display_name: str, services: dict) -> dict:
		now = self.date_time_provider.now()
		project = self.get(database_client, project_identifier)

		if project is None:
			project = {
				"identifier": project_identifier,
				"display_name": display_name,
				"services": services,
				"creation_date": now,
				"update_date": now,
			}

			database_client.insert_one(self.table, project)

		else:
			update_data = {
				"display_name": display_name,
				"services": services,
				"update_date": now,
			}

			project.update(update_data)
			database_client.update_one(self.table, { "identifier": project_identifier }, update_data)

		return project
