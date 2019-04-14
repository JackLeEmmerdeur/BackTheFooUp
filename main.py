import click
from modules.FileBackupUnit import FileBackup
from lib.helpers import list_to_str
from classes.LoggerFactory import LoggerFactory

backuptypes_str = list_to_str(["file", "image"], ", ", True, " or ", "'", "'")


@click.command()
@click.option("--configfile", type=click.File(mode='r'), help="Path to the configfile used for image- or filebackup")
@click.option("--backuptype", type=click.Choice(['file', 'image']), help="Either {}".format(backuptypes_str))
def backup(configfile, backuptype):
	factory = LoggerFactory("backup")
	if backuptype == "image":
		raise Exception("Backuptype 'image' not supported")
	fb = FileBackup(configfile, True, factory)
	fb.run()
	return 1


if __name__ == "__main__":
	exit(backup())