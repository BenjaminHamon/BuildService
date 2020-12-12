class ProcessException(Exception):

	def __init__(self, message: str, exit_code: int) -> None:
		super().__init__(message)

		self.exit_code = exit_code
