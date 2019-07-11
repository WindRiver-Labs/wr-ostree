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
GRUB_EDITENV_BIN=$(which grub-editenv)
GRUB_ENV_FILE="/boot/efi/EFI/BOOT/boot.env"
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
	$GRUB_EDITENV_BIN $GRUB_ENV_FILE create
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
		ROLLBACK_VAL=""
		BOOTMODE_VAL="${BACKUP_PART_INDICATOR}"
	else
		UPGRADE_ROOT_LABEL=`echo "${labelroot}" |sed "s/${BACKUP_PART_INDICATOR}//g"`
		UPGRADE_BOOT_LABEL=`echo "${labelboot}" |sed "s/${BACKUP_PART_INDICATOR}//g"`
		ROLLBACK_VAL="${BACKUP_PART_INDICATOR}"
		BOOTMODE_VAL=""
	fi

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

	mount -o $MOUNT_FLAG "LABEL=$1" "$UPGRADE_ROOTFS_DIR" || fatal "Error mounting LABEL=$1"
	mount -o $MOUNT_FLAG "LABEL=$2" "$UPGRADE_BOOT_DIR" || fatal "Error mounting LABEL=$2"
	mount -o $MOUNT_FLAG "$3" $UPGRADE_ESP_DIR || fatal "Error mounting $3"
}

check_repo_url() {
	local branch
	local remote
	local url

	# Check and copy any repo information for the upgrade
	branch=`ostree config --repo=/sysroot/ostree/repo get upgrade.branch 2> /dev/null`
	remote=`ostree config --repo=/sysroot/ostree/repo get upgrade.remote 2> /dev/null`

	if [ -z "${branch}" ] ; then
		echo "No branch specified for upgrade, please configure it via:"
		echo " ostree config set upgrade.branch <branch>"
		cleanup
		exit 1
	fi

	if [ -z "${remote}" ] ; then
		echo "No remote repository specified for upgrade, please configure it via:"
		echo " ostree config set upgrade.remote <remote_repo_name>"
		cleanup
		exit 1
	fi

	url=`ostree remote --repo=/sysroot/ostree/repo show-url ${remote} 2> /dev/null`

	if [ -z "${url}" ] ; then
		echo "No remote repository url configured, please configure it via:"
		echo " ostree remote add ${remote} <url>"
		cleanup
		exit 1
	fi

	# Copy the existing configuration to the upgrade partition
	cp /sysroot/ostree/repo/config $UPGRADE_ROOTFS_DIR/ostree/repo/config

}

prepare_upgrade() {
	UPGRADE_ESP_DEV=$(get_esp_dev)
	get_upgrade_part_label

	prepare_mount $UPGRADE_ROOT_LABEL $UPGRADE_BOOT_LABEL $UPGRADE_ESP_DEV
	check_repo_url
}

fatal() {
	echo $1
	cleanup
	exit 1
}

ostree_upgrade() {
	local branch
	local remote

	branch=`ostree config --repo=$UPGRADE_ROOTFS_DIR/ostree/repo get upgrade.branch 2> /dev/null`
	remote=`ostree config --repo=$UPGRADE_ROOTFS_DIR/ostree/repo get upgrade.remote 2> /dev/null`
	os=`ostree config --repo=$UPGRADE_ROOTFS_DIR/ostree/repo get upgrade.os 2> /dev/null`

	if [ "${os}" = "" ] ; then
	    os=`ls /ostree/deploy |head -1`
	fi

	if [ "${os}" = "" ] ; then
	    echo "Error deploy OS is not defined, please configure it via:"
	    echo " ostree config set upgrade.os <DEPLOY_OS_NAME>"
	    cleanup
	    exit 1
	fi

	# Perform repairs, if needed on the upgrade ostree repository
	repair=0
	ostree fsck -a --delete --repo=$UPGRADE_ROOTFS_DIR/ostree/repo
	if [ $? != 0 ] ; then
		repair=1
	fi

	lcache="--localcache-repo=/sysroot/ostree/repo"

	ostree fsck --repo=/sysroot/ostree/repo
	if [ $? = 0 ] ; then
		ostree pull $lcache --repo=$UPGRADE_ROOTFS_DIR/ostree/repo ${remote}:${branch}
		# Always try a cached pull first so as not to incur extra bandwidth cost
		if [ $? -ne 0 ]; then
			lcache=""
			echo "Trying an uncached pull"
			ostree pull --repo=$UPGRADE_ROOTFS_DIR/ostree/repo ${remote}:${branch}
		fi
	else
		lcache=""
		# if the local repository is corrupted in any maner, skip the localcache operation
		ostree pull --repo=$UPGRADE_ROOTFS_DIR/ostree/repo ${remote}:${branch}
	fi
	if [ $? -ne 0 ]; then
		echo "Ostree pull failed"
		cleanup
		exit 1
	fi
	if [ $repair = 1 ] ; then
		# Repair any other remote references if the original was damaged and re-run fsck
		for b in `ostree --repo=$UPGRADE_ROOTFS_DIR/ostree/repo refs|grep :`; do
			if [ "${remote}:${branch}" != "$b" ] ; then
				ostree pull $lcache --repo=$UPGRADE_ROOTFS_DIR/ostree/repo $b
				if [ $? -ne 0 ]; then
					echo "Ostree pull failed"
					cleanup
					exit 1
				fi
			fi
		done
		ostree fsck -a --delete --repo=$UPGRADE_ROOTFS_DIR/ostree/repo
		if [ $? != 0 ] ; then
			echo "Error: Upgrade partition ostree repo could not be repaired"
			cleanup
			exit 1
		fi
	fi

	ostree admin --sysroot=$UPGRADE_ROOTFS_DIR deploy --os=${os} ${branch}
	if [ $? -ne 0 ]; then
		echo "Ostree deploy failed"
		cleanup
		exit 1
	fi
	check=`ostree config get upgrade.noflux 2>/dev/null`
	if [ "$check" = 1 ] ; then
		if [ -n "${updir}" -a -n "${upcommit}" ] ; then
			sed -i -e  's/^LABEL=fluxdata.*//' $UPGRADE_ROOTFS_DIR/boot/0/etc/fstab
		fi
	fi
}

update_env() {
	$GRUB_EDITENV_BIN $GRUB_ENV_FILE set \
		rollback_part=$ROLLBACK_VAL $BOOTMODE_VAR=$BOOTMODE_VAL \
		default=0 boot_tried_count=0
}

run_upgrade() {
	prepare_upgrade
	ostree_upgrade
	update_env
	cleanup

	exit 0

}

run_upgrade
