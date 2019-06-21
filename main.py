import click
from modules.FileBackupUnit import FileBackup
from modules.ImageBackupUnit import ImageBackup
from fileutilslib.misclib.helpertools import list_to_str, get_reformatted_exception
from classes.LoggerFactory import LoggerFactory
from classes.ConsoleColors import ConsoleColors, ConsoleColor

backuptypes_str = list_to_str(["file", "image"], ", ", True, " or ", "'", "'")


@click.command()
@click.option("--configfile", type=click.File(mode='r'), help="Path to the configfile used for image- or filebackup")
@click.option("--backuptype", type=click.Choice(['ssh', 'image']), help="Either {}".format(backuptypes_str))
def backup(configfile, backuptype):
	try:
		factory = LoggerFactory("backup")
		if backuptype == "image":
			b = ImageBackup(configfile, factory)
		elif backuptype == "ssh":
			b = FileBackup(configfile, True, factory)
		else:
			raise Exception("Backup-Unit-Type invalid")
		b.run()
	except Exception as e:
		print(ConsoleColor.colorline(get_reformatted_exception("Error in backup-function", e), ConsoleColors.FAIL))
		print(ConsoleColor.colorline(str(e), ConsoleColors.FAIL))
		return 2
	except (KeyboardInterrupt, SystemExit):
		print(ConsoleColor.colorline("Application killed via CTRL+C", ConsoleColors.FAIL))
		return 3
	else:
		return 1


if __name__ == "__main__":
	exit(backup())

