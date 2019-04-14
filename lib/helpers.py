import encodings
import sys
from codecs import encode
from datetime import datetime
from enum import Enum
from importlib import import_module
from importlib.machinery import SourceFileLoader
from inspect import getmembers, isbuiltin, currentframe, ismethod  # ,isfunction
from json import load as jsonload
from os import listdir as oslistdir, environ, makedirs, unlink as osunlink
from os.path import isdir as opisdir, expanduser as opexpanduser, isfile as opisfile, join as opjoin, dirname as opdirname
from pathlib import Path
from pkgutil import iter_modules, find_loader
from platform import system
from sys import exc_info
from traceback import format_exception
from typing import Union, List, Any
from unicodedata import normalize
from shutil import copy, rmtree
from os import walk
# from getpass import getuser
from chardet import detect
from chardet.universaldetector import UniversalDetector
from six import PY2
from six import string_types, text_type

if PY2:
	from cStringIO import StringIO
else:
	from io import StringIO


class UserFolderType(Enum):
	Desktop = ["XDG_DESKTOP_DIR", "desktop"]
	Download = ["XDG_DOWNLOAD_DIR", "download"]
	Templates = ["XDG_TEMPLATES_DIR", ""]
	PublicShare = ["XDG_PUBLICSHARE_DIR", "public"]
	Documents = ["XDG_DOCUMENTS_DIR", "documents"]
	Music = ["XDG_MUSIC_DIR", "music"]
	Pictures = ["XDG_PICTURES_DIR", "pictures"]
	Videos = ["XDG_VIDEOS_DIR", "videos"]
	Roaming = ["XDG_CONFIG", "roaming"]


def is_linux():
	return system().lower().find("linux") > -1


def is_function(var: Any) -> bool:
	return isbuiltin(var) or hasattr(var, '__call__')  # isfunction(var)


def is_method(var: Any) -> bool:
	return ismethod(var)


def is_boolean(var: Any) -> bool:
	return isinstance(var, bool)


def is_string(var: Any) -> bool:
	return isinstance(var, string_types)


def is_stringtype(obj: Any) -> bool:
	return is_unicode(obj) or is_string(obj)


def is_integer(var: Any) -> bool:
	return isinstance(var, int)


def is_integerish(var: Any) -> bool:
	"""stackoverflow.com/questions/1265665/python-check-if-a-string-represents-an-int-without-using-try-except"""
	i = str(var)
	return i == '0' or (i if i.find('..') > -1 else i.lstrip('-+').rstrip('0').rstrip('.')).isdigit()


def is_datetime(var: Any) -> bool:
	return isinstance(var, datetime)


def is_unicode(obj: Any) -> bool:
	return isinstance(obj, text_type)


def is_sequence(var: Any) -> bool:
	return (
		not hasattr(var, "strip") and
		hasattr(var, "__getitem__") or
		hasattr(var, "__iter__")
	)


def is_sequence_with_any_elements(tuple_or_list: Union[list, set, dict, range, frozenset, tuple, bytearray]) -> bool:
	if is_sequence(tuple_or_list) and len(tuple_or_list) > 0:
		return True
	return False


def is_empty_sequence(sequencevar: Union[list, set, dict, range, frozenset, tuple, bytearray]) -> bool:
	return not is_sequence(sequencevar) or len(sequencevar) == 0


def is_dict(var: Any) -> bool:
	return isinstance(var, dict)


def is_empty_dict(var: dict) -> bool:
	if var is None:
		return True
	a = not isinstance(var, dict)
	b = (len(var) == 0)
	return a and b


def is_native_integer(var):
	return isinstance(var, int)


