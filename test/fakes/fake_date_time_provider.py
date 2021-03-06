import datetime

from bhamon_orchestra_model.date_time_provider import DateTimeProvider


class FakeDateTimeProvider(DateTimeProvider):
	""" Fake datetime provider for unit tests """


	def __init__(self):
		super().__init__()
		self.now_value = datetime.datetime(2020, 1, 1, 0, 0, 0)


	def now(self):
		return self.now_value
