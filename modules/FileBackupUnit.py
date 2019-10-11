import stat
from datetime import datetime
from fnmatch import fnmatch
from os import lstat
from os import makedirs, utime
from pathlib import Path
from typing import Dict, List
import paramiko
from fileutilslib.disklib.filetools import get_filesize_progress_divider, bytes_to_unit, path_from_partindex
from fileutilslib.misclib.helpertools import assert_obj_has_keys, is_sequence_with_any_elements, repeat, \
	string_is_empty, is_empty_dict, is_integer
from classes.BackupEntry import BackupEntryType, BackupEntry
from classes.JobException import JobException
from classes.LoggerFactory import LoggerFactory
from modules.Unit import Unit


class FileBackupUnit(Unit):
	"""Used for downloading dirs and single files from a remote ssh host and syncing them to local dirs

	Attributes:
		_transport 	Used for the current ssh session
	"""
	_entries = None

	_host = None
	""":type: str"""

	_user = None
	""":type: str"""

	_password = None
	""":type: str"""

	_keyfile = None
	""":type: str"""

	_targetdir = None
	""":type: str"""

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

	def __init__(
		self,
		configfile,
		show_copystats=False,
		logfactory: LoggerFactory=None,
		group: str=None,
		ignoreoptions: List[str]=None
	):
		super().__init__(
			"FileBackup",
			configfile,
			["name", "host", "user", "password", "targetdir"],
			self.on_config_loaded,
			logfactory,
			group,
			ignoreoptions
		)

		self._entries = []
		self._show_copystats = show_copystats

	def __del__(self):
		if self._transport is not None:
			self._transport.close()

	def __str__(self):
		dbg = super().__str__()
		if "paths" in self._jsondata:
			jobs = "{}\n{}\n{}\n{} Jobs defined\n".format(
				self._div, self._unit_name, self._div,
				len(self._jsondata["pathes"])
			)

			dbg = jobs + dbg
		return dbg

	def on_config_loaded(self, jsondata: Dict):
		if is_empty_dict(jsondata):
			raise Exception("no config json-data found")
		self.info("Configdata loaded")
		self._jsondata = jsondata

		self._host = None
		self._user = None
		self._password = None

		options = self._jsondata["options"]

		self._host = options["host"]
		self._user = options["user"]
		self._password = options["password"]
		self._targetdir = options["targetdir"]

		if "keyfile" in options:
			self._keyfile = options["keyfile"]

		if "copystats" in options:
			self._copystats = options["copystats"]

		if "processonly_types" in options:
			self._processonly_types = options["processonly_types"].split(",")

		assert_obj_has_keys(self._jsondata, "json", ["pathes"])

	def _check_option_ignored(self, optionname: str):
		if is_sequence_with_any_elements(self._ignoreoptions):
			if optionname in self._ignoreoptions:
				return True
		return False

	def _check_folder_with_options(self, remote_root, remote_path, options):
		accept = None

		if is_sequence_with_any_elements(options):
			if "exclude_folders" in options and not self._check_option_ignored("exclude_folders"):
				exfolders = options["exclude_folders"]

				if not is_sequence_with_any_elements(exfolders):
					raise JobException("options['exclude_folders'] has to contain a list of shell-file-patters", 10)

				for exfolder in exfolders:
					if remote_root is not None and not Path(exfolder).is_absolute():
						exfolder = remote_root.joinpath(exfolder)

					if fnmatch(str(remote_path), str(exfolder)):
						accept = "EXCLUDE_FOLDERS"
						break

			if (
				accept is None and
				"group" in options and
				not string_is_empty(self._group) and
				not self._check_option_ignored("group")
			):
				group = options["group"]
				if not string_is_empty(group):
					if group != self._group:
						accept = "GROUP"

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
		do_transfer = None

		if stat.S_ISLNK(remote_stat.st_mode):
			do_transfer = "IS_LINK"

		if "overwrite_existing" in options and not self._check_option_ignored("overwrite_existing"):
			if localfile.exists() and options["overwrite_existing"] is False:
				do_transfer = "OVERWRITE_EXISTING"

		if (
			do_transfer is None and
			"overwrite_newer" in options and
			options["overwrite_newer"] is True and
			not self._check_option_ignored("overwrite_newer")
		):
			if localfile.exists():
				local_stat = lstat(str(localfile))
				if local_stat.st_mtime >= remote_stat.st_mtime:
					self.info("{}Remote file modification date '{}' is not newer than local modification date '{}'".format(
						prepend_output_tabs,
						datetime.fromtimestamp(remote_stat.st_mtime),
						datetime.fromtimestamp(local_stat.st_mtime),
					))
					do_transfer = "OVERWRITE_NEWER"

		if (
			do_transfer is None and
			"exclude_filter" in options and
			not self._check_option_ignored("exclude_filter")
		):
			exclude_filter = options["exclude_filter"]
			if not string_is_empty(exclude_filter):
				if fnmatch(str(remotefile), exclude_filter):
					do_transfer = "EXCLUDE_FILTER"

		if (
			do_transfer is None and
			"include_filters" in options and
			not self._check_option_ignored("include_filters")
		):
			include_filters = options["include_filters"]
			if is_sequence_with_any_elements(include_filters):
				do_transfer = "INCLUDE_FILTERS"
				for include_filter in include_filters:
					if fnmatch(str(remotefile), include_filter):
						do_transfer = None
						break
			elif not string_is_empty(include_filters):
				if not fnmatch(str(remotefile), include_filters):
					do_transfer = "INCLUDE_FILTERS"

		if (
			do_transfer is None and
			"exclude_files" in options and
			not self._check_option_ignored("exclude_files")
		):
			exclude_files = options["exclude_files"]
			if is_sequence_with_any_elements(exclude_files):
				for exclude_file in exclude_files:
					if not string_is_empty(exclude_file):
						testfile = remoteroot.joinpath(exclude_file)
						if str(testfile) == str(remotefile):
							do_transfer = "EXCLUDE_FILES"
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

		indentation = repeat("\t", indentationlevel+1)

		if not is_simulation:
			stat_remote = sftp.lstat(str(remote_filenode))

		do_transfer = True

		self.info("{}Processing file: '{}'".format(indentation, remote_filenode))

		if has_options and not is_simulation:
			do_transfer = self._check_file_with_options(
				options,
				remote_root,
				localfile,
				remote_filenode,
				stat_remote,
				indentation
			)

		if do_transfer is not None:
			self.info("{}Excluding '{}' due to json-file-option {}".format(
				indentation, remote_filenode, do_transfer
			))
		else:
			if is_simulation:
				self.info("{}Simulating download of file '{}'".format(indentation, remote_filenode))
			else:
				self.info("{}Downloading file (Total: {})".format(
					indentation, bytes_to_unit(stat_remote.st_size, 1, True, False))
				)

				self._current_progress_divider = get_filesize_progress_divider(stat_remote.st_size)

				sftp.get(str(remote_filenode), str(localfile))

				if self._copystats:
					self.info("{}Copying file modification dates".format(indentation))
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
		options = entry.get_options()
		has_options = not is_empty_dict(options)
		path_rootindex = None
		recurse = False

		if has_options:
			if "recurse" in options and not self._check_option_ignored("recures"):
				recurse = options["recurse"]
			if "path_rootindex" in options and not self._check_option_ignored("path_rootindex"):
				path_rootindex = options["path_rootindex"]

		if len(remote_path.parents) == 0:
			isroot = True

		if isroot:
			localdir = local_targetdir
		else:
			if path_rootindex is not None and is_integer(path_rootindex):
				f = path_from_partindex(remote_path, path_rootindex)
				localdir = local_targetdir.joinpath(f)
			else:
				localdir = local_targetdir.joinpath(str(remote_path)[1:])

		remote_filenode = None
		tabs2 = repeat("\t", level + 1)

		do_transfer = self._check_folder_with_options(remote_root, remote_path, options)

		if do_transfer is not None:
			self.info("{}Excluding '{}' due to json-folder-option {}".format(
				tabs2,
				remote_path,
				do_transfer
			))
			return

		if not localdir.exists():
			self.info("{}Creating parent folders '{}'".format(tabs2, localdir))
			makedirs(str(localdir))

		try:
			filelist = sftp.listdir(str(remote_path))

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

		except Exception as e:
			self.error("Error:\n{}".format(remote_filenode))
			self.error(e)

	def run(self):
		self.info("Starting unit task")

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

			self.info("Trying to connect to SSH-Host {}".format(self._host))

			if self._transport is None:
				self._transport = paramiko.Transport(self._host)

			if not string_is_empty(self._keyfile):
				key = paramiko.RSAKey.from_private_key_file(self._keyfile)
				self.info("With Key:".format(key.get_name()))
				self._transport.connect(username=self._user, pkey=key)
			else:
				self.info("With Username/Password")
				self._transport.connect(username=self._user, password=self._password)

			if not self._transport.is_authenticated():
				raise JobException(Exception("could not authenticate"), 5)

			self.info("Successfully connected!")
			self.info("Opening SFTP-Channel from transport")

			with paramiko.SFTPClient.from_transport(self._transport) as sftp:

				self.info("Successfully opened SFTP-Channel!")

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