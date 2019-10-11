from json import load
from logging import INFO, ERROR
from typing import List, Callable
from classes.LoggerFactory import LoggerHandlerType, LoggerFactory, LoggerHandlerConfig
from fileutilslib.misclib.helpertools import is_sequence_with_any_elements, assert_obj_has_keys, string_is_empty
import click


class Unit:

	_unit_name = None
	""":type: str"""

	_group = None
	""":type: str"""

	_ignoreoptions = None
	""":type: List[str]"""

	_options = None
	""":type: Dict"""

	_entries = None
	""":type: object[]"""

	_config_loaded = False
	""":type: bool"""

	_logger = None
	""":type: logging.Logger"""

	_jsondata = None
	""":type: Dict"""

	_div = "==============="
	""":type: str"""

	def __init__(
		self,
		unit_name: str,
		configfile: click.File,
		mandatory_option_keys: List[str],
		config_loaded_handler: Callable,
		logfactory: LoggerFactory=None,
		group: str=None,
		ignoreoptions: List[str]=None
	):
		self._unit_name = unit_name
		self._entries = []
		self._config_loaded = False
		self._group = group
		self._ignoreoptions = ignoreoptions

		if configfile is None:
			raise Exception("configfile is invalid")

		self.reload_jsonconfig(
			configfile,
			mandatory_option_keys,
			config_loaded_handler,
			logfactory
		)
		self.info(str(self))

	def __str__(self):
		dbg = ""
		if self._config_loaded:
			for k, v in self._jsondata["options"].items():
				if k != "password":
					dbg += "{}: {}\n".format(k, str(v))
		return dbg

	def info(self, msg):
		if self._logger is not None:
			self._logger.info(msg)

	def error(self, e):
		if self._logger is not None:
			self._logger.error(str(e))

	def is_config_loaded(self):
		return self._config_loaded

	def reload_jsonconfig(
		self,
		configfile: click.File,
		mandatory_option_keys: List[str],
		config_loaded_handler: Callable,
		logfactory: LoggerFactory
	):
		if is_sequence_with_any_elements(self._jsondata):
			self._jsondata.clear()

		self._jsondata = load(configfile)

		assert_obj_has_keys(self._jsondata, "json", ["options"])
		options = self._jsondata["options"]
		assert_obj_has_keys(options, "options", mandatory_option_keys)

		self._options = options

		if "loggers" in options:
			loggers = options["loggers"]
			if is_sequence_with_any_elements(loggers):
				lt = LoggerHandlerType.Nope

				handlerconfigs = []

				for logger in loggers:
					if "type" not in logger:
						raise Exception("logger in json has to contain a type")

					if "level" not in logger or (
						logger["level"] != "all" and
						logger["level"] != "errors"
					):
						raise Exception("logger level is not cool (use 'all' or 'errors')")

					if logger["type"] == "file":
						lt = LoggerHandlerType.FileHandler
					elif logger["type"] == "console":
						lt = LoggerHandlerType.ConsoleHandler
					else:
						raise Exception("logger-type {} in json is not recognized".format(logger["type"]))

					if lt == LoggerHandlerType.FileHandler and ("folder" not in logger or string_is_empty(logger["folder"])):
						raise Exception("logger with type file has to contain a folder-option")

					handlerconfig = None
					""":type:LoggerHandlerConfig"""

					if lt == LoggerHandlerType.FileHandler:
						handlerconfig = LoggerHandlerConfig.create_file_config(
							ERROR if logger["level"] == "errors" else INFO,
							logger["folder"]
						)
					else:
						if logger["level"] == "errors":
							handlerconfig = LoggerHandlerConfig.create_console_err_config(ERROR)
						else:
							handlerconfig = LoggerHandlerConfig.create_console_err_config(INFO)

					handlerconfigs.append(handlerconfig)

				self._logger = logfactory.addlogger(
					options["name"],
					handlerconfigs
				)
		self._config_loaded = True

		if config_loaded_handler is not None:
			config_loaded_handler(self._jsondata)

