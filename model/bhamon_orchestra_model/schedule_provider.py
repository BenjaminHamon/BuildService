import logging

from typing import List, Optional, Tuple

from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.date_time_provider import DateTimeProvider


logger = logging.getLogger("ScheduleProvider")


class ScheduleProvider:


	def __init__(self, date_time_provider: DateTimeProvider) -> None:
		self.date_time_provider = date_time_provider
		self.table = "schedule"


	def count(self, database_client: DatabaseClient, project: Optional[str] = None, job: Optional[str] = None) -> int:
		filter = { "project": project, "job": job } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.count(self.table, filter)


	def get_list(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: Optional[str] = None, job: Optional[str] = None,
			skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:

		filter = { "project": project, "job": job } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.find_many(self.table, filter, skip = skip, limit = limit, order_by = order_by)


	def get(self, database_client: DatabaseClient, project: str, schedule_identifier: str) -> Optional[dict]:
		return database_client.find_one(self.table, { "project": project, "identifier": schedule_identifier })


	def create_or_update(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			schedule_identifier: str, project: str, display_name: str, job: str, parameters: dict, expression: str) -> dict:

		now = self.date_time_provider.now()
		schedule = self.get(database_client, project, schedule_identifier)

		if schedule is None:
			schedule = {
				"project": project,
				"identifier": schedule_identifier,
				"display_name": display_name,
				"job": job,
				"parameters": parameters,
				"expression": expression,
				"is_enabled": False,
				"last_run": None,
				"creation_date": now,
				"update_date": now,
			}

			database_client.insert_one(self.table, schedule)

		else:
			update_data = {
				"display_name": display_name,
				"job": job,
				"parameters": parameters,
				"expression": expression,
				"update_date": now,
			}

			schedule.update(update_data)
			database_client.update_one(self.table, { "project": project, "identifier": schedule_identifier }, update_data)

		return schedule


	def update_status(self, database_client: DatabaseClient,
			schedule: dict, is_enabled: Optional[bool] = None, last_run: Optional[str] = None) -> None:

		now = self.date_time_provider.now()

		update_data = {
			"is_enabled": is_enabled,
			"last_run": last_run,
			"update_date": now,
		}

		update_data = { key: value for key, value in update_data.items() if value is not None }

		schedule.update(update_data)
		database_client.update_one(self.table, { "project": schedule["project"], "identifier": schedule["identifier"] }, update_data)


	def delete(self, database_client: DatabaseClient, project: str, schedule_identifier: str) -> None:
		database_client.delete_one(self.table, { "project": project, "identifier": schedule_identifier })
