from lib.helpers import assert_obj_has_keys, is_sequence_with_any_elements, repeat, string_is_empty, is_empty_dict, is_string
from lib.filesize_helpers import get_filesize_progress_divider, bytes_to_unit
from os import makedirs, utime
import paramiko
from json import load
from pathlib import Path
from classes.BackupEntry import BackupEntryType, BackupEntry
from classes.JobException import JobException
from classes.ConsoleColors import ConsoleColors
from os import lstat
from datetime import datetime
import stat
from fnmatch import fnmatch
from classes.LoggerFactory import LoggerHandlerType, LoggerFactory, LoggerFormatterType, LoggerHandlerConfig
from logging import DEBUG, INFO, WARNING, ERROR


class FileBackup:
	_entries = None

	_jsondata = None
	""":type: Dict"""

	_host = None
	""":type: str"""

	_user = None
	""":type: str"""

	_password = None
	""":type: str"""

	_targetdir = None
	""":type: str"""

	_config_loaded = True
	""":type: bool"""

	_last_dl_bytes = 0
	""":type: long"""

	_current_progress_divider = 0
	""":type: int"""

	_transport = None
	""":type: paramiko.Transport"""

	_copystats = False
	""":type: bool"""

	_show_copystats = False
	""":type: bool"""

	_processonly_types = None
	""":type: str[]"""

	_div = "==============="

	_logger = None
	""":type: logging.Logger"""

	def __init__(
		self,
		configfile,
		show_copystats=False,
		logfactory: LoggerFactory=None
	):
		self._entries = []
		self._config_loaded = False
		self._show_copystats = show_copystats
		self.reload_jsonconfig(configfile, logfactory)
		self.info(str(self))

	def __del__(self):
		if self._transport is not None:
			self._transport.close()

	def __str__(self):
		dbg = "{}\nFileBackupUnit\n{}\n{} Jobs defined\n".format(
			self._div, self._div,
			len(self._jsondata["pathes"])
		)
		if self._config_loaded:
			for k, v in self._jsondata["options"].items():
				dbg += "{}: {}\n".format(k, str(v))
		return dbg

	def info(self, msg):
		if self._logger is not None:
			self._logger.info(msg)

	def error(self, e):
		if self._logger is not None:
			self._logger.error(str(e))

	def reload_jsonconfig(self, configfile, logfactory: LoggerFactory):
		if is_sequence_with_any_elements(self._jsondata):
			self._jsondata.clear()

		self._jsondata = load(configfile)

		self._host = None
		self._user = None
		self._password = None

		assert_obj_has_keys(self._jsondata, "json", ["options"])
		options = self._jsondata["options"]
		assert_obj_has_keys(options, "options", ["name", "host", "user", "password", "targetdir"])

		self._host = options["host"]
		self._user = options["user"]
		self._password = options["password"]
		self._targetdir = options["targetdir"]

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

		if "copystats" in options:
			self._copystats = options["copystats"]

		if "processonly_types" in options:
			self._processonly_types = options["processonly_types"].split(",")

		assert_obj_has_keys(self._jsondata, "json", ["pathes"])

		self._config_loaded = True

	# def progressfiledownload(self, current, total):
	# 	p = False
	# 	if current == total:
	# 		p = True
	# 	elif self._last_dl_bytes > 0:
	# 		if current - self._last_dl_bytes > self._current_progress_divider:
	# 			p = True
	# 			self._last_dl_bytes = current
	# 	else:
	#
	# 		if total > self._current_progress_divider:
	# 			p = True
	# 			self._last_dl_bytes = current
	#
	# 	if p is True and self._show_copystats is True:
	# 		self.info("{}Downloaded: {}".format(bytes_to_unit(current, 1, True, False)))

	def _check_folder_with_options(self, remote_root, remote_path, options):
		accept = True

		if is_sequence_with_any_elements(options) and "exclude_folders" in options:
			exfolders = options["exclude_folders"]

			if not is_sequence_with_any_elements(exfolders):
				raise JobException("options['exclude_folders'] muss eine Liste von shell-file-patterns enthalten", 10)

			for exfolder in exfolders:
				if remote_root is not None and not Path(exfolder).is_absolute():
					exfolder = remote_root.joinpath(exfolder)

				if fnmatch(str(remote_path), str(exfolder)):
					accept = False
					break

		return accept

	def _check_file_with_options(
		self,
		options: dict,
		remoteroot: Path,
		localfile: Path,
		remotefile: Path,
		remote_stat,
		prepend_output_tabs="\t"
	):
		do_transfer = True

		if stat.S_ISLNK(remote_stat.st_mode):
			do_transfer = False

		if "overwrite_existing" in options:
			if localfile.exists() and options["overwrite_existing"] is False:
				do_transfer = False

		if do_transfer is True and "overwrite_newer" in options and options["overwrite_newer"] is True:
			if localfile.exists():
				stat_local = lstat(str(localfile))
				if stat_local.st_mtime <= remote_stat.st_mtime:
					self.info("{}File-Modification-Time is same as remote: {}".format(
						prepend_output_tabs,
						datetime.fromtimestamp(remote_stat.st_mtime),
					))
					do_transfer = False

		if do_transfer is True and "exclude_filter" in options:
			exclude_filter = options["exclude_filter"]
			if not string_is_empty(exclude_filter):
				if fnmatch(str(remotefile), exclude_filter):
					do_transfer = False

		if do_transfer is True and "include_filters" in options:
			include_filters = options["include_filters"]
			if is_sequence_with_any_elements(include_filters):
				do_transfer = False
				for include_filter in include_filters:
					if fnmatch(str(remotefile), include_filter):
						do_transfer = True
						break
			elif not string_is_empty(include_filters):
				if not fnmatch(str(remotefile), include_filters):
					do_transfer = False

		if do_transfer is True and "exclude_files" in options:
			exclude_files = options["exclude_files"]
			if is_sequence_with_any_elements(exclude_files):
				for exclude_file in exclude_files:
					if not string_is_empty(exclude_file):
						testfile = remoteroot.joinpath(exclude_file)
						if str(testfile) == str(remotefile):
							do_transfer = False
							break

		return do_transfer

	def _download_file(
			self,
			indentationlevel: int,
			sftp: paramiko.SFTPClient,
			remote_root: Path,
			localfile: Path,
			remote_filenode: Path,
			entry: BackupEntry
	):
		options = entry.get_options()
		has_options = is_sequence_with_any_elements(options)
		is_simulation = False

		if has_options is True:
			is_simulation = options["simulate"] if "simulate" in options and options["simulate"] is True else False

		t = repeat("\t", indentationlevel+1)

		if not is_simulation:
			stat_remote = sftp.lstat(str(remote_filenode))

		do_transfer = True

		self.info("{}Processing file: '{}'".format(t, remote_filenode))

		if has_options and not is_simulation:
			do_transfer = self._check_file_with_options(
				options,
				remote_root,
				localfile,
				remote_filenode,
				stat_remote,
				t
			)

		if do_transfer is False:
			self.info("{}Excluding '{}' due to file-options".format(
				t, remote_filenode
			))
		else:
			if is_simulation:
				self.info("{}Simulating download of file '{}'".format(t, remote_filenode))
			else:
				self.info("{}Downloading file (Total: {})".format(
					t, bytes_to_unit(stat_remote.st_size, 1, True, False))
				)

				self._current_progress_divider = get_filesize_progress_divider(stat_remote.st_size)

				sftp.get(str(remote_filenode), str(localfile))

				if self._copystats:
					self.info("{}Copying file modification dates".format(t))
					utime(str(localfile), (stat_remote.st_atime, stat_remote.st_mtime))

	def _process_directory(
		self,
		level: int,
		sftp: paramiko.SFTPClient,
		remote_root: Path,
		remote_path: Path,
		local_targetdir: Path,
		entry: BackupEntry
	):
		isroot = False

		if len(remote_path.parents) == 0:
			isroot = True

		if isroot:
			localdir = local_targetdir
		else:
			localdir = local_targetdir.joinpath(str(remote_path)[1:])

		remote_filenode = None
		tabs1 = repeat("\t", level)
		tabs2 = repeat("\t", level + 1)
		options = entry.get_options()
		if not self._check_folder_with_options(remote_root, remote_path, options):
			self.info("{}Excluding '{}' due to folder-options".format(
				tabs2,
				remote_path
			))
			return

		if not localdir.exists():
			self.info("{}Creating parent folders '{}'".format(tabs2, localdir))
			makedirs(str(localdir))
		try:
			has_options = not is_empty_dict(options)
			filelist = sftp.listdir(str(remote_path))
			recurse = False

			if has_options and "recurse" in options:
				recurse = options["recurse"]

			if len(filelist) > 0:
				for filenode in filelist:
					remote_filenode = remote_path.joinpath(filenode)
					remote_stat = sftp.lstat(str(remote_filenode))

					if stat.S_ISDIR(remote_stat.st_mode):
						if recurse is True:
							self.info("\n{}Recursing into sub-directory '{}'".format(
								tabs2, remote_filenode
							))
							self._process_directory(
								level + 1, sftp,
								remote_path,
								remote_filenode,
								local_targetdir,
								entry
							)
					else:
						localfile = localdir.joinpath(filenode)
						self._download_file(level, sftp, remote_root, localfile, remote_filenode, entry)
		except Exception as e:
			if isinstance(e, PermissionError):
				self.info("{}PermissionError while listing contents of {}\n".format(
					tabs2,
					remote_filenode if remote_filenode is not None else remote_path
				))
			elif isinstance(e, JobException):
				raise e
			else:
				raise JobException(e, 1)

	def process_directory(
		self,
		sftp: paramiko.SFTPClient,
		remote_root: Path,
		local_targetdir: Path,
		entry: BackupEntry
	):
		remotedir = Path(entry.get_path())

		self.info("\tProcessing folder: '{}'".format(remotedir))

		remote_exists = True

		try:
			stat_remote = sftp.stat(str(remotedir))
		except:
			remote_exists = False

		if not remote_exists:
			self.info("\tPath '{}' doesn't exist".format(
				remotedir
			))
		elif not stat.S_ISDIR(stat_remote.st_mode):
			self.info("\t{}Path '{}' is not a directory".format(
				remotedir
			))
		else:
			self._process_directory(0, sftp, remote_root, remotedir, local_targetdir, entry)

		self.info("Finished\n")

	def process_file(
		self,
		sftp: paramiko.SFTPClient,
		remote_root: Path,
		local_targetdir: Path,
		entry: BackupEntry
	):
		remote_filenode = entry.get_path()
		localdir = local_targetdir.joinpath(str(remote_filenode.parents[0])[1:])
		localfile = localdir.joinpath(remote_filenode.name)

		if not localdir.exists():
			self.info("Creating folder '{}'".format(localdir))
			makedirs(str(localdir))

		try:
			self._download_file(1, sftp, remote_root, localfile, remote_filenode, entry)
			# stat_remote = sftp.lstat(str(remote_filenode))
			# options = entry.get_options()
			# do_transfer = True
			#
			# self.info("\tProcessing file: '{}'".format(remote_filenode))
			#
			# if options is not None:
			# 	do_transfer = self._check_file_with_options(options, localfile, remote_filenode, stat_remote, "\t\t")
			#
			# if do_transfer is False:
			# 	self.info("\t\tExcluding '{}' due to file-options".format(
			# 		remote_filenode
			# 	))
			# else:
			# 	self.info("\t\tDownloading file (Total: {})".format(
			# 		bytes_to_unit(stat_remote.st_size, 1, True, False))
			# 	)
			#
			# 	self._current_progress_divider = get_filesize_progress_divider(stat_remote.st_size)
			# 	if "simulate" in options and options["simulate"] is True:
			# 		pass
			# 	else:
			# 		sftp.get(
			# 			str(remote_filenode), str(localfile),
			# 			self.progressfiledownload
			# 		)
			#
			# 	if self._copystats:
			# 		self.info("\tCopying file modification dates")
			# 		utime(str(localfile), (stat_remote.st_atime, stat_remote.st_mtime))

		except Exception as e:
			self.error("Error:\n{}".format(remote_filenode))
			self.error(e)

	def run(self):
		pathes = self._jsondata["pathes"]

		sftp = None
		""":type: paramiko.SFTPClient"""

		try:
			for entry in pathes:
				entryfilter = None
				if "type" not in entry:
					raise JobException(Exception("no type-key in entry"), 2)
				if "path" not in entry:
					raise JobException(Exception("no path-key in entry"), 3)

				entrytype = entry["type"]

				if "filter" in entry:
					entryfilter = entry["filter"]

				et = BackupEntryType.Unknown
				if entrytype == "file":
					et = BackupEntryType.File
				elif entrytype == "dir":
					et = BackupEntryType.Dir

				if "name" in entry:
					entryname = entry["name"]
				else:
					entryname = str(entrytype)

				e = BackupEntry(
					et, entryname,
					entryfilter, entry["path"],
					entry["options"] if "options" in entry else None
				)

				self._entries.append(e)

			if len(self._entries) == 0:
				raise JobException(Exception("No entrys found in json"), 4)

			if self._transport is None:
				self._transport = paramiko.Transport(self._host)

			self._transport.connect(username=self._user, password=self._password)

			if not self._transport.is_authenticated():
				raise JobException(Exception("could not authenticate"), 5)

			with paramiko.SFTPClient.from_transport(self._transport) as sftp:

				local_targetdir = Path(self._targetdir)
				""":type: Path"""

				d = True
				f = True

				if len(self._processonly_types) > 0:
					if "all" not in self._processonly_types:
						if "dir" not in self._processonly_types:
							d = False
						if "file" not in self._processonly_types:
							f = False

				if f is False and d is False:
					raise JobException(Exception(
						"If processonly_types is set in options, either dir or file has to be passed"),
						6
					)

				for entry in self._entries:
					self.info("Executing job-task '{}'".format(entry.get_name()))
					t = entry.get_type()
					if entry.should_skip():
						self.info("Skipping entry '{}' because options skip is active".format(
							entry.get_type()
						))
					else:
						if t is BackupEntryType.File and f is True:
							self.process_file(sftp, entry.get_path(), local_targetdir, entry)
						elif t is BackupEntryType.Dir and d is True:
							self.process_directory(sftp, entry.get_path(), local_targetdir, entry)

		except JobException as je:
			from traceback import format_exc
			self.error(str(format_exc()))
			return je.get_errcode()

		except paramiko.SSHException as se:
			from traceback import format_exc
			self.error(str(format_exc()))
			return 113

		finally:
			if sftp is not None:
				sftp.close()
			if self._transport is not None:
				self._transport.close()
