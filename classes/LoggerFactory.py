from enum import Enum
from lib.helpers import string_is_empty, is_sequence_with_any_elements
from logging import Formatter, Logger, getLogger, DEBUG, FileHandler, StreamHandler, basicConfig
from sys import stdout, stderr
from typing import List
from pathlib import Path


class LoggerHandlerType(Enum):
	Nope = 1
	FileHandler = 2
	ConsoleHandler = 3


class LoggerStdStreamType(Enum):
	StdOut = 1
	StdErr = 2


class LoggerFormatterType(Enum):
	User = 1
	FmtLong = 2
	FormatMid = 3
	FormatSmol = 3

	def set_format(self, userfmt, handler):

		defaultfmt = "%(message)s"

		if self.value == LoggerFormatterType.User:
			fmt = Formatter(userfmt)
		else:
			if self.value == LoggerFormatterType.FmtLong:
				fmt = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
			elif self.value == LoggerFormatterType.FormatMid:
				fmt = Formatter("%(asctime)s - %(name)s - %(message)s")
			elif self.value == LoggerFormatterType.FormatMid:
				fmt = Formatter("%(asctime)s - %(message)s")
			else:
				fmt = Formatter(defaultfmt)
		handler.setFormatter(fmt)


class LoggerHandlerConfig:
	_level = None
	""":type: int"""

	_handlertype = None
	""":type: LoggerHandlerType"""

	_stdstream = None
	""":type: LoggerStdStreamType"""

	_formatter = None
	""":type: LoggerFormatterType"""

	_formatter_user_fmt = None
	""":type: str"""

	_filefolder = None
	""":type: str"""

	def __init__(
		self,
		level: int,
		handlertype: LoggerHandlerType,
		filefolder: str,
		stdstream: LoggerStdStreamType=LoggerStdStreamType.StdOut,
		formatter: LoggerFormatterType=LoggerFormatterType.FmtLong,
		formatter_user_fmt: str=None
	):
		self._level = level
		self._handlertype = handlertype
		self._stdstream = stdstream
		self._formatter = formatter
		self._formatter_user_fmt = formatter_user_fmt
		self._filefolder = filefolder

	def get_level(self): return self._level

	def get_handlertype(self): return self._handlertype

	def get_stdstream(self): return self._stdstream

	def get_formatter(self): return self._formatter

	def get_formatter_user_fmt(self): return self._formatter_user_fmt

	def get_filefolder(self): return self._filefolder

	def create_handler(self, handlername):
		if self._handlertype == LoggerHandlerType.FileHandler:
			p = Path(self._filefolder, "{}.log".format(handlername))
			handler = FileHandler(str(p), mode="w")
		else:
			if self._stdstream == LoggerStdStreamType.StdOut:
				handler = StreamHandler(stdout)
			elif self._stdstream == LoggerStdStreamType.StdErr:
				handler = StreamHandler(stderr)
			else:
				raise Exception("Stdstream {} not supported".format(self._stdstream))
		handler.setLevel(self._level)
		self._formatter.set_format(self._formatter_user_fmt, handler)
		return handler

	@staticmethod
	def create_console_err_config(
		level: int=DEBUG,
		formatter: LoggerFormatterType=LoggerFormatterType.FmtLong,
		formatter_user: str=None
	):
		return LoggerHandlerConfig(
			level,
			LoggerHandlerType.ConsoleHandler,
			None,
			LoggerStdStreamType.StdErr,
			formatter, formatter_user)

	@staticmethod
	def create_console_out_config(
		level: int=DEBUG,
		formatter: LoggerFormatterType=LoggerFormatterType.FmtLong,
		formatter_user: str=None
	):
		return LoggerHandlerConfig(
			level,
			LoggerHandlerType.ConsoleHandler,
			None,
			LoggerStdStreamType.StdOut,
			formatter,
			formatter_user
		)

	@staticmethod
	def create_file_config(
		level: int=DEBUG,
		folder: str=".",
		formatter: LoggerFormatterType=LoggerFormatterType.FmtLong,
		formatter_user: str=None
	):
		return LoggerHandlerConfig(
			level,
			LoggerHandlerType.FileHandler,
			folder,
			None,
			formatter,
			formatter_user
		)


class LoggerFactory:

	_nameprefix = None
	""":type: str"""

	_loggers = {}

	def __init__(self, nameprefix: str):
		# logging.basicConfig(filename='example.log', level=logging.DEBUG)
		if string_is_empty(nameprefix):
			raise Exception("name has to be passed")
		self._nameprefix = nameprefix

	def addlogger(
		self,
		name: str,
		configs: List[LoggerHandlerConfig]
	) -> Logger:

		if not is_sequence_with_any_elements(configs):
			raise Exception("configs needs to be passed")

		if string_is_empty(name):
			raise Exception("name needs to be passed")

		loggername = self._nameprefix + "." + name

		if loggername in self._loggers:
			return self._loggers[loggername]

		logger = getLogger(loggername)
		logger.setLevel(DEBUG)

		for config in configs:  # type: LoggerConfig
			logger.addHandler(config.create_handler(loggername))

		self._loggers[loggername] = logger

		return self._loggers[loggername]
