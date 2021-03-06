import datetime
import hashlib
import hmac
import logging
import secrets
import uuid

from typing import List, Optional, Tuple

from bhamon_orchestra_model.database.database_client import DatabaseClient
from bhamon_orchestra_model.date_time_provider import DateTimeProvider


logger = logging.getLogger("AuthenticationProvider")


class AuthenticationProvider:


	def __init__(self, database_client: DatabaseClient, date_time_provider: DateTimeProvider) -> None:
		self.database_client = database_client
		self.date_time_provider = date_time_provider
		self.table = "user_authentication"

		self.password_salt_size = 32
		self.password_hash_function = "pbkdf2"
		self.password_hash_function_parameters = { "hash_name": "sha256", "iterations": 1000 * 1000 }

		self.token_size = 32
		self.token_hash_function = "sha256"
		self.token_hash_function_parameters = {}


	def set_password(self, user: str, password: str) -> dict:
		now = self.date_time_provider.now()
		authentication = self.database_client.find_one(self.table, { "user": user, "type": "password" })

		if authentication is None:
			authentication = {
				"identifier": str(uuid.uuid4()),
				"user": user,
				"type": "password",
				"creation_date": self.date_time_provider.serialize(now),
				"update_date": self.date_time_provider.serialize(now),
			}

			self.database_client.insert_one(self.table, authentication)

		authentication.update({
			"hash_function": self.password_hash_function,
			"hash_function_parameters": self.password_hash_function_parameters,
			"hash_function_salt": secrets.token_hex(self.password_salt_size),
			"update_date": self.date_time_provider.serialize(now),
		})

		authentication["secret"] = self.hash_password(password, authentication["hash_function_salt"], authentication["hash_function"], authentication["hash_function_parameters"])

		self.database_client.update_one(self.table, { "identifier": authentication["identifier"] }, authentication)
		return self.convert_to_public(authentication)


	def remove_password(self, user: dict) -> None:
		self.database_client.delete_one(self.table, { "user": user, "type": "password" })


	def authenticate_with_password(self, user_identifier: str, password: str) -> bool:
		authentication = self.database_client.find_one(self.table, { "user": user_identifier, "type": "password" })
		if authentication is None:
			return False
		hashed_password = self.hash_password(password, authentication["hash_function_salt"], authentication["hash_function"], authentication["hash_function_parameters"])
		return hmac.compare_digest(hashed_password, authentication["secret"])


	def authenticate_with_token(self, user_identifier: str, secret: str) -> bool:
		now = self.date_time_provider.serialize(self.date_time_provider.now())
		user_tokens = self.database_client.find_many(self.table, { "user": user_identifier, "type": "token" })

		for token in user_tokens:
			if "expiration_date" not in token or token["expiration_date"] > now:
				hashed_secret = self.hash_token(secret, token["hash_function"], token["hash_function_parameters"])
				if hashed_secret == token["secret"]:
					return True

		return False


	def count_tokens(self, user: Optional[str] = None) -> int:
		filter = { "user": user, "type": "token" } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		return self.database_client.count(self.table, filter)


	def get_token_list(self, user: Optional[str] = None, skip: int = 0, limit: Optional[int] = None, order_by: Optional[Tuple[str,str]] = None) -> List[dict]:
		filter = { "user": user, "type": "token" } # pylint: disable = redefined-builtin
		filter = { key: value for key, value in filter.items() if value is not None }
		token_list = self.database_client.find_many(self.table, filter, skip = skip, limit = limit, order_by = order_by)
		return [ self.convert_to_public(token) for token in token_list ]


	def get_token(self, user_identifier: str, token_identifier: str) -> Optional[dict]:
		token = self.database_client.find_one(self.table, { "identifier": token_identifier, "user": user_identifier, "type": "token" })
		return self.convert_to_public(token) if token is not None else None


	def create_token(self, user: str, description: str, expiration: Optional[datetime.timedelta]) -> dict:
		now = self.date_time_provider.now()

		token = {
			"identifier": str(uuid.uuid4()),
			"user": user,
			"type": "token",
			"description": description,
			"hash_function": self.token_hash_function,
			"hash_function_parameters": self.token_hash_function_parameters,
			"creation_date": self.date_time_provider.serialize(now),
			"update_date": self.date_time_provider.serialize(now),
		}

		if expiration is not None:
			token["expiration_date"] = self.date_time_provider.serialize(now + expiration)

		secret = secrets.token_hex(self.token_size)
		token["secret"] = self.hash_token(secret, token["hash_function"], token["hash_function_parameters"])

		self.database_client.insert_one(self.table, token)
		result = self.convert_to_public(token)
		result["secret"] = secret
		return result


	def set_token_expiration(self, user_identifier: str, token_identifier: str, expiration: datetime.timedelta) -> None:
		token = self.database_client.find_one(self.table, { "identifier": token_identifier, "user": user_identifier, "type": "token" })
		if "expiration_date" not in token:
			raise ValueError("Token '%s' does not expire" % token_identifier)

		now = self.date_time_provider.now()

		update_data = {
			"expiration_date": self.date_time_provider.serialize(now + expiration),
			"update_date": self.date_time_provider.serialize(now),
		}

		self.database_client.update_one(self.table, { "identifier": token_identifier, "user": user_identifier, "type": "token" }, update_data)


	def delete_token(self, user_identifier: str, token_identifier: str) -> None:
		self.database_client.delete_one(self.table, { "identifier": token_identifier, "user": user_identifier, "type": "token" })


	def hash_password(self, password: str, salt: str, function: str, parameters: dict) -> str: # pylint: disable = no-self-use
		if function == "pbkdf2":
			return hashlib.pbkdf2_hmac(password = password.encode("utf-8"), salt = bytes.fromhex(salt), **parameters).hex()
		raise ValueError("Unsupported hash function '%s'" % function)


	def hash_token(self, token: str, function: str, parameters: dict) -> str: # pylint: disable = no-self-use, unused-argument
		if function == "sha256":
			return hashlib.sha256(bytes.fromhex(token)).hexdigest()
		raise ValueError("Unsupported hash function '%s'" % function)


	def convert_to_public(self, authentication: dict) -> dict: # pylint: disable = no-self-use
		keys_to_return = [ "identifier", "user", "type", "description", "expiration_date", "creation_date", "update_date" ]
		return { key: value for key, value in authentication.items() if key in keys_to_return }
