from enum import Enum
from typing import Dict
from pathlib import Path
from lib.helpers import is_empty_dict


class BackupEntryType(Enum):
	Unknown = 1
	Dir = 2
	File = 3

	def __str__(self):
		return self.name


class BackupEntry:
	_entrytype = None
	""":type: EntryType"""

	_path = None
	""":type: Path"""

	_entryfilter = None
	""":type: str"""

	_entryname = None
	""":type: str"""

	def __init__(self, entrytype: BackupEntryType, entryname: str, entryfilter: str, path: str, options: Dict):
		self._entrytype = entrytype
		self._entryfilter = entryfilter
		self._path = Path(path)
		self._options = options
		self._entryname = entryname

	def get_type(self) -> BackupEntryType:
		return self._entrytype

	def get_path(self) -> Path:
		return self._path

	def get_filter(self) -> str:
		return self._entryfilter

	def get_options(self) -> Dict:
		return self._options

	def get_name(self) -> str:
		return self._entryname

	def should_skip(self) -> bool:
		return (
			not is_empty_dict(self._options) and
			"skip" in self._options and
			self._options["skip"] is True
		)
