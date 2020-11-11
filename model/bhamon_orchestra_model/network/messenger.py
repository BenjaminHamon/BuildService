import asyncio
import logging
import traceback
import uuid
from typing import Callable, Optional

from bhamon_orchestra_model.network.connection import NetworkConnection
from bhamon_orchestra_model.serialization.iserializer import ISerializer


logger = logging.getLogger("Messenger")


class Messenger:


	def __init__(self, serializer: ISerializer, identifier: str, connection: NetworkConnection, # pylint: disable = too-many-arguments
			request_handler: Callable[[dict],None] = None, update_handler: Callable[[dict],None] = None) -> None:

		self.serializer = serializer
		self.identifier = identifier
		self.connection = connection
		self.request_handler = request_handler
		self.update_handler = update_handler

		self.is_disposed = False

		self._messages_to_send = []
		self._messages_to_wait = []
		self._messages_to_handle = []
		self._messages_events = {}


	async def run(self) -> None:
		if self.is_disposed:
			raise RuntimeError("Messenger is disposed")

		incoming_future = asyncio.ensure_future(self._pull())
		incoming_process_future = asyncio.ensure_future(self._handle_incoming())
		outgoing_future = asyncio.ensure_future(self._push())

		try:
			await asyncio.gather(incoming_future, incoming_process_future, outgoing_future)

		finally:
			incoming_future.cancel()
			incoming_process_future.cancel()
			outgoing_future.cancel()


	def dispose(self) -> None:
		for message in self._messages_to_send:
			logger.warning("Cancelling outgoing %s %s", message["type"], message["identifier"])

			if message["type"] == "request":
				message["response"] = { "identifier": message["identifier"], "error": "Cancelled" }
				self._messages_events[message["identifier"]].set()

		for message in self._messages_to_wait:
			logger.warning("Cancelling expected response %s", message["identifier"])

			if message["type"] == "request":
				message["response"] = { "identifier": message["identifier"], "error": "Cancelled" }
				self._messages_events[message["identifier"]].set()

		for message in self._messages_to_handle:
			logger.warning("Cancelling handling %s %s", message["type"], message["identifier"])

		self._messages_to_send.clear()
		self._messages_to_wait.clear()
		self._messages_to_handle.clear()
		self._messages_events.clear()

		self.is_disposed = True


	async def send_request(self, data: dict) -> Optional[dict]:
		if self.is_disposed:
			raise RuntimeError("Messenger is disposed")

		identifier = str(uuid.uuid4())
		message_event = asyncio.Event()
		message = { "type": "request", "identifier": identifier, "data": data }

		self._messages_events[identifier] = message_event
		self._messages_to_send.append(message)

		await message_event.wait()

		if message["response"].get("error", None) is not None:
			raise RuntimeError(message["response"]["error"])
		return message["response"].get("data", None)


	def _send_response(self, identifier: str, data: dict) -> None:
		message = { "type": "response", "identifier": identifier, "data": data }
		self._messages_to_send.append(message)


	def _send_response_error(self, identifier: str, error: dict) -> None:
		message = { "type": "response", "identifier": identifier, "error": error }
		self._messages_to_send.append(message)


	def send_update(self, data: dict) -> None:
		if self.is_disposed:
			raise RuntimeError("Messenger is disposed")

		identifier = str(uuid.uuid4())
		message = { "type": "update", "identifier": identifier, "data": data }
		self._messages_to_send.append(message)


	async def _push(self) -> None:
		while True:
			while len(self._messages_to_send) > 0:
				await self._send_next()
			await asyncio.sleep(0.1)


	async def _send_next(self) -> None:
		if len(self._messages_to_send) == 0:
			return

		message = self._messages_to_send[0]
		logger.debug("(%s) > %s %s", self.identifier, message["type"], message["identifier"])
		await self.connection.send(self.serializer.serialize_to_string(message))
		self._messages_to_send.remove(message)

		if message["type"] == "request":
			self._messages_to_wait.append(message)


	async def _pull(self) -> None:
		while True:
			await self._receive_next()


	async def _receive_next(self) -> None:
		message = self.serializer.deserialize_from_string(await self.connection.receive())
		logger.debug("(%s) < %s %s", self.identifier, message["type"], message["identifier"])
		self._messages_to_handle.append(message)


	async def _handle_incoming(self) -> None:
		while True:
			while len(self._messages_to_handle) > 0:
				await self._handle_next()
			await asyncio.sleep(0.1)


	async def _handle_next(self) -> None:
		if len(self._messages_to_handle) == 0:
			return

		message = self._messages_to_handle[0]

		try:
			message_was_handled = await self._handle_message(message)
			if message_was_handled:
				self._messages_to_handle.remove(message)
		except Exception: # pylint: disable = broad-except
			logger.error("Unhandled exception in message handler", exc_info = True)


	async def _handle_message(self, message: dict) -> bool:
		if message["type"] == "request":
			return await self._handle_request(message)
		if message["type"] == "response":
			return await self._handle_response(message)
		if message["type"] == "update":
			return await self._handle_update(message)
		raise ValueError("Unsupported message type: '%s'" % message["type"])


	async def _handle_request(self, request: dict) -> bool:
		if self.request_handler is None:
			raise ValueError("Request handler is None")

		logger.debug("Handling request '%s'", request["identifier"])

		try:
			result = await self.request_handler(request["data"])
			self._send_response(request["identifier"], result)
		except Exception as exception: # pylint: disable = broad-except
			logger.error("Handler for request '%s' raised an exception", request["identifier"], exc_info = True)
			error_result = "".join(traceback.format_exception_only(exception.__class__, exception)).strip()
			self._send_response_error(request["identifier"], error_result)

		return True


	async def _handle_response(self, response: dict) -> bool:
		logger.debug("Handling response '%s'", response["identifier"])

		request = next(r for r in self._messages_to_wait if r["type"] == "request" and r["identifier"] == response["identifier"])
		request["response"] = response
		self._messages_events[request["identifier"]].set()
		self._messages_to_wait.remove(request)
		return True


	async def _handle_update(self, update: dict) -> bool:
		if self.update_handler is None:
			raise ValueError("Update handler is None")

		logger.debug("Handling update '%s'", update["identifier"])

		try:
			await self.update_handler(update["data"])
		except Exception: # pylint: disable = broad-except
			logger.error("Handler for update '%s' raised an exception", update["identifier"], exc_info = True)
		return True
