# TODO: Integrate zip function
from typing import Dict
from fileutilslib.classes.ConsoleColors import ConsoleColors, ConsoleColor
from fileutilslib.classes.ImageBackup import ImageBackup
from fileutilslib.misclib.helpertools import is_boolean
from classes.LoggerFactory import LoggerFactory
from modules.Unit import Unit


class ImageBackupUnit(Unit):

	_imagebackup = None
	""":type: ImageBackup"""

	_local = True
	""":type: bool"""

	_logger = None
	""":type: logging.Logger"""

	_ddbatchsize = None
	""":type: str"""

	_safe_free_targetspace_margin = 50 * 1024 * 1024
	""":type: int"""

	_interactive = None
	""":type: bool"""

	def __init__(
		self,
		configfile,
		logfactory: LoggerFactory=None
	):
		super().__init__(
			self,
			configfile,
			["local", "targetdir"],
			self.on_config_loaded,
			logfactory
		)

		self._imagebackup = ImageBackup(True)

	def on_config_loaded(self, jsondata: Dict):
		options = jsondata["options"]
		self._local = options["local"]
		if "ddbatchsize" in options:
			self._ddbatchsize = options["ddbatchsize"]

		if "interactive" in options:
			b = options["interactive"]
			if is_boolean(b):
				self._interactive = b

		if self._interactive is None:
			self._interactive = True

		if self._interactive is False:
			if "devicepath" not in options:
				raise Exception("If interactive is on in options, you'll have to provide a devicepath, too!")
			self._imagebackup.set_device(options["devicepath"])
			if "imagepath" not in options:
				raise Exception("If interactive is on in options, you'll have to provide a imagepath, too!")

	def run(self):

		if self._interactive is True:
			self._imagebackup.set_device()
		self._imagebackup.assert_devicepath_is_valid()

		if self._interactive is True:
			if self._imagebackup.set_image_path() is False:
				print(ConsoleColor.colorline("Cancelled", ConsoleColors.OKBLUE))
				return

		self._imagebackup.assert_imagepath_is_valid()

		self._imagebackup.ensure_image_deleted()

		if self._interactive is True:
			self._imagebackup.print_pre_dd_info()

		self._imagebackup.assert_free_space(self._safe_free_targetspace_margin)

		self._imagebackup.start_dd(True, self._ddbatchsize)