def list_to_str(
		srclist: List[Any],
		div: str = ", ",
		use_prosaic: bool=False,
		prosaic_terminator: str="or",
		prepend_to_list_item=None,
		append_to_list_item=None
):
	t = ""

	if not is_sequence(srclist):
		return t

	c = len(srclist) - 1

	if c < 0:
		return t

	for (index, a) in enumerate(srclist):
		if index > 0:
			if use_prosaic:
				if index < c:
					t += div
				else:
					t += prosaic_terminator

			else:
				if index <= c:
					t += div

		if prepend_to_list_item is not None:
			t += prepend_to_list_item
		t += a
		if append_to_list_item is not None:
			t += append_to_list_item

	return t

def parse_boolean(val, default_if_not_parseable=False):
	b = default_if_not_parseable

	if is_boolean(val):
		b = val
	elif is_string(val):
		if not string_is_empty(val):
			bs = val.lower()
			if bs == "ja" or bs == "an" or bs == "yes" or bs == "true" or bs == "on" or bs == "1" or bs == "y":
				b = True
			elif bs == "nein" or bs == "aus" or bs == "no" or bs == "false" or bs == "off" or bs == "0" or bs == "n":
				b = False
	elif is_native_integer(val):
		b = val > 0
	return b


def nested_get(dic: dict, keys: List[str]) -> Any:
	"""
	Gets a value from a hierachically organized dict

	Example:
		print(nested_get({"a":{"b":{"c":10}}}, ["a", "b", "c"]))
		>>> 10

	:param dic: The dict of which to get the value for `keys`
	:param keys: A chain of keys
	:return: The value or None if key-chain could not be found
	"""
	if is_empty_dict(dic) or is_empty_sequence(keys):
		return dic
	d = dic
	for key in keys[:-1]:
		if key in d:
			d = d[key]
		else:
			return None
	if keys[-1] in d:
		return d[keys[-1]]
	return None


def nested_set(dic: dict, value: Any, create_missing: bool, keys: List[str]) -> dict:
	"""
	Taken from my answer on
	https://stackoverflow.com/questions/13687924/setting-a-value-in-a-nested-python-dictionary-given-a-list-of-indices-and-value/49290758#49290758
	Explanation there

	:param dic: A dict of hierachical key-values like {"a":{"b":{"c":1}}}
	:param value: The value you want to set to the key specified with `keys`
	:param create_missing: If False, values of nonexistant keys wont be created
	:param keys: A key-chain (e.g. ["a", "b", "c"])
	:return: The dict-parameter itself for method-chaining
	"""
	if is_empty_dict(dic) or is_empty_sequence(keys):
		return dic

	d = dic
	for key in keys[:-1]:
		if key in d:
			d = d[key]
		elif create_missing:
			d = d.setdefault(key, {})
		else:
			return dic
		if keys[-1] in d or create_missing:
			d[keys[-1]] = value
	return dic


def test_false_or_none(var: bool) -> bool:
	if is_boolean(var):
		return var is False
	else:
		return var is None


def module_exists(modulename):
	"""
	Basically code by yarbelk
	https://stackoverflow.com/questions/14050281/how-to-check-if-a-python-module-exists-without-importing-it
	"""
	return find_loader(modulename) is not None


def varexists_locally(varname: str) -> bool:
	parentlocalvars = currentframe().f_back.f_locals
	return varname in parentlocalvars


def varexists_globally(varname: str) -> bool:
	parentglobals = currentframe().f_back.f_globals
	return varname in parentglobals


def obj_has_attr(obj, attrname):
	if obj is not None:
		return hasattr(obj, attrname)


def assert_obj_has_keys(obj: object, objtype: str, keys: List[str]):
	if obj is None or type(obj) is not dict:
		raise Exception("obj is not of type dict")
	if keys is None or len(keys) == 0:
		raise Exception("no obj")
	for key in keys:
		if key not in obj:
			raise Exception("Missing key '{}' in object({})".format(key, objtype))


def get_methods(obj):
	getmembers(obj, predicate=ismethod)


def get_members(obj, predicate=None):
	getmembers(obj, predicate)


def call_vararg_with_seq(tpl, fnc):
	return fnc(*tpl)


def print_args(*args):
	for n in range(0, len(args)):
		if not string_is_empty(args[n]):
			print(args[n])


