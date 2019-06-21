Things to do to test the app in pycharm:
	1. 	sudo visudo
		Add following line:
			pycharm ALL=(ALL) NOPASSWD: ALL

	2. 	Create a start script for pycharm:
			#!/usr/bin/env bash
			export PATH=/sbin:$PATH
			/opt/pycharm-community-2018.1.2/bin/pycharm.sh

	3. Launch via startscript

	4. On console:
		sudo fdisk -l