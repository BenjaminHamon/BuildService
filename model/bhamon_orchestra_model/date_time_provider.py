import datetime

import dateutil.parser


class DateTimeProvider:
	""" Provider to standardize operations with datetime objects and allow overriding.

	This implementation uses UTC times, ISO serialization and limits precision to the second.

	"""


	def now(self) -> datetime.datetime: # pylint: disable = no-self-use
		""" Return the current datetime """
		return datetime.datetime.now(datetime.timezone.utc).replace(microsecond = 0)


	def serialize(self, value: datetime.datetime) -> str: # pylint: disable = no-self-use
		""" Serialize a datetime to its string representation """
		return value.replace(microsecond = 0, tzinfo = None).isoformat() + "Z"


	def deserialize(self, value: str) -> datetime.datetime: # pylint: disable = no-self-use
		""" Deserialize a datetime from its string representation """
		return dateutil.parser.parse(value).replace(microsecond = 0, tzinfo = None)
