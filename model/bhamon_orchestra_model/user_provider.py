import logging
import re

from typing import List, Optional, Tuple

from bhamon_orchestra_model.authentication_provider import AuthenticationProvider
from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.date_time_provider import DateTimeProvider
from bhamon_orchestra_model.worker_provider import WorkerProvider


logger = logging.getLogger("UserProvider")


class UserProvider:


	def __init__(self, date_time_provider: DateTimeProvider) -> None:
		self.date_time_provider = date_time_provider
		self.table = "user"
		self.user_identifier_regex = re.compile(r"^[a-zA-Z0-9_\-\.]{3,32}$")


	def count(self, database_client: DatabaseClient) -> int:
		return database_client.count(self.table, {})


	def get_list(self, database_client: DatabaseClient,
			skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:
		return database_client.find_many(self.table, {}, skip = skip, limit = limit, order_by = order_by)


	def get(self, database_client: DatabaseClient, user_identifier: str) -> Optional[dict]:
		return database_client.find_one(self.table, { "identifier": user_identifier })


	def create(self, database_client: DatabaseClient, user_identifier: str, display_name: str) -> dict:
		if self.user_identifier_regex.search(user_identifier) is None:
			raise ValueError("User identifier is invalid: '%s'" % user_identifier)

		now = self.date_time_provider.now()

		user = {
			"identifier": user_identifier,
			"display_name": display_name,
			"roles": [],
			"is_enabled": True,
			"creation_date": now,
			"update_date": now,
		}

		database_client.insert_one(self.table, user)
		return user


	def update_identity(self, database_client: DatabaseClient, user: dict, display_name: Optional[str] = None) -> None:
		now = self.date_time_provider.now()

		update_data = {
			"display_name": display_name,
			"update_date": now,
		}

		update_data = { key: value for key, value in update_data.items() if value is not None }

		user.update(update_data)
		database_client.update_one(self.table, { "identifier": user["identifier"] }, update_data)


	def update_roles(self, database_client: DatabaseClient, user: dict, roles: List[str]) -> None:
		now = self.date_time_provider.now()

		update_data = {
			"roles": roles,
			"update_date": now,
		}

		user.update(update_data)
		database_client.update_one(self.table, { "identifier": user["identifier"] }, update_data)


	def update_status(self, database_client: DatabaseClient, user: dict, is_enabled: Optional[bool] = None) -> None:
		now = self.date_time_provider.now()

		update_data = {
			"is_enabled": is_enabled,
			"update_date": now,
		}

		update_data = { key: value for key, value in update_data.items() if value is not None }

		user.update(update_data)
		database_client.update_one(self.table, { "identifier": user["identifier"] }, update_data)


	def delete(self, database_client: DatabaseClient,
			user_identifier: str, authentication_provider: AuthenticationProvider, worker_provider: WorkerProvider) -> None:

		user_record = self.get(database_client, user_identifier)
		if user_record is None:
			raise ValueError("User '%s' does not exist" % user_identifier)
		if user_record["is_enabled"]:
			raise ValueError("User '%s' is enabled" % user_identifier)
		if worker_provider.count(database_client, owner = user_identifier) > 0:
			raise ValueError("User '%s' owns workers" % user_identifier)

		authentication_provider.remove_password(database_client, user_identifier)
		for token in authentication_provider.get_token_list(database_client, user_identifier):
			authentication_provider.delete_token(database_client, user_identifier, token["identifier"])
		database_client.delete_one(self.table, { "identifier": user_identifier })