def fill(char: str, filllen: int) -> str:
	s = ""
	for i in range(0, filllen):
		s += char
	return s


def mkdir(dirpath, octalmode=0o777, throw_if_exists=False):
	return makedirs(dirpath, octalmode, not throw_if_exists)


def delete_file(filepath, raiseexceptions=False):
	if string_is_empty(filepath):
		if raiseexceptions:
			raise Exception("No valid filepath given.")
		else:
			return False
	if file_exists(filepath):
		try:
			osunlink(filepath)
			return True
		except Exception as e:
			if raiseexceptions:
				raise e
			return False
	else:
		if raiseexceptions:
			raise Exception("File {} does not exists. Nothin to delete.".format(filepath))
		else:
			return False


def copy_file(filepathfrom, filepathto):
	p1 = Path(filepathfrom)
	p2 = Path(filepathto)
	if not p1.exists():
		raise(Exception("filepathfrom {} does not exist".format(filepathfrom)))
	copy(str(p1), str(p2))


def filepath_to_tmp(filepath: str):
	p = Path(filepath).absolute()
	filename_temp = p.stem
	filename_exts = p.suffixes
	ok = False
	i = -1
	while not ok:
		p2 = p.parent.joinpath(filename_temp + "_tmp" + ("" if i == -1 else str(i)) + ".".join(filename_exts))
		if p2.exists():
			i += 1
		else:
			ok = True
	return str(p2.resolve())


def filepath_verify_extension(filepath: str, ext: str, case_sensitive=False) -> bool:
	if string_is_empty(filepath) or string_is_empty(ext):
		return False

	p = Path(filepath)

	if string_is_empty(p.suffix):
		return False

	e = p.suffix[1:] if case_sensitive else p.suffix[1:].lower()

	if not case_sensitive:
		ext = ext.lower()

	return e == ext


def filefilter_to_extension(filefilter: str) -> str:
	p1 = filefilter.find("(")
	p2 = filefilter.find(")")

	if p1 > -1 and p2 > -1:
		ff = filefilter[p1+1:p2]
		if ff.startswith("*."):
			ff = ff[2:]
		elif ff.startswith("."):
			ff = ff[1:]
		return ff
	return filefilter


def folder_exists(folderpath: str) -> bool:
	if not string_is_empty(folderpath):
		return opisdir(folderpath)
	return False


def file_exists(filevar: Union[str, int]) -> bool:
	if isinstance(filevar, string_types) or isinstance(filevar, text_type):
		return opisfile(filevar)
	else:
		return False


def read_json(filevar: Union[str, int], codec=None) -> object:
	with open(filevar, 'rt') as f:
		jsonobj = jsonload(f, encoding=("utf-8" if codec is None else codec))
	return jsonobj


def clean_recursive(p: Path, items: List[str]):
	if items is None or len(items) < 1:
		return

	roots = []
	for root, dirs, files in walk(p.absolute()):
		for item in items:
			if root.find(item) > -1:
				roots.append(root)
				break

	rl = len(roots)

	for i in range(rl - 1, -1, -1):
		rmtree(roots[i])


def get_currentdir():
	return Path.cwd()


def get_roaming_apppath(organization_dirname: str, app_dirname: str) -> Path:
	roaming = get_user_folder(UserFolderType.Roaming)
	if not roaming.exists():
		raise (Exception("Could not open user-path"))

	roamingorgpath = roaming.joinpath(organization_dirname)

	if not roamingorgpath.exists():
		makedirs(str(roamingorgpath.absolute()))

	if not roamingorgpath.exists():
		raise (Exception("Could not open user-organization-path"))

	roamingapppath = roamingorgpath.joinpath(app_dirname)

	if not roamingapppath.exists():
		makedirs(str(roamingapppath.absolute()))

	if not roamingapppath.exists():
		raise (Exception("Could not open user-app-path"))

	return roamingapppath


