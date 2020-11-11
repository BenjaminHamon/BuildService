import io
import logging
import os
import time
import uuid
import zipfile

from typing import List, Optional, Tuple

from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.database.data_storage import DataStorage
from bhamon_orchestra_model.date_time_provider import DateTimeProvider
from bhamon_orchestra_model.serialization.iserializer import ISerializer


logger = logging.getLogger("RunProvider")


class RunProvider:


	def __init__(self, data_storage: DataStorage, date_time_provider: DateTimeProvider, serializer: ISerializer) -> None:
		self.data_storage = data_storage
		self.date_time_provider = date_time_provider
		self.serializer = serializer
		self.table = "run"


	def count(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: Optional[str] = None, job: Optional[str] = None, worker: Optional[str] = None, status: Optional[str] = None) -> int:

		filter = { "project": project, "job": job, "worker": worker, "status": status } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.count(self.table, filter)


	def get_list(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: Optional[str] = None, job: Optional[str] = None, worker: Optional[str] = None, status: Optional[str] = None,
			skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:

		filter = { "project": project, "job": job, "worker": worker, "status": status } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		run_collection = database_client.find_many(self.table, filter, skip = skip, limit = limit, order_by = order_by)
		return [ self.convert_to_public(run) for run in run_collection ]


	def get_list_as_documents(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: Optional[str] = None, job: Optional[str] = None, worker: Optional[str] = None, status: Optional[str] = None,
			skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:

		filter = { "project": project, "job": job, "worker": worker, "status": status } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return database_client.find_many(self.table, filter, skip = skip, limit = limit, order_by = order_by)


	def get(self, database_client: DatabaseClient, project: str, run_identifier: str) -> Optional[dict]:
		run = database_client.find_one(self.table, { "project": project, "identifier": run_identifier })
		return self.convert_to_public(run) if run is not None else None


	def create(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: str, job: str, parameters: dict, source: dict) -> dict:
		now = self.date_time_provider.now()

		run = {
			"identifier": str(uuid.uuid4()),
			"project": project,
			"job": job,
			"parameters": parameters,
			"source": source,
			"worker": None,
			"status": "pending",
			"steps": None,
			"start_date": None,
			"completion_date": None,
			"results": None,
			"should_cancel": False,
			"should_abort": False,
			"creation_date": now,
			"update_date": now,
		}

		database_client.insert_one(self.table, run)
		return run


	def update_status(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			run: dict, worker: Optional[str] = None, status: Optional[str] = None,
			start_date: Optional[str] = None, completion_date: Optional[str] = None,
			should_cancel: Optional[bool] = None, should_abort: Optional[bool] = None) -> None:

		now = self.date_time_provider.now()

		update_data = {
			"worker": worker,
			"status": status,
			"start_date": start_date,
			"completion_date": completion_date,
			"should_cancel": should_cancel,
			"should_abort": should_abort,
			"update_date": now,
		}

		update_data = { key: value for key, value in update_data.items() if value is not None }

		run.update(update_data)
		database_client.update_one(self.table, { "project": run["project"], "identifier": run["identifier"] }, update_data)


	def get_all_steps(self, database_client: DatabaseClient, project: str, run_identifier: str) -> List[dict]:
		return database_client.find_one(self.table, { "project": project, "identifier": run_identifier })["steps"]


	def get_step(self, database_client: DatabaseClient, project: str, run_identifier: str, step_index: int) -> dict:
		return database_client.find_one(self.table, { "project": project, "identifier": run_identifier })["steps"][step_index]


	def update_steps(self, database_client: DatabaseClient, run: dict, step_collection: List[dict]) -> None:
		now = self.date_time_provider.now()

		update_data = {
			"steps": step_collection,
			"update_date": now,
		}

		run.update(update_data)
		database_client.update_one(self.table, { "project": run["project"], "identifier": run["identifier"] }, update_data)


	def _get_step_log_key(self, database_client: DatabaseClient, project: str, run_identifier: str, step_index: int) -> str:
		run_step = self.get_step(database_client, project, run_identifier, step_index) # pylint: disable = possibly-unused-variable
		return "projects/{project}/runs/{run_identifier}/step_{run_step[index]}_{run_step[name]}.log".format(**locals())


	def has_step_log(self, database_client: DatabaseClient, project: str, run_identifier: str, step_index: int) -> bool:
		return self.data_storage.exists(self._get_step_log_key(database_client, project, run_identifier, step_index))


	def get_step_log(self, database_client: DatabaseClient, project: str, run_identifier: str, step_index: int) -> Tuple[str,int]:
		key = self._get_step_log_key(database_client, project, run_identifier, step_index)
		raw_data = self.data_storage.get(key)
		text_data = raw_data.decode("utf-8") if raw_data is not None else ""
		return text_data, len(raw_data) if raw_data is not None else 0


	def get_step_log_chunk(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: str, run_identifier: str, step_index: int, skip: int = 0, limit: Optional[int] = None) -> Tuple[str,int]:
		key = self._get_step_log_key(database_client, project, run_identifier, step_index)
		raw_data = self.data_storage.get_chunk(key, skip = skip, limit = limit)
		text_data = raw_data.decode("utf-8") if raw_data is not None else ""
		return text_data, (len(raw_data) if raw_data is not None else 0) + skip


	def get_step_log_size(self, database_client: DatabaseClient, project: str, run_identifier: str, step_index: int) -> int:
		return self.data_storage.get_size(self._get_step_log_key(database_client, project, run_identifier, step_index))


	def append_step_log(self, database_client: DatabaseClient, # pylint: disable = too-many-arguments
			project: str, run_identifier: str, step_index: int, log_text: str) -> None:
		self.data_storage.append(self._get_step_log_key(database_client, project, run_identifier, step_index), log_text.encode("utf-8"))


	def get_results(self, database_client: DatabaseClient, project: str, run_identifier: str) -> dict:
		return database_client.find_one(self.table, { "project": project, "identifier": run_identifier })["results"]


	def set_results(self, database_client: DatabaseClient, run: dict, results: dict) -> None:
		now = self.date_time_provider.now()

		update_data = {
			"results": results,
			"update_date": now,
		}

		run.update(update_data)
		database_client.update_one(self.table, { "project": run["project"], "identifier": run["identifier"] }, update_data)


	def get_archive(self, database_client: DatabaseClient, project: str, run_identifier: str) -> dict:
		run = database_client.find_one(self.table, { "project": project, "identifier": run_identifier })
		if run is None:
			return None

		file_name = run_identifier + ".zip"
		now = time.gmtime()

		with io.BytesIO() as file_object:
			with zipfile.ZipFile(file_object, mode = "w", compression = zipfile.ZIP_DEFLATED) as archive:
				entry_info = zipfile.ZipInfo("run" + self.serializer.get_file_extension(), now[0:6])
				entry_info.external_attr = 0o644 << 16
				archive.writestr(entry_info, self.serializer.serialize_to_string(run))

				if run["steps"] is not None:
					for step in run["steps"]:
						log_key = self._get_step_log_key(database_client, project, run_identifier, step["index"])
						log_data = self.data_storage.get(log_key)

						if log_data is not None:
							entry_info = zipfile.ZipInfo(os.path.basename(log_key), now[0:6])
							entry_info.external_attr = 0o644 << 16
							archive.writestr(entry_info, self.data_storage.get(log_key))

			return { "file_name": file_name, "data": file_object.getvalue(), "type": "zip" }


	def convert_to_public(self, run: dict) -> dict: # pylint: disable = no-self-use
		keys_to_return = [
			"identifier", "project", "job", "worker", "parameters", "source", "status",
			"start_date", "completion_date", "should_cancel", "should_abort", "creation_date", "update_date",
		]

		return { key: value for key, value in run.items() if key in keys_to_return }
