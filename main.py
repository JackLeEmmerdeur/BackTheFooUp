import click
from fileutilslib.classes.ConsoleColors import ConsoleColors, ConsoleColor
from fileutilslib.misclib.helpertools import list_to_str, get_reformatted_exception
from classes.LoggerFactory import LoggerFactory
from modules.FileBackupUnit import FileBackupUnit
from modules.ImageBackupUnit import ImageBackupUnit
from classes.PythonLiteralOption import PythonLiteralOption

backuptypes_str = list_to_str(["ssh", "image"], ", ", True, " or ", "'", "'")


@click.command()
@click.option("--configfile", type=click.File(mode='r'), help="Path to the configfile used for image- or filebackup")
@click.option("--backuptype", type=click.Choice(['ssh', 'image']), help="Either {}".format(backuptypes_str))
@click.option(
	"--group",
	type=str,
	required=False,
	help=
	"Specifiy 'cmdline_group' in an 'option'-object in a json-config and "
	"reference it here, to trigger just that backup-unit."
)
@click.option(
	"--ignoreoptions",
	# required=False,
	cls=PythonLiteralOption,
	default='[]',
	help=
	"A list of backup-unit-options that should be ignored. Format: '[\"skip\", \"overwrite_newer\"]'"
)
def backup(configfile, backuptype, group, ignoreoptions):
	try:
		factory = LoggerFactory("backup")
		if backuptype == "image":
			b = ImageBackupUnit(configfile, factory)
		elif backuptype == "ssh":
			b = FileBackupUnit(configfile, True, factory, group, ignoreoptions)
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