def get_user_folder_base() -> Path:
	if is_linux():
		basepath = Path(opexpanduser('~'))
	else:
		basepath = Path(environ['USERPROFILE'])
	return basepath


def get_user_folder(foldertype: UserFolderType) -> Path:
	"""
	Todo: Use http://ginstrom.com/code/winpaths.html on windows
	https://stackoverflow.com/questions/626796/how-do-i-find-the-windows-common-application-data-folder-using-python/626927#626927
	Maybe use the newer not deprecated method (not like in winpaths)
	:param foldertype:
	:return:
	"""
	userfolder = None

	if is_linux():
		userrootpath = Path(opexpanduser('~'))
		if foldertype.value[0] == "XDG_CONFIG":
			userfolder = userrootpath.joinpath(".config")
		else:

			xdgconfig = userrootpath.joinpath(".config", "user-dirs.dirs")

			if xdgconfig.exists() and xdgconfig.is_file():
				with open(str(xdgconfig), "rt") as xdgconfigfile:
					for row in xdgconfigfile:
						row = row.strip()
						if string_is_empty(row) or row[0] == "#":
							continue
						equalpos = row.find("=")
						if equalpos == -1:
							continue
						xdgpathval = row[equalpos+1:].strip(" \"\t\r\n")
						xdgpathname = row[0:equalpos].strip()
						if foldertype.value[0] == xdgpathname:
							xdgpathval = xdgpathval.replace("$HOME", str(userrootpath))
							userfolder = Path(xdgpathval)
							break
			else:
				# Todo: Do something stupid if xdg is not available on current distro
				pass
	else:
		basepath = Path(environ['USERPROFILE'])

		if foldertype.value[1] == "roaming":
			userfolder = basepath.joinpath("AppData", "Roaming")
		else:
			userfolder = Path(basepath, foldertype.value[1])

	return userfolder


def detect_from_unicode(uctext):
	if uctext is not None:
		t = type(uctext)
		if is_unicode(t):
			return detect(bytes(encode(uctext, "utf-8")))['encoding']
		elif t is str:
			return detect(bytes(uctext))['encoding']
	return None


def string_equal_utf8(obj1, obj2, case_sensitive=True):
	f1n = obj1 is None
	f2n = obj2 is None

	if f1n and f2n:
		return True
	elif f1n or f2n:
		return False
	else:
		f1u = is_unicode(obj1)
		f2u = is_unicode(obj2)
		f1s = is_string(obj1)
		f2s = is_string(obj2)

		if not f1s and not f1u:
			obj1 = str(obj1)
		if not f2s and not f2u:
			obj2 = str(obj2)

		if f1u and f2u:
			eq = string_equal(obj1, obj2, case_sensitive)
		elif f1u and not f2u:
			eq = string_equal(obj1, decode(obj2, "utf-8"), case_sensitive)
		else:
			eq = string_equal(decode(obj1, "utf-8"), obj2, case_sensitive)
		return eq


def string_equal(str1, str2, case_sensitive=True):
	if case_sensitive:
		return str1 == str2
	# Do not call string_iequal here (method-call-micro-optimized)
	e1 = string_is_empty(str1)
	e2 = string_is_empty(str2)
	if e1 and e2:
		return True
	elif e1 or e2:
		return False
	else:
		if str1.lower() == str2.lower():
			return True
		else:
			return False


def string_iequal(str1, str2):
	e1 = string_is_empty(str1)
	e2 = string_is_empty(str2)
	if e1 and e2:
		return True
	elif e1 or e2:
		return False
	else:
		if str1.lower() == str2.lower():
			return True
		else:
			return False


def repeat(text: str, times: int):
	t = ""
	for i in range(0, times):
		t += text
	return t


def strip(text):
	return text.lstrip().rstrip()


def striplower(text):
	return text.lstrip().rstrip().lower()


