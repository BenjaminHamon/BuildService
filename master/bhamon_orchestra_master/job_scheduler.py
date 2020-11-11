import asyncio
import datetime
import logging

from typing import Callable, List

import pycron

from bhamon_orchestra_master.supervisor import Supervisor
from bhamon_orchestra_master.worker_selector import WorkerSelector
from bhamon_orchestra_model.date_time_provider import DateTimeProvider
from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.job_provider import JobProvider
from bhamon_orchestra_model.run_provider import RunProvider
from bhamon_orchestra_model.schedule_provider import ScheduleProvider


logger = logging.getLogger("JobScheduler")


class JobScheduler:
	""" Trigger timed schedules and dispatch pending runs to workers """


	def __init__(self, # pylint: disable = too-many-arguments
			database_client_factory: Callable[[], DatabaseClient],
			job_provider: JobProvider, run_provider: RunProvider, schedule_provider: ScheduleProvider,
			supervisor: Supervisor, worker_selector: WorkerSelector, date_time_provider: DateTimeProvider) -> None:

		self._database_client_factory = database_client_factory
		self._job_provider = job_provider
		self._run_provider = run_provider
		self._schedule_provider = schedule_provider
		self._supervisor = supervisor
		self._worker_selector = worker_selector
		self._date_time_provider = date_time_provider

		self.update_interval_seconds = 10
		self.run_expiration = datetime.timedelta(days = 1)


	async def run(self) -> None:
		""" Perform updates until cancelled """

		while True:
			try:
				with self._database_client_factory() as database_client:
					await asyncio.gather(self.update(database_client), asyncio.sleep(self.update_interval_seconds))
			except asyncio.CancelledError: # pylint: disable = try-except-raise
				raise
			except Exception: # pylint: disable = broad-except
				logger.error("Unhandled exception", exc_info = True)
				await asyncio.sleep(self.update_interval_seconds)


	async def update(self, database_client: DatabaseClient) -> None:
		""" Perform a single update """

		now = self._date_time_provider.now()

		all_active_schedules = self._list_active_schedules(database_client)

		for schedule in all_active_schedules:
			if self._should_schedule_trigger(database_client, schedule, now):
				logger.info("Triggering run for schedule '%s'", schedule["identifier"])
				source = { "type": "schedule", "identifier": schedule["identifier"] }
				run = self._run_provider.create(database_client, schedule["project"], schedule["job"], schedule["parameters"], source)
				self._schedule_provider.update_status(database_client, schedule, last_run = run["identifier"])

		all_pending_runs = self._list_pending_runs(database_client)

		for run in all_pending_runs:
			if run["should_cancel"] or now > (run["creation_date"] + self.run_expiration):
				logger.info("Cancelling run '%s'", run["identifier"])
				self._run_provider.update_status(database_client, run, status = "cancelled")
				continue

			try:
				self.trigger_run(database_client, run)
			except Exception: # pylint: disable = broad-except
				logger.error("Run trigger '%s' raised an exception", run["identifier"], exc_info = True)
				self._run_provider.update_status(database_client, run, status = "exception")

		all_active_runs = self._list_active_runs(database_client)

		for run in all_active_runs:
			if run["should_abort"]:
				self.abort_run(run)


	def _list_active_schedules(self, database_client: DatabaseClient) -> List[dict]:
		""" Retrieve all active schedules from the database """
		all_schedules = self._schedule_provider.get_list(database_client)
		all_schedules = [ schedule for schedule in all_schedules if schedule["is_enabled"] ]
		return all_schedules


	def _list_pending_runs(self, database_client: DatabaseClient) -> List[dict]:
		""" Retrieve all pending runs from the database """
		all_runs = self._run_provider.get_list(database_client, status = "pending")
		all_runs = [ run for run in all_runs if run["worker"] is None ]
		return all_runs


	def _list_active_runs(self, database_client: DatabaseClient) -> List[dict]:
		""" Retrieve all active runs from the database """
		return self._run_provider.get_list(database_client, status = "running")


	def _should_schedule_trigger(self, database_client: DatabaseClient, schedule: dict, now: datetime.datetime) -> bool:
		""" Check if a new run should be triggered based on a timed schedule """

		now = now.replace(second = 0)
		if not pycron.is_now(schedule["expression"], now):
			return False

		if schedule["last_run"] is None:
			return True

		last_run = self._run_provider.get(database_client, schedule["project"], schedule["last_run"])
		if last_run is None:
			return True

		if last_run["status"] in [ "pending", "running" ]:
			return False

		last_trigger_date = last_run["creation_date"].replace(second = 0)
		if last_trigger_date == now:
			return False

		return True


	def trigger_run(self, database_client: DatabaseClient, run: dict) -> bool:
		""" Try to start a run execution """

		if run["status"] != "pending":
			raise ValueError("Run '%s' cannot be triggered (Status: '%s')" % (run["identifier"], run["status"]))

		job = self._job_provider.get(database_client, run["project"], run["job"])
		if not job["is_enabled"]:
			return False

		selected_worker = self._worker_selector(job, run)
		if selected_worker is None:
			return False

		logger.info("Assigning run '%s' to worker '%s'", run["identifier"], selected_worker)
		self._supervisor.get_worker(selected_worker).assign_run(job, run)
		return True


	def abort_run(self, run: dict) -> bool:
		""" Try to abort an active run """

		if run["status"] != "running":
			raise ValueError("Run '%s' cannot be aborted (Status: '%s')" % (run["identifier"], run["status"]))

		try:
			worker_instance = self._supervisor.get_worker(run["worker"])
		except KeyError:
			return False

		worker_instance.abort_run(run["identifier"])
		return True
