import abc
from typing import Any, Optional


class ISerializer(abc.ABC):


	@abc.abstractmethod
	def serialize_to_file(self, path: str, value: Optional[Any]) -> None:
		pass


	@abc.abstractmethod
	def deserialize_from_file(self, path: str) -> Optional[Any]:
		pass


	@abc.abstractmethod
	def serialize_to_string(self, value: Optional[Any]) -> str:
		pass


	@abc.abstractmethod
	def deserialize_from_string(self, serialized_value: str) -> Optional[Any]:
		pass