def wrap_str_fast(linelen, text):
	if string_is_empty(text):
		return text
	textlen = len(text)
	if textlen < linelen:
		return text
	d = textlen / linelen
	r = textlen % linelen

	with StringIO("utf-8") as sio:
		# with StringIOEx("utf-8") as sio:
		i = 0
		lastpos = 0
		while i < d:
			if i > 0:
				sio.write("\n")
			lastpos = i * linelen + linelen
			sio.write(text[i * linelen:lastpos])
			i += 1
		if r > 0:
			sio.write("\n")
			sio.write(text[lastpos:])
	return sio.getvalue()


def case_normalize(text):
	if PY2:
		enc = detect_from_unicode(text)
		if enc is not None:
			if enc.lower() != "ascii":
				if is_unicode(text):
					text = normalize("NFD", text).encode('ascii', 'ignore')
				else:
					if PY2:
						text = normalize("NFKD", unicode(text, enc)).encode('ascii', 'ignore')
			return text
	else:
		return normalize("NFD", text)
	return "NOTNORMALIZED"


def detect_file_encoding_str(filepath: Union[str, int]) -> Any:
	"""
	Detects the encoding of a file with the chardet library
	Returns the name of the encoding as opposed to the detect_file_encoding library,
	which returns an UniversalDetector-Instance
	:param filepath: Path to the file you want to check or int-filedescriptor
	:return: A string naming the possible encoding of the file or None on failure
	"""
	u = detect_file_encoding(filepath, None)
	if u is not None and hasattr(u, "result") and u.result is not None and "encoding" in u.result:
		return u.result["encoding"]
	return None


def detect_file_encoding(filepath: Union[str, int], universal_detector: UniversalDetector=None) -> UniversalDetector:
	"""
	Detects the encoding of a file with the chardet library
	Stops as soon the chardet-lib is confidential to have found one

	:param filepath: Path to the file you want to check or int-filedescriptor
	:param universal_detector: If not provided a new UniversalDetector-instance is created every time
	:return: An UniversalDetector-Instance with a property named "result", which contains a
	dict-instance like {'encoding': 'EUC-JP', 'confidence': 0.99}
	"""
	u = UniversalDetector() if universal_detector is None else universal_detector
	i = 0

	with open(filepath, 'rb') as f:
		for l in f:
			u.feed(l)
			if u.done:
				break
			i += 1
	u.close()
	return u


def get_reformatted_exception(msg, e) -> str:
	tb = ""
	excfmtlist = format_exception(type(e), e, exc_info()[2])
	for (index, excfmtitem) in enumerate(excfmtlist):
		if index > 0:
			tb += "\r\n"
		tb += "\t" + excfmtitem
	return "{}\r\n{}".format(msg, tb)


def string_is_empty(
	thetext: string_types,
	preserve_whitespace: bool=False,
	check_strip_availability: bool=False
) -> bool:
	"""
	Checks if `thetext` is emtpy and returns True if so.

	Example:
	>>> string_is_empty("  ")
	True
	>>> string_is_empty("  ", True)
	False
	>>> string_is_empty("  ", False)
	True

	:param thetext: The string to check for emptiness
	:param preserve_whitespace: If True, blankspaces will not count as empty
	:param check_strip_availability: Checks if `thetext is a string-type via availability of strip-method (esotheric)
	:return: True if `thetext` is empty
	:rtype: bool
	"""
	if thetext is None:
		return True
	isstring = False
	if check_strip_availability:
		isstring = hasattr(thetext, "strip")
	elif is_string(thetext) or is_unicode(thetext):
		isstring = True
	if isstring or isinstance(thetext, bytes):
		return len(thetext if preserve_whitespace else thetext.strip()) < 1
	else:
		return True


def strings_in_string(haystack: str, needles: List[str]):
	"""
	Checks if needle is found in haystack and returns True if so
	For more info consult `strings_in_string_i`
	"""
	return strings_in_string_i(haystack, needles) > -1


