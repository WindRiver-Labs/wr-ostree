#!/bin/sh

#  This script is supposed to run on intel-x86 target with grub-efi installed.
#
#* Copyright (c) 2018 Wind River Systems, Inc.
#* 
#* This program is free software; you can redistribute it and/or modify
#* it under the terms of the GNU General Public License version 2 as
#* published by the Free Software Foundation.
#* 
#* This program is distributed in the hope that it will be useful,
#* but WITHOUT ANY WARRANTY; without even the implied warranty of
#* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#* See the GNU General Public License for more details.
#* 
#* You should have received a copy of the GNU General Public License
#* along with this program; if not, write to the Free Software
#* Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

UPGRADE_ROOTFS_DIR=""
UPGRADE_BOOT_DIR=""
UPGRADE_ESP_DIR=""
BACKUP_PART_INDICATOR="_b"
#BOOTCMD=$(cat /proc/bootcmd)
GRUB_EDITENV_BIN=$(which grub-editenv)
GRUB_ENV_FILE="/boot/efi/EFI/BOOT/pulsar.env"
ROLLBACK_VAR="rollback_part"
BOOTMODE_VAR="boot_mode"
BOOT_VAR="boot_part"
ROOT_VAR="root_part"
MOUNT_FLAG="rw,noatime,iversion"

[ -f $GRUB_EDITENV_BIN ] || {
	echo "grub-editenv is not found on target."
	echo "This script should run on intel-x86 platform with grub-efi installed!"
	exit 1
}

[ -f $GRUB_ENV_FILE ] || {
	echo "Grub env file /boot/efi/EFI/BOOT/pulsar.env is not found, aborting."
	exit 1
}

# retrieve 
get_grub_env_var() {
	local env_var=$1
	local env_val=$($GRUB_EDITENV_BIN $GRUB_ENV_FILE list |grep $env_var | cut -f 2 -d=)

	echo "$env_val"
}

cleanup() {
	umount $UPGRADE_ESP_DIR 
	umount $UPGRADE_BOOT_DIR 
	umount $UPGRADE_ROOTFS_DIR

	rm -rf $UPGRADE_ROOTFS_DIR	
}
# get the label name for boot partition to be upgraded
get_upgrade_part_label() {
	local labelroot=`cat /proc/cmdline |tr " " "\n" |grep ostree_root | awk -F '=' '{print $3}'`
	local labelboot=`cat /proc/cmdline |tr " " "\n" |grep ostree_boot | awk -F '=' '{print $3}'`

	echo "$labelroot" | fgrep "${BACKUP_PART_INDICATOR}" >> /dev/null
	if [ $? -ne 0 ]; then
		UPGRADE_ROOT_LABEL="${labelroot}${BACKUP_PART_INDICATOR}"
		UPGRADE_BOOT_LABEL="${labelboot}${BACKUP_PART_INDICATOR}"
		ROOLBACK_VAL=""
		BOOTMODE_VAL="${BACKUP_PART_INDICATOR}"
	else
		UPGRADE_ROOT_LABEL=`echo "${labelroot}" |sed "s/${BACKUP_PART_INDICATOR}//g"`
		UPGRADE_BOOT_LABEL=`echo "${labelboot}" |sed "s/${BACKUP_PART_INDICATOR}//g"`
		ROOLBACK_VAL="${BACKUP_PART_INDICATOR}"
		BOOTMODE_VAL=""
	fi


	ROOLBACK_VAL=$(get_grub_env_var $ROLLBACK_VAR)

	[ -z $ROOLBACK_VAL ] && {

		ROOLBACK_VAL="${BACKUP_PART_INDICATOR}"
		BOOTMODE_VAL=""
       	} || {
		ROOLBACK_VAL=""
		BOOTMODE_VAL="${BACKUP_PART_INDICATOR}"
	}

	return 0
}

# ESP device
get_esp_dev() {
	mount |grep /boot/efi | cut -f 1 -d " "
}

create_dir() {
	local dir="$1"

	if [ ! -d "$dir" ]; then
	        mkdir -p "$dir" || return 1
	fi

	return 0
}

#arg1 ROOT label
#arg2 BOOT label
#arg3 ESP device
prepare_mount() {
	UPGRADE_ROOTFS_DIR=$(mktemp -d /tmp/rootfs.XXXXX)
	UPGRADE_BOOT_DIR="$UPGRADE_ROOTFS_DIR/boot"
	UPGRADE_ESP_DIR="$UPGRADE_BOOT_DIR/efi"

	mount -o $MOUNT_FLAG "LABEL=$1" "$UPGRADE_ROOTFS_DIR"
	mount -o $MOUNT_FLAG "LABEL=$2" "$UPGRADE_BOOT_DIR"
	mount -o $MOUNT_FLAG "$3" $UPGRADE_ESP_DIR
}

prepare_upgrade() {
	UPGRADE_ESP_DEV=$(get_esp_dev)
	get_upgrade_part_label

	prepare_mount $UPGRADE_ROOT_LABEL $UPGRADE_BOOT_LABEL $UPGRADE_ESP_DEV
}

ostree_upgrade() {
	[ -d $UPGRADE_ROOTFS_DIR/ostree/repo/refs/remotes/pulsar-linux ] && \
		branch=`ls $UPGRADE_ROOTFS_DIR/ostree/repo/refs/remotes/pulsar-linux/ | sed -n '1p'`

	if [ -z '${branch}' ]; then
		echo "No branch found, try default cube-gw"
		branch=cube-gw-ostree-runtime
	fi

	
	ostree remote list --repo=$UPGRADE_ROOTFS_DIR/ostree/repo |grep pulsar-linux

	[ $? = 0 ] || {
		echo "No remote repo found for pulsar-linux, please configure it via:"
		echo " ostree remote add --repo=/path/to/upgrade/repo pulsar-linux <URL>"
		cleanup
		exit 1
	}
	ostree pull --repo=$UPGRADE_ROOTFS_DIR/ostree/repo pulsar-linux:${branch}

	if [ $? -ne 0 ]; then
		echo "Ostree pull failed"
		cleanup
		exit 1
	fi

	ostree admin --sysroot=$UPGRADE_ROOTFS_DIR deploy --os=pulsar-linux ${branch}
	if [ $? -ne 0 ]; then
		echo "Ostree deploy failed"
		cleanup
		exit 1
	fi
}

update_env() {
	$GRUB_EDITENV_BIN $GRUB_ENV_FILE set \
		rollback_part=$ROOLBACK_VAL $BOOTMODE_VAR=$BOOTMODE_VAL
}

run_upgrade() {
	prepare_upgrade
	ostree_upgrade
	update_env
	cleanup

	exit 0

}

run_upgrade
