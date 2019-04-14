# from plumbum import local
# from Helpers import string_equal_utf8, striplower, strip
# from pathlib import Path
# from fdisklist import fdisklist
#
#
# try:
# 	devs = fdisklist(True)
#
# 	print()
#
# 	mydev = input("Please type the path of the device you want to backup (shortly after Disk, e.g. /dev/sdf):\n")
# 	mydev = strip(mydev)
# 	devok = False
#
# 	for dev in devs:
# 		if string_equal_utf8(dev["path"], mydev, False):
# 			devok = True
#
# 	if not devok:
# 		raise Exception("Device '" + mydev + "' not found")
#
# 	mydev = Path(mydev)
#
# 	dd = local["dd"]
#
# 	fp = input("Please type the filepath of the image you want to create:\n")
# 	fp = strip(fp)
# 	fp = Path(fp)
#
# 	fpexists = fp.exists()
#
# 	if fp.is_dir():
# 		raise Exception("Path is a directory")
#
# 	if fpexists:
# 		print("\033[93mThe image already exists")
# 		yn = striplower(input("Do you want to delete it (y/n):\033[0m\n"))
# 		if yn == 'y':
# 			fpexists = False
# 			remove(fp.absolute())
#
# 	if fpexists:
# 		raise Exception("Not writing image")
#
# 	dd["if=" + mydev + " of=" + fp + " status=progress bs=1M"]
#
# except Exception as e:
# 	# print(reformat_exception("GENERAL ERROR", e))
# 	print()
# 	print("\033[91m" + str(e) + "\033[0m")
# except (KeyboardInterrupt, SystemExit):
# 	print("DOH!")
