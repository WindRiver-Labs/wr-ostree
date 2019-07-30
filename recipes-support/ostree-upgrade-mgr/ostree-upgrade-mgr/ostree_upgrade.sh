#!/bin/sh

#  This script will use OSTree to upgrade the partitions which are not
#  in use and update either the grub or u-boot to start the upgraded
#  partition on the next reboot.
#
#* Copyright (c) 2018-2019 Wind River Systems, Inc.
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
CLEANUP_MOUNTS=""
CLEANUP_DIRS=""
DEBUG_SKIP_FSCK=${DEBUG_SKIP_FSCK=0}
USE_GRUB=1
BACKUP_PART_INDICATOR="_b"
GRUB_EDITENV_BIN=$(which grub-editenv 2>/dev/null)
GRUB_ENV_FILE="/boot/efi/EFI/BOOT/boot.env"
ROLLBACK_VAR="rollback_part"
BOOTMODE_VAR="boot_mode"
BOOT_VAR="boot_part"
ROOT_VAR="root_part"
MOUNT_FLAG="noatime,iversion"

cleanup() {
	for d in $CLEANUP_MOUNTS ; do
		umount $d
	done

	for d in $CLEANUP_DIRS ; do
		rmdir $d
	done
}
# get the label name for boot partition to be upgraded
get_upgrade_part_label() {
	local labelroot=`cat /proc/cmdline |tr " " "\n" |sort -u |grep ostree_root | awk -F '=' '{print $3}'`
	local labelboot=`cat /proc/cmdline |tr " " "\n" |sort -u |grep ostree_boot | awk -F '=' '{print $3}'`

	NO_AB=`ostree config --repo=/sysroot/ostree/repo get upgrade.no-ab 2> /dev/null`

	echo "$labelroot" | fgrep "${BACKUP_PART_INDICATOR}" >> /dev/null
	if [ $? -ne 0 -a "${NO_AB}" != "1" ]; then
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
	cat /proc/mounts |grep \ /boot/efi | cut -f 1 -d " "
}

create_dir() {
	local dir="$1"

	if [ ! -d "$dir" ]; then
	        mkdir -p "$dir" || return 1
	fi

	return 0
}

rwmount() {
    local flags="$1"
    local dev="$2"
    local mount="$3"

    if [ "$flags" != "" ] ; then
	    flags=",${flags}"
    fi

    # First mount read-only and transition to rw, or mount straight to
    # rw if the volume is available
    mount -r $dev $mount 2> /dev/null
    if [ $? = 0 ] ; then
	CLEANUP_MOUNTS="$mount $CLEANUP_MOUNTS"
	mount -o remount,rw${flags} $dev $mount 2> /dev/null || fatal "Error mounting $3"
    else
	mount -o rw${flags} $dev $mount || fatal "Error mounting $3"
	CLEANUP_MOUNTS="$mount $CLEANUP_MOUNTS"
    fi
}

#arg1 ROOT label
#arg2 BOOT label
#arg3 ESP device
prepare_mount() {
	UPGRADE_ROOTFS_DIR=$(mktemp -d /tmp/rootfs.XXXXX)
	CLEANUP_DIRS="$UPGRADE_ROOTFS_DIR $CLEANUP_DIRS"
	UPGRADE_BOOT_DIR="$UPGRADE_ROOTFS_DIR/boot"
	UPGRADE_ESP_DIR="$UPGRADE_BOOT_DIR/efi"

	# Detect correct disk labels from the running disk
	sysrootdev=$(cat /proc/mounts |grep \ /sysroot\  |awk '{print $1}'|head -1)
	[ "$sysrootdev" = "" ] && fatal "Could not find mounted /sysroot"

	RAWDEV=$(lsblk -npo pkname $sysrootdev)
	[ "$sysrootdev" = "" ] && fatal "Could not find raw device"

	dev=$(lsblk -rpno label,kname $RAWDEV|grep ^$1\ |awk '{print $2}')
	[ "$dev" = "" ] && fatal "Error finding LABEL=$1"
	if [ ${NO_AB} = "1" ] ; then
		mount --bind / $UPGRADE_ROOTFS_DIR || fatal "Error with bind mount of root dir"
		CLEANUP_MOUNTS="${UPGRADE_ROOTFS_DIR} $CLEANUP_MOUNTS"
		rwmount "$MOUNT_FLAG" $dev "$UPGRADE_ROOTFS_DIR/sysroot"
	else
		rwmount "$MOUNT_FLAG" $dev "$UPGRADE_ROOTFS_DIR"
	fi

	dev=$(lsblk -rpno label,kname $RAWDEV|grep ^$2\ |awk '{print $2}')
	[ "$dev" = "" ] && fatal "Error finding LABEL=$2"
	rwmount "$MOUNT_FLAG" $dev "$UPGRADE_BOOT_DIR" || fatal "Error mounting LABEL=$2"

	if [ "$3" != "" ] ; then
		rwmount "" "$3" $UPGRADE_ESP_DIR
	fi
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
		fatal " ostree config set upgrade.branch <branch>"
	fi

	if [ -z "${remote}" ] ; then
		echo "No remote repository specified for upgrade, please configure it via:"
		fatal " ostree config set upgrade.remote <remote_repo_name>"
	fi

	url=`ostree remote --repo=/sysroot/ostree/repo show-url ${remote} 2> /dev/null`

	if [ -z "${url}" ] ; then
		echo "No remote repository url configured, please configure it via:"
		fatal " ostree remote add ${remote} <url>"
	fi

	# Copy the existing configuration to the upgrade partition
	if [ "$(stat -c "%d:%i" /sysroot/ostree/repo/config)" != "$(stat -c "%d:%i" $UPGRADE_ROOTFS_DIR/ostree/repo/config)" ] ; then
		cp /sysroot/ostree/repo/config $UPGRADE_ROOTFS_DIR/ostree/repo/config
	fi
}