def strings_in_string_i(haystack: str, needles: List[str]):
	"""
	Checks if one of the needle-items is contained within `haystack`
	and returns the relevant first found item index from `needles`

	Example:
	>>> print(strings_in_string_i("doh!", ["duh", "doo", "doh!"]))
	2

	>>> print(strings_in_string_i("doh!", ["duh", "doh", "doh!"]))
	1

	>>> print(strings_in_string_i("doh", ["duh", "doo", "dho"]))
	-1

	:param str haystack: The string to search within
	:param list needles: The list of str's to search within haystack
	:return: The index of the needle-item which was first found in haystack,
	otherwise if nothing found or parameters invalid: -1
	:rtype: int
	"""
	found = -1

	if is_string(needles):
		needles = [needles]

	if not string_is_empty(haystack) and not is_empty_sequence(needles):
		for index, needle in enumerate(needles):
			if not string_is_empty(needle) and needle in haystack:
				found = index
				break
	return found


def listcodecs():
	"""
	Lists all available codecs in the python environment
	see: https://stackoverflow.com/questions/1728376/get-a-list-of-all-the-encodings-python-can-encode-to

	:return: a set of str's representing encoding-names
	:rtype: set
	"""
	false_positives = {"aliases"}
	found = set(name for imp, name, ispkg in iter_modules(encodings.__path__) if not ispkg)
	found.difference_update(false_positives)
	return found


def iter_text_lines(text: string_types):
	sio = StringIO(text)

	for line in sio:
		yield line.strip()


def count_file_rows(filevar: Union[str, int], encoding: str= "utf_8") -> int:
	"""
	Counts rows in a file, using the systems lineseparator

	:param Union[str,int] filevar: Either a filename(str) or a filedescriptor(int)
	:param str encoding: The files encoding (default 'utf_8')
	:return:
	"""
	i = 0
	with open(filevar, mode="rt", encoding=encoding if string_is_empty(encoding) else encoding) as f:
		for i, l in enumerate(f):
			pass
	return i


def get_executable_dirname(executable=None):
	if getattr(sys, 'frozen', False):
		# frozen
		parentdir = opdirname(sys.executable)
	else:
		# start from main.py
		p = Path(executable if executable is not None else __file__)
		parentdir = str(p.parent.absolute())
	return parentdir


def _load_modules(parentdir_path: str, parent_package_names: list, exclude_contains_list: list=None, submodule_suffix=None):
	pluginfiles = oslistdir(parentdir_path)

	relmodules = []

	if parent_package_names is not None:
		for parent_package_name in parent_package_names:
			loader = SourceFileLoader(parent_package_name[0], parentdir_path + "/" + parent_package_name[1])
			relmodules.append(loader.load_module(parent_package_name[0]))

	submodule_suffix_r = ("" if submodule_suffix is None else ".TVPlugin")

	for pluginfile in pluginfiles:
		subdir = opjoin(parentdir_path, pluginfile)

		if strings_in_string(subdir, exclude_contains_list):
			continue

		if not opisdir(subdir):
			continue

		subdirfiles = oslistdir(subdir)

		for subdirfile in subdirfiles:
			if not strings_in_string(subdirfile, exclude_contains_list) and ".py" in subdirfile:
				loader = SourceFileLoader(
					pluginfile + submodule_suffix_r,
					parentdir_path + "/" + pluginfile + "/" + pluginfile + ".py"
				)
				relmodules.append(loader.load_module(pluginfile + submodule_suffix_r))

	return relmodules


def load_module(parentdir_path: str, parent_package_names: list, module_name: str, submodule_suffix: str=None):
	relmodulenames = _load_modules(parentdir_path, parent_package_names, None, submodule_suffix)
	module = None

	for relmodulename in relmodulenames:
		if relmodulename == "." + module_name:
			module = import_module(relmodulename, package=parent_package_names)
			break
	return module


def load_modules(parentdir_path: str, parent_package_names: list, exclude_contains_list: list=None, submodule_suffix:str=None):
	return _load_modules(parentdir_path, parent_package_names, exclude_contains_list, submodule_suffix)
