import datetime
import json
import os
import re
from typing import Any, Optional

import dateutil

from bhamon_orchestra_model.serialization.iserializer import ISerializer


datetime_isoformat_regex = re.compile(r"^[0-9]+-[0-9]+-[0-9]+T[0-9]+:[0-9]+:[0-9]+(\.[0-9]+)?([\-\+][0-9]+:[0-9]+|Z)?$")


class JsonSerializer(ISerializer):

	def __init__(self, indent = None) -> None:
		self.indent = indent


	def get_file_extension(self) -> None:
		return ".json"


	def serialize_to_file(self, path: str, value: Optional[Any]) -> None:
		with open(path + ".tmp", mode = "w", encoding = "utf-8") as data_file:
			json.dump(value, data_file, cls = JsonEncoder, indent = self.indent)
		os.replace(path + ".tmp", path)


	def deserialize_from_file(self, path: str) -> Optional[Any]:
		with open(path, mode = "r", encoding = "utf-8") as data_file:
			return json.load(data_file, cls = JsonDecoder)


	def serialize_to_string(self, value: Optional[Any]) -> str:
		return json.dumps(value, cls = JsonEncoder, indent = self.indent)


	def deserialize_from_string(self, serialized_value: str) -> Optional[Any]:
		return json.loads(serialized_value, cls = JsonDecoder)


class JsonEncoder(json.JSONEncoder):


	def default(self, o: Any) -> Any:
		if isinstance(o, datetime.datetime):
			return o.isoformat()
		return super().default(o)


class JsonDecoder(json.JSONDecoder):


	def __init__(self, *args, **kwargs):
		json.JSONDecoder.__init__(self, object_hook = self._object_hook, *args, **kwargs)


	def _object_hook(self, obj): # pylint: disable = no-self-use
		for key, value in obj.items():
			if isinstance(value, str) and datetime_isoformat_regex.search(value) is not None:
				obj[key] = dateutil.parser.parse(value)

		return obj
