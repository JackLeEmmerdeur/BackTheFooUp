# TODO: Integrate zip function
from typing import Dict
from fileutilslib.classes.Bencher import Bencher
from fileutilslib.classes.ConsoleColors import ConsoleColors, ConsoleColor
from fileutilslib.classes.ImageBackup import ImageBackup
from fileutilslib.misclib.helpertools import is_boolean, string_is_empty, strip, singlecharinput, is_linux
from fileutilslib.disklib.filetools import sevenzip
from classes.LoggerFactory import LoggerFactory
from modules.Unit import Unit


class ImageBackupUnit(Unit):

	_bencher = None
	""":type: Bencher"""

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

	_compress = False
	""":type: bool"""

	_compress_format = None
	""":type: str"""

	_compress_file = None
	""":type: str"""

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
		self._bencher = Bencher()

	def on_config_loaded(self, jsondata: Dict):
		options = jsondata["options"]

		self._local = options["local"]
		if "ddbatchsize" in options:
			self._ddbatchsize = options["ddbatchsize"]

		if "interactive" in options:
			b = options["interactive"]
			if is_boolean(b):
				self._interactive = b
			else:
				raise Exception("json-config options['interactive'] has to be a boolean")

		if self._interactive is None:
			self._interactive = True

		if "compress" in options:
			compress = options["compress"]
			if "format" not in compress:
				raise Exception("json-config 'compress' dict has to contain a 'format' key")
			self._compress_format = compress["format"]
			if self._interactive is False:
				if "file" in compress:
					raise Exception("If the image backup isn't interactive and 'compress' is provided, 'compress' has to contain a file-key")
				self._compress_file = compress["file"]

		if self._interactive is False:
			if "devicepath" not in options:
				raise Exception("If interactive is on in options, you'll have to provide a devicepath, too!")
			self._imagebackup.set_device(options["devicepath"])
			if "imagepath" not in options:
				raise Exception("If interactive is on in options, you'll have to provide a imagepath, too!")

	def _finished(self, retcode: str, imagepath: str):
		if is_linux():
			sevenzip(self._interactive, "7z", imagepath, None)

			self._bencher.endbench()

			if self._interactive is True:
				print("Total time: {}".format(self._bencher.get_result()))

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
		self._bencher.startbench()
		self._imagebackup.start_dd(True, self._ddbatchsize, self._finished)


