from click import ClickException
from typing import Any


class JobException(ClickException):
	_errcode = 0
	""":type: int"""

	def __init__(self, e: Any, errcode: int):
		super().__init__(str(e) if isinstance(e, Exception) else e)
		self._errcode = errcode

	def get_errcode(self) -> int:
		return self._errcode