prepare_upgrade() {
	UPGRADE_ESP_DEV=$(get_esp_dev)
	if [ "${UPGRADE_ESP_DEV}" = "" ] ; then
		USE_GRUB=0
	else
		[ -f "$GRUB_EDITENV_BIN" ] || {
			echo "grub-editenv is not found on target."
			echo "This script should run on intel-x86 platform with grub-efi installed!"
			exit 1
		}

		[ -f "$GRUB_ENV_FILE" ] || {
			$GRUB_EDITENV_BIN $GRUB_ENV_FILE create
		}
	fi
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
	    fatal " ostree config set upgrade.os <DEPLOY_OS_NAME>"
	fi

	# Perform repairs, if needed on the upgrade ostree repository
	repair=0
	[ $DEBUG_SKIP_FSCK = 1 ] || ostree fsck -a --delete --repo=$UPGRADE_ROOTFS_DIR/ostree/repo
	if [ $? != 0 ] ; then
		repair=1
	fi

	lcache="--localcache-repo=/sysroot/ostree/repo"

	[ $DEBUG_SKIP_FSCK = 1 ] || ostree fsck --repo=/sysroot/ostree/repo
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
		fatal "Ostree pull failed"
	fi
	if [ $repair = 1 ] ; then
		# Repair any other remote references if the original was damaged and re-run fsck
		for b in `ostree --repo=$UPGRADE_ROOTFS_DIR/ostree/repo refs|grep :`; do
			if [ "${remote}:${branch}" != "$b" ] ; then
				ostree pull $lcache --repo=$UPGRADE_ROOTFS_DIR/ostree/repo $b
				if [ $? -ne 0 ]; then
					fatal "Ostree pull failed"
				fi
			fi
		done
		ostree fsck -a --delete --repo=$UPGRADE_ROOTFS_DIR/ostree/repo
		if [ $? != 0 ] ; then
			fatal "Error: Upgrade partition ostree repo could not be repaired"
		fi
	fi

	OSTREE_ETC_MERGE_DIR=/etc ostree admin --sysroot=$UPGRADE_ROOTFS_DIR deploy --os=${os} ${branch}
	if [ $? -ne 0 ]; then
		fatal "Ostree deploy failed"
	fi
	check=`ostree config get upgrade.noflux 2>/dev/null`
	if [ "$check" = 1 ] ; then
		if [ -n "${updir}" -a -n "${upcommit}" ] ; then
			sed -i -e  's/^LABEL=fluxdata.*//' $UPGRADE_ROOTFS_DIR/boot/0/etc/fstab
		fi
	fi
}

update_env() {
	if [ $USE_GRUB = 1 ] ; then
		$GRUB_EDITENV_BIN $UPGRADE_ROOTFS_DIR/$GRUB_ENV_FILE set \
			rollback_part=$ROLLBACK_VAL $BOOTMODE_VAR=$BOOTMODE_VAL \
			default=0 boot_tried_count=0
	else
		# Assume this is a u-boot volume to update
		tmpdir=$(mktemp -d /tmp/boot.XXXXX)
		CLEANUP_DIRS="$tmpdir $CLEANUP_DIRS"
		dev=$(lsblk -rpno label,kname $RAWDEV|grep ^boot\ |awk '{print $2}')
		[ "$dev" = "" ] && fatal "Error finding LABEL=boot"
		rwmount "" $dev $tmpdir
		abflag="B"
		if [ "$BOOTMODE_VAL" = "" ] ; then
			abflag="A"
		fi
		printf "123"${abflag} > $tmpdir/boot_ab_flag
		# The first 0 is the boot count, the second zero is the boot entry default
		printf '00WR' > $tmpdir/boot_cnt
	fi
}

run_upgrade() {
	prepare_upgrade
	ostree_upgrade
	update_env
	cleanup

	exit 0

}

run_upgrade
