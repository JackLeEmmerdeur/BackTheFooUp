# TODO: Modularize for standalone app; integrate zip function
from classes.LoggerFactory import LoggerFactory
from modules.Unit import Unit
from typing import Dict
from pathlib import Path
from plumbum import local
from os import remove, statvfs, stat
from classes.ConsoleColors import ConsoleColors, ConsoleColor
from subprocess import PIPE
from datetime import datetime
from fileutilslib.disklib.fdisktools import fdisklist, fdiskdevicesize, predict_job_time
from fileutilslib.misclib.helpertools import string_equal_utf8, strip, string_is_empty, humantime
from fileutilslib.disklib.filetools import sizeinfo_from_statvfs_result, find_mount_point, bytes_to_unit
from fileutilslib.disklib.ddtools import parse_dd_info


class ImageBackup(Unit):
	_local = True
	""":type: bool"""

	_logger = None
	""":type: logging.Logger"""

	_ddbatchsize = None
	""":type: str"""

	_safe_free_targetspace_margin = 50 * 1024 * 1024
	""":type: int"""

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

	def on_config_loaded(self, jsondata: Dict):
		options = jsondata["options"]
		self._local = options["local"]
		if "ddbatchsize" in options:
			self._ddbatchsize = options["ddbatchsize"]

	def run(self):
		devs = fdisklist(True)

		mydev = strip(input("Type the path of device (e.g. /dev/sde) or partition (e.g. /dev/sde1) you want to backup:\n"))
		devok = False

		for dev in devs:
			if string_equal_utf8(dev["dev"], mydev, False):
				devok = True

			if devok is False:
				if "partitions" in dev:
					for devpart in dev["partitions"]:
						if devpart["dev"] == mydev:
							devok = True
							break

			if devok is True:
				break

		if not devok:
			raise Exception("Device or partition '{}' not found".format(mydev))

		mydev = Path(mydev)
		imagepathok = False
		cancelled = False
		cancelled_reason = None
		imagefile = None
		imagefilepath = None

		try:
			while imagepathok is False:
				fpi = input("Type the filepath of the image you want to create (empty to cancel image creation):\n")
				imagefilepath = strip(fpi)

				if string_is_empty(imagefilepath):
					raise Exception("_cic_")

				imagefile = Path(imagefilepath)

				if imagefile.is_dir():
					print(ConsoleColor.colorline("Path is a directory", ConsoleColors.FAIL))
					imagefile = None
				else:
					imagepathok = True

		except Exception as e:
			if str(e) == "_cic_":
				cancelled = True
				cancelled_reason = "Cancelling image creation"

		if cancelled is False:
			fpexists = imagefile.exists()

			if fpexists:
					print(ConsoleColor.colorline("The image already exists", ConsoleColors.FAIL))

					yn = Unit.singlecharinput(
						"Do you want to delete it (y/n)?",
						ConsoleColors.OKGREEN
					)

					if yn == "y":
						yn = Unit.singlecharinput(
							"Do you really want to delete the image '{}' (y/n)?".format(imagefile),
							ConsoleColors.OKGREEN
						)

						if yn == "y":
							print(ConsoleColor.colorline("Deleting image '{}'".format(imagefile), ConsoleColors.FAIL))
							remove(str(imagefile.absolute()))
							imagefile = Path(imagefilepath)
							if imagefile.exists():
								raise Exception("Could not delete image '{}'".format(imagefile))
							else:
								fpexists = False

					if fpexists is True:
						cancelled_reason = "Will not overwrite existing image"
						cancelled = True

			if cancelled is True:
				print(ConsoleColor.colorline(cancelled_reason, ConsoleColors.OKBLUE))
			else:
				image_mountpoint = find_mount_point(str(imagefile))
				image_mountpoint_sizeinfo = sizeinfo_from_statvfs_result(statvfs(image_mountpoint))

				target_image_sizebytes = fdiskdevicesize(devs, str(mydev))
				target_image_sizehuman = bytes_to_unit(target_image_sizebytes, True, True, False)

				print(ConsoleColor.colorline(
					"Approximate image size: {}".format(target_image_sizehuman),
					ConsoleColors.UNDERLINE))

				print(ConsoleColor.colorline(
					"Free space on image partition: {}".format(image_mountpoint_sizeinfo["free_h"]),
					ConsoleColors.UNDERLINE))

				if image_mountpoint_sizeinfo["free"] - self._safe_free_targetspace_margin <= target_image_sizebytes:
					raise Exception("There is not enough free space to create the image")

				param_if = "if={}".format(str(mydev).replace(" ", "\\ "))
				param_of = "of={}".format(str(imagefile).replace(" ", "\\ "))
				param_status = "status=progress"

				# todo: make configurable batch size
				if self._ddbatchsize is not None:
					param_bs = "bs={}".format(self._ddbatchsize)
				else:
					param_bs = "bs=1M"

				print(ConsoleColor.colorline("Will execute \"{}\"".format(
					"sudo dd {} {} {} {}".format(param_if, param_of, param_status, param_bs)
				), ConsoleColors.OKGREEN))

				yn = Unit.singlecharinput(
					"Confirm the creation of image '{}' from device '{}' (y/n)!".format(
						str(imagefile), str(mydev)
					), ConsoleColors.OKGREEN
				)

				if yn == "y":
					sudo = local["sudo"]
					dd = local["dd"]

					starttime = datetime.now()

					p = sudo[dd[param_if, param_of, param_status, param_bs]].popen(stderr=PIPE)
					line = ''
					# retcode = 0

					# Intention is not to get the first "\r" from dd-output
					# sleep(1)
					print()
					while True:
						retcode = p.poll()
						if retcode is None:
							out = p.stderr.read(1).decode("utf-8", errors="replace")
							if out == '':
								break
							else:
								if out == '\r':
									line = strip(line)
									if not string_is_empty(line):
										dd_info = parse_dd_info(line)
										currenttime = datetime.now()
										deltatime = currenttime - starttime

										print(
											"{0:10}{1:4}{2:9}{3:3}{4:10}{5:4}{6:8}{7:3}{8}".format(
												bytes_to_unit(dd_info["size_b"], True, True, False),
												"of",
												target_image_sizehuman,
												"|",
												dd_info["time_h"],
												"of",
												humantime(
													predict_job_time(
														dd_info["time"],
														target_image_sizebytes,
														dd_info["size_b"]
													)
												),
												"|",
												"Total time: {}".format(humantime(deltatime.total_seconds()))
											),
											end="\r"
										)

									line = ''
								else:
									line = line + out
						else:
							break

					retcode = retcode if retcode is not None else p._proc.returncode
					print()

					currenttime = datetime.now()
					deltatime = currenttime - starttime
					print(
						ConsoleColor.colorline(
							"Total time: {}".format(
								humantime(deltatime.total_seconds())
							), ConsoleColors.OKGREEN
						)
					)

					st = stat(str(imagefile))
					print(
						ConsoleColor.colorline(
							"Final image size: {}".format(
								bytes_to_unit(st.st_size, True, True, False)
							), ConsoleColors.OKGREEN
						)
					)
					if retcode == 0:
						print(ConsoleColor.colorline("Successfully created image!", ConsoleColors.OKGREEN))
					else:
						print(ConsoleColor.colorline("No Result from dd (image might be ok)!", ConsoleColors.WARNING))

					# print("Success" if retcode == 0 else "Something went wrong")
				else:
					print(ConsoleColor.colorline("Cancelled image creation on your wish", ConsoleColors.OKBLUE))
