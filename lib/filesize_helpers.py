from math import floor, pow, log


def bytes_to_unit(bytesize: int, base1024: bool=False, print_suffix: bool=True, print_space: bool=True):
	"""
	Converts bytes to a string in another unit with an appropriate suffix
	:param bytesize: The amount of bytes you want to convert
	:param base1024: If the calculation should be made with 1024 bytes or 1000 bytes for one kilobyte
	:param print_suffix: Print a unit suffix (e.g. KB)
	:param print_space: Print a space between number and suffix
	:return: A localized number String (commata/digits after comma)
	"""
	size_name = ("Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

	basefactor = 1024 if base1024 else 1000

	if bytesize > 0:

		index = int(floor(log(bytesize, basefactor)))

		unitdivisor = pow(basefactor, index)

		bytes_in_unit = round(bytesize / unitdivisor, 2)

		if print_suffix:
			return "{}{}{}".format(bytes_in_unit, " " if print_space else "", size_name[index])
		else:
			return "{}".format(bytes_in_unit)
	else:
		return "0 Bytes"


def get_filesize_progress_divider(total_size: int):
	tb = total_size / 1000000000000
	gb = total_size / 1000000000
	mb = total_size / 1000000
	kb = total_size / 10000

	if tb > 1:
		d = 10000000000
	elif gb > 1:
		if gb >= 5:
			d = 50000000
		else:
			d = 10000000
	elif mb > 1:
		d = 500000
	elif kb > 1:
		if kb > 100:
			d = 50000
		else:
			d = 1000
	else:
		d = 10

	return d
