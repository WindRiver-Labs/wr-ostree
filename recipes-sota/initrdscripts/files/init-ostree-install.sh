#!/bin/sh
#
# Copyright (c) 2019 Wind River Systems, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# This is a reference implementation for initramfs install
# The kernel arguments to use an install are as follows:
#

helptxt() {
	cat <<EOF
Usage: This script is intended to run from the initramfs and use the ostree
binaries in the initramfs to install a file system onto a disk device.

The arguments to this script are passed through the kernel boot arguments.

REQUIRED:
 rdinit=/install		- Activates the installer
 instdev=/dev/YOUR_DEVCICE	- One or more devices separated by a comma
	  where the first valid device found is used as the install device
 instname=OSTREE_REMOTE_NAME	- Remote name like wrlinux
 instbr=OSTREE_BRANCH_NAME	- Branch for OSTree to use
 insturl=OSTREE_URL		- URL to OSTree repository

OPTIONAL:
 bl=booloader                  - grub, ufsd(u-boot fdisk sd)
 instab=0			- Do not use the AB layout, only use A
 instnet=0			- Do not invoke udhcpc or dhclient
   If the above is 0, use the kernel arg:
    ip=<client-ip>::<gw-ip>:<netmask>:<hostname>:<device>:off:<dns0-ip>:<dns1-ip>
   Example:
    ip=10.0.2.15::10.0.2.1:255.255.255.0:tgt:eth0:off:10.0.2.3:8.8.8.8
 LUKS=0				- Do not create encrypted volumes
 LUKS=1				- Encrypt var volume (requires TPM)
 LUKS=2				- Encrypt var and and root volumes (requires TPM)
 instflux=0			- Do not create/use the fluxdata partition for /var
	  VSZ will be used for the size of the / partition if instab=0
 instl=DIR			- Local override ostree repo to install from
 instsh=1			- Start a debug shell
 instsh=2			- Use verbose logging
 instsh=3			- Use verbose logging and start shell
 instsh=4			- Display the help text and start a shell
 instpost=halt			- Halt at the end of install vs reboot
 instpost=exit			- exit at the end of install vs reboot
 instpost=shell		- shell at the end of install vs reboot
 instos=OSTREE_OS_NAME		- Use alternate OS name vs wrlinux
 instsbd=1			- Turn on the skip-boot-diff configuration
 instsf=1			- Skip fat partition format
 instfmt=1			- Set to 0 to skip partition formatting
 instpt=1			- Set to 0 to skip disk partitioning
 instgpg=0			- Turn off OSTree GnuPG signing checks
 instdate=datespec	        - Argument to "date -u -s" like @1577836800
 dhcpargs=DHCP_ARGS		- Arguments to pass to udhcpc
 ecurl=URL_TO_SCRIPT		- Download+execute script before disk prep
 ecurlarg=ARGS_TO_ECURL_SCRIPT	- Arguments to pass to ecurl script
 lcurl=URL_TO_SCRIPT		- Download+execute script after install
 lcurlarg=ARGS_TO_ECURL_SCRIPT	- Arugments to pass to lcurl script
 Disk sizing
 BLM=#				- Blocks of boot magic area to skip
				  ARM BSPs with SD cards usually need this
 FSZ=#				- MB size of fat partition
 BSZ=#				- MB size of boot partition
 RSZ=#				- MB size of root partition
 VSZ=#				- MB size of var partition (0 for auto expand)

EOF
}

log_info() { echo "$0[$$]: $*" >&2; }
log_error() { echo "$0[$$]: ERROR $*" >&2; }

PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/lib/ostree:/usr/lib64/ostree

lreboot() {
	echo b > /proc/sysrq-trigger
	while [ 1 ] ; do
		sleep 60
	done
}

do_dhcp() {
	if [ -f /sbin/udhcpc ] ; then
		/sbin/udhcpc ${DCHPARGS}
	else
		dhclient ${DCHPARGS}
	fi
}


do_mount_fs() {
	echo "mounting FS: $*"
	[[ -e /proc/filesystems ]] && { grep -q "$1" /proc/filesystems || { log_error "Unknown filesystem"; return 1; } }
	[[ -d "$2" ]] || mkdir -p "$2"
	[[ -e /proc/mounts ]] && { grep -q -e "^$1 $2 $1" /proc/mounts && { log_info "$2 ($1) already mounted"; return 0; } }
	mount -t "$1" "$1" "$2" || fatal "Error mounting $2"
}

early_setup() {
	do_mount_fs proc /proc
	read_args
	do_mount_fs sysfs /sys
	mount -t devtmpfs none /dev
	do_mount_fs tmpfs /tmp
	do_mount_fs tmpfs /run

	$_UDEV_DAEMON --daemon
	udevadm trigger --action=add

	if [ -x /sbin/mdadm ]; then
		/sbin/mdadm -v --assemble --scan --auto=md
	fi

	if [ -e "/sys/fs/selinux" ];then
		do_mount_fs selinuxfs /sys/fs/selinux
		echo 1 > /sys/fs/selinux/disable
	fi
}

udev_daemon() {
	OPTIONS="/sbin/udev/udevd /sbin/udevd /lib/udev/udevd /lib/systemd/systemd-udevd"

	for o in $OPTIONS; do
		if [ -x "$o" ]; then
			echo $o
			return 0
		fi
	done

	return 1
}

fatal() {
    echo $1 >$CONSOLE
    echo >$CONSOLE
    if [ "$INSTPOST" = "shell" ] ; then shell_start ; fi
    if [ "$INSTPOST" = "exit" ] ; then exit 1 ; fi
    sleep 10
    lreboot
}

# Global Variable setup
# default values must match wr-ostree.inc
BLM=2506
FSZ=32
BSZ=200
RSZ=1400
VSZ=0
# end values from wr-ostree.inc
LUKS=0
_UDEV_DAEMON=`udev_daemon`
INSTDATE=${INSTDATE=""}
INSTSH=${INSTSH=""}
INSTNET=${INSTNET=""}
INSTDEV=${INSTDEV=""}
INSTAB=${INSTAB=""}
INSTPOST=${INSTPOST=""}
INSTOS=${INSTOS=""}
INSTNAME=${INSTNAME=""}
BL=${BL=""}
INSTL=${INSTL=""}
INSTPT=${INSTPT=""}
INSTFMT=${INSTFMT=""}
INSTBR=${INSTBR=""}
INSTSBD=${INSTSBD=""}
INSTURL=${INSTURL=""}
INSTGPG=${INSTGPG=""}
INSTSF=${INSTSF=""}
INSTFLUX=${INSTFLUX=""}
DHCPARGS=${DHCPARGS=""}
ECURL=${ECURL=""}
ECURLARG=${ECURLARG=""}
LCURL=${LCURL=""}
LCURLARG=${LCURLARG=""}
IP=""
MAX_TIMEOUT_FOR_WAITING_LOWSPEED_DEVICE=60
OSTREE_KERNEL_ARGS=${OSTREE_KERNEL_ARGS=%OSTREE_KERNEL_ARGS%}

if [ "$OSTREE_KERNEL_ARGS" = "%OSTREE_KERNEL_ARGS%" ] ; then
	OSTREE_KERNEL_ARGS="ro rootwait"
fi

read_args() {
	[ -z "$CMDLINE" ] && CMDLINE=`cat /proc/cmdline`
	for arg in $CMDLINE; do
		optarg=`expr "x$arg" : 'x[^=]*=\(.*\)'`
		case $arg in
			bl=*)
				BL=$optarg ;;
			instnet=*)
				INSTNET=$optarg ;;
			instsh=*)
				if [ "$INSTSH" = "" ] ; then
					INSTSH=$optarg
					if [ "$INSTSH" = 2 -o "$INSTSH" = 3 ] ; then
						set -xv
					fi
				fi
				;;
			ip=*)
				IP=$optarg ;;
			instl=*)
				INSTL=$optarg ;;
			instdev=*)
				INSTDEV=$optarg ;;
			instab=*)
				INSTAB=$optarg ;;
			instpost=*)
				if [ "$INSTPOST" = "" ] ; then INSTPOST=$optarg; fi ;;
			instname=*)
				INSTNAME=$optarg ;;
			instsf=*)
				INSTSF=$optarg ;;
			instbr=*)
				INSTBR=$optarg ;;
			instsbd=*)
				INSTSBD=$optarg ;;
			instpt=*)
				INSTPT=$optarg ;;
			instfmt=*)
				INSTFMT=$optarg ;;
			insturl=*)
				INSTURL=$optarg ;;
			instgpg=*)
				INSTGPG=$optarg ;;
			instdate=*)
				INSTDATE=$optarg ;;
			instflux=*)
				INSTFLUX=$optarg ;;
			dhcpargs=*)
				DHCPARGS=$optarg ;;
			ecurl=*)
				if [ "$ECURL" = "" ] ; then ECURL=$optarg; fi ;;
			ecurlarg=*)
				ECURLARG=$optarg ;;
			lcurl=*)
				if [ "$LCURL" = "" ] ; then LCURL=$optarg; fi ;;
			lcurlarg=*)
				LCURLARG=$optarg ;;
			LUKS=*)
				LUKS=$optarg ;;
			BLM=*)
				BLM=$optarg ;;
			FSZ=*)
				FSZ=$optarg ;;
			BSZ=*)
				BSZ=$optarg ;;
			RSZ=*)
				RSZ=$optarg ;;
			VSZ=*)
				VSZ=$optarg ;;
		esac
	done
	# defaults if not set
	if [ "$BL" = "" ] ; then BL=grub ; fi
	if [ "$INSTSF" = "" ] ; then INSTSF=0 ; fi
	if [ "$INSTSH" = "" ] ; then INSTSH=0 ; fi
	if [ "$INSTAB" = "" ] ; then INSTAB=1 ; fi
	if [ "$INSTOS" = "" ] ; then INSTOS=wrlinux ; fi
	if [ "$INSTNET" = "" ] ; then INSTNET=dhcp ; fi
	if [ "$INSTGPG" = "" ] ; then INSTGPG=1 ; fi
	if [ "$INSTFLUX" = "" ] ; then INSTFLUX=1 ; fi
	if [ "$INSTSBD" = "" ] ; then INSTSBD=2 ; fi
}

shell_start() {
	a=`cat /proc/cmdline`
	for e in $a; do
		case $e in
			console=*)
				c=${e%,*}
				c=${c#console=*}
				break
				;;
		esac
	done

	if [ "$c" = "" ] ; then
		c=tty0
	fi
	if [ "$1" = "exec" ] ; then
		exec setsid sh -c "exec /bin/bash </dev/$c >/dev/$c 2>&1"
	else
		echo "trap lreboot EXIT; function lreboot { echo b > /proc/sysrq-trigger; while [ 1 ] ; do sleep 60; done }" > /debugrc
		setsid sh -c "exec /bin/bash --rcfile /debugrc </dev/$c >/dev/$c 2>&1"
	fi
}

grub_pt_update() {
	first=$(($end+1))
	p=$((p+1))
	if [ $first -gt $last ] ; then
		fatal "ERROR: Disk is not big enough for requested layout"
	fi
}

grub_partition() {
	local a
	local p
	local first
	local last
	local end
	lsz=`lsblk -n ${dev} -o LOG-SEC -d`
	lsz=${lsz// /}
	# EFI Partition
	if [ ! -e ${fs_dev}1 ] ; then
		echo "WARNING WARNING - ${fs_dev}1 does not exist, creating"
		INSTSF=0
	fi
	if [ $INSTSF = 1 ] ; then
		for e in `sgdisk -p ${dev} 2> /dev/null |grep -A 1024 ^Number |grep -v ^Number |awk '{print $1}' |grep -v ^1\$`; do
			a="$a -d $e"
		done
		a="$a -c 1:otaefi -t 1:EF00"
		sgdisk -e $a ${dev}
		a=""
		first=`sgdisk -F ${dev}|grep -v Creating`
	else
		sgdisk -Z ${dev}
		first=`sgdisk -F ${dev}|grep -v Creating`
		end=$(($first+($FSZ*1024*1024/$lsz)-1))
		a="$a -n 1:$first:$end -c 1:otaefi -t 1:EF00"
		first=$(($end+1))
	fi
	last=$(sgdisk -E ${dev} 2>/dev/null |grep -v Creating)
	p=2
	# Boot Partition A
	end=$(($first+($BSZ*1024*1024/$lsz)-1))
	a="$a -n $p:$first:$end -c $p:otaboot"
	grub_pt_update
	# Root Partition A
	if [ "$INSTAB" = 0 -a "${INSTFLUX}" = 0 ] ; then
		if [ "$VSZ" = 0 ] ; then
			end=$last
		else
			end=$(($first+($VSZ*1024*1024/$lsz)-1))
		fi
		a="$a -n $p:$first:$end -c $p:otaroot"
	else
		end=$(($first+($RSZ*1024*1024/$lsz)-1))
		a="$a -n $p:$first:$end -c $p:otaroot"
		grub_pt_update
	fi
	if [ "$INSTAB" = 1 ] ; then
		# Boot Partition B
		end=$(($first+($BSZ*1024*1024/$lsz)-1))
		a="$a -n $p:$first:$end -c $p:otaboot_b"
		grub_pt_update
		# Root Partition B
		end=$(($first+($RSZ*1024*1024/$lsz)-1))
		a="$a -n $p:$first:$end -c $p:otaroot_b"
		grub_pt_update
	fi
	# Flux Partition
	if [ "${INSTFLUX}" = 1 ] ; then
		if [ "$VSZ" = 0 ] ; then
			end=$last
		else
			end=$(($first+($VSZ*1024*1024/$lsz)-1))
		fi
		a="$a -n $p:$first:$end -c $p:fluxdata"
	fi
	sgdisk $a -p ${dev}
}

ufdisk_partition() {
	if [ ! -e ${fs_dev}1 ] ; then
		echo "WARNING WARNING - ${fs_dev}1 does not exist, creating"
		INSTSF=0
	fi
	if [ $INSTSF = 1 ] ; then
		pts=`mktemp`
		fdisk -l -o device ${dev} |grep ^${fs_dev} > $pts || fatal "fdisk probe failed"
		# Start by deleting all the other partitions
		fpt=$(cat $pts |sed -e "s#${fs_dev}##" | head -n 1)
		for p in `cat $pts |sed -e "s#${fs_dev}##" |sort -rn`; do
			if [ $p != 1 ] ; then
				sfdisk --no-reread --no-tell-kernel -w never --delete ${dev} $p
			fi
		done
	else
		sgdisk -Z ${dev} > /dev/null 2> /dev/null
		echo 'label: mbr' | sfdisk --no-reread --no-tell-kernel -W never -w never ${dev}
		# Partition for storage of u-boot variables and backup kernel
		echo "${BLM},${FSZ}M,0xc" | sfdisk --no-reread --no-tell-kernel -W never -w never ${dev}
		sfdisk --no-reread --no-tell-kernel -W never -w never -A ${dev} 1
	fi
	# Create extended partition for remainder of disk
	echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'), +,0x5" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
	if [ "${INSTFLUX}" = 1 ] ; then
		# Create Boot and Root A partition
		echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${BSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
		echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${RSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
		if [ "$INSTAB" = "1" ] ; then
			# Create Boot and Root B partition
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${BSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${RSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
		fi
		# flux data partition
		if [ "$VSZ" = 0 ] ; then
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'), +" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
		else
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${VSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
		fi
	else
		if [ "$INSTAB" = "1" ] ; then
			# Create Boot and Root A partition
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${BSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${RSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
			# Create Boot and Root B partition
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${BSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${RSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
		else
			# Create Boot and Root A partition for whole disk
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'),${BSZ}M" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
			echo "$(sfdisk -F ${dev} |tail -1 |awk '{print $1}'), +" | sfdisk --no-reread --no-tell-kernel -a -W never -w never ${dev}
		fi
	fi
}

##################

if [ "$1" = "-h" -o "$1" = "-?" ] ; then
	helptxt
	exit 0
fi

early_setup

[ -z "$CONSOLE" ] && CONSOLE="/dev/console"
[ -z "$INIT" ] && INIT="/sbin/init"

if [ "$INSTSH" = 1 -o "$INSTSH" = 3 -o "$INSTSH" = 4 ] ; then
	if [ "$INSTSH" = 4 ] ; then
		helptxt
	fi
	echo "Starting boot shell.  System will reboot on exit"
	echo "You can execute the install with:"
	echo "     INSTPOST=exit INSTSH=0 bash -v -x /install"
	shell_start exec
	lreboot
fi

udevadm settle --timeout=3

if [ "$INSTNAME" = "" ] ; then
	fatal "Error no remote archive name, need kernel argument: instname=..."
fi
if [ "$INSTBR" = "" ] ; then
	fatal "Error no branch name for OSTree, need kernel argument: instbr=..."
fi
if [ "$INSTURL" = "" ] ; then
	fatal "Error no URL for OSTree, need kernel argument: insturl=..."
fi

if [ "$INSTDATE" != "" ] ; then
	if [ "$INSTDATE" = "BUILD_DATE" ] ; then
		echo "WARNING date falling back to 1/1/2020"
		date -u -s @1577836800
	else
		date -u -s $INSTDATE
	fi
fi

# Customize here for network
if [ "$IP" != "" ] ; then
	if [ "$IP" = "dhcp" ] ; then
		dns=$(dmesg |grep nameserver.= |sed 's/nameserver.=//g; s/,//g')
	else
		dns=$(echo "$IP"|awk -F: '{print $8" "$9}')
	fi
	for e in $dns; do
		echo nameserver $e >> /etc/resolv.conf
	done
fi

if [ "$INSTNET" = dhcp ] ; then
	do_dhcp
fi

# Early curl exec

if [ "${ECURL}" != "" -a "${ECURL}" != "none" ] ; then
	curl ${ECURL} --output /ecurl
	# Prevent recursion if script debugging
	export ECURL="none"
	chmod 755 /ecurl
	/ecurl ${ECURLARG}
fi

# Customize here for disk detection

if [ "$INSTDEV" = "" ] ; then
	fatal "Error no kernel argument instdev=..."
fi

# Device setup
retry=0
fail=1
while [ $retry -lt $MAX_TIMEOUT_FOR_WAITING_LOWSPEED_DEVICE ] ; do
	if [ "$INSTDEV" = "${INSTDEV//,/ }" ] ; then
		if [ -e $INSTDEV ] ; then
			fail=0
			break
		fi
	else
		for i in ${INSTDEV//,/ }; do
			if [ -e $i ] ; then
				INSTDEV=$i
				echo "Installing to: $i"
				fail=0
				break
			fi
		done
		[ fail = 0 ] && break
	fi
	retry=$(($retry+1))
	sleep 0.1
done
if [ $fail = 1 ] ; then
	fatal "Error device instdev=$INSTDEV not found"
fi

fs_dev=${INSTDEV}

if [ "${fs_dev#/dev/mmcblk}" != ${fs_dev} ] ; then
       fs_dev="${INSTDEV}p"
elif [ "${fs_dev#/dev/nbd}" != ${fs_dev} ] ; then
       fs_dev="${INSTDEV}p"
elif [ "${fs_dev#/dev/nvme}" != ${fs_dev} ] ; then
       fs_dev="${INSTDEV}p"
elif [ "${fs_dev#/dev/loop}" != ${fs_dev} ] ; then
       fs_dev="${INSTDEV}p"
fi

# Customize here for disk partitioning

dev=${INSTDEV}

if [ "$INSTPT" != "0" ] ; then
	if [ "$BL" = "grub" ] ; then
		grub_partition
	elif [ "$BL" = "ufsd" ] ; then
		ufdisk_partition
	else
		fatal "Error: bl=$BL is not supported"
	fi
fi

cnt=50
while [ $cnt ] ; do
	blockdev --rereadpt ${dev} 2> /dev/null > /dev/null && break
	sleep 0.1
	cnt=$(($cnt - 1))
done
sync

# Customize here for disk formatting

if [ "$INSTPT" != "0" ] ; then
	INSTFMT=1
fi

if [ "$BL" = "grub" -a "$INSTFMT" != "0" ] ; then
	FLUXPART=6
	if [ $INSTSF = 1 ] ; then
		dosfslabel ${fs_dev}1 otaefi
	else
		mkfs.vfat -n otaefi ${fs_dev}1
	fi
	mkfs.ext4 -F -L otaboot ${fs_dev}2
	dashe="-e"
	if [ $LUKS -gt 1 ] ; then
		echo Y | luks-setup.sh -f $dashe -d ${fs_dev}3 -n luksotaroot || \
			fatal "Cannot create LUKS volume luksotaroot"
		dashe=""
		mkfs.ext4 -F -L otaroot /dev/mapper/luksotaroot
	else
		mkfs.ext4 -F -L otaroot ${fs_dev}3
	fi
	if [ "$INSTAB" = "1" ] ; then
		mkfs.ext4 -F -L otaboot_b ${fs_dev}4
		if [ $LUKS -gt 1 ] ; then
			echo Y | luks-setup.sh -f -d ${fs_dev}5 -n luksotaroot_b || \
				fatal "Cannot create LUKS volume luksotaroot_b"
			mkfs.ext4 -F -L otaroot_b /dev/mapper/luksotaroot_b
		else
			mkfs.ext4 -F -L otaroot_b ${fs_dev}5
		fi
	else
		FLUXPART=4
	fi
	if [ "${INSTFLUX}" = 1 ] ; then
		if [ $LUKS -gt 0 ] ; then
			echo Y | luks-setup.sh -f $dashe -d ${fs_dev}${FLUXPART} -n luksfluxdata || \
				fatal "Cannot create LUKS volume luksfluxdata"
			dashe=""
			mkfs.ext4 -F -L fluxdata /dev/mapper/luksfluxdata
		else
			mkfs.ext4 -F -L fluxdata ${fs_dev}${FLUXPART}
		fi
	fi
elif [ "$INSTFMT" != 0 ] ; then
	if [ $INSTSF = 1 ] ; then
		dosfslabel ${fs_dev}1 boot
	else
		mkfs.vfat -n boot ${fs_dev}1
	fi
	FLUXPART=9
	mkfs.ext4 -F -L otaboot ${fs_dev}5
	mkfs.ext4 -F -L otaroot ${fs_dev}6
	if [ "$INSTAB" = "1" ] ; then
		mkfs.ext4 -F -L otaboot_b ${fs_dev}7
		mkfs.ext4 -F -L otaroot_b ${fs_dev}8
	else
		FLUXPART=7
	fi
	if [ "${INSTFLUX}" = 1 ] ; then
		mkfs.ext4 -F -L fluxdata ${fs_dev}${FLUXPART}
	fi
fi

# OSTree deploy

PHYS_SYSROOT="/sysroot"
OSTREE_BOOT_DEVICE="LABEL=otaboot"
OSTREE_ROOT_DEVICE="LABEL=otaroot"
mount_flags="rw,noatime,iversion"

for arg in ${OSTREE_KERNEL_ARGS}; do
        kargs_list="${kargs_list} --karg-append=$arg"
done

mkdir -p ${PHYS_SYSROOT}
mount -o $mount_flags "${OSTREE_ROOT_DEVICE}" "${PHYS_SYSROOT}" || fatal "Error mouting ${OSTREE_ROOT_DEVICE}"

ostree admin --sysroot=${PHYS_SYSROOT} init-fs ${PHYS_SYSROOT}
ostree admin --sysroot=${PHYS_SYSROOT} os-init ${INSTOS}
ostree config --repo=${PHYS_SYSROOT}/ostree/repo set core.add-remotes-config-dir false
ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.branch ${INSTBR}
ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.remote ${INSTNAME}
ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.os ${INSTOS}
if [ "$INSTFLUX" != "1" ] ; then
	ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.noflux 1
fi
if [ "$INSTAB" != "1" ] ; then
	ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.no-ab 1
fi

ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.skip-boot-diff $INSTSBD

if [ ! -d "${PHYS_SYSROOT}/boot" ] ; then
   mkdir -p ${PHYS_SYSROOT}/boot
fi

mount "${OSTREE_BOOT_DEVICE}" "${PHYS_SYSROOT}/boot"  || fatal "Error mouting ${OSTREE_BOOT_DEVICE}"

mkdir /instboot
blkid --label instboot
if [ $? = 0 ] ; then
	mount -r LABEL=instboot /instboot
fi

mkdir -p ${PHYS_SYSROOT}/boot/efi
mount ${fs_dev}1 ${PHYS_SYSROOT}/boot/efi || fatal "Error mouting ${fs_dev}1"

# Prep for Install
mkdir -p ${PHYS_SYSROOT}/boot/loader.0
ln -s loader.0 ${PHYS_SYSROOT}/boot/loader

if [ "$BL" = "grub" ] ; then
	mkdir -p ${PHYS_SYSROOT}/boot/grub2
	touch ${PHYS_SYSROOT}/boot/grub2/grub.cfg
else
	touch  ${PHYS_SYSROOT}/boot/loader/uEnv.txt
fi

do_gpg=""
if [ "$INSTGPG" != "1" ] ; then
	do_gpg=--no-gpg-verify
fi
ostree remote --repo=${PHYS_SYSROOT}/ostree/repo add ${do_gpg} ${INSTNAME} ${INSTURL}

touch /etc/ssl/certs/ca-certificates.crt
mkdir -p /var/volatile/tmp /var/volatile/run

lpull=""
if [ "$INSTL" != "" ] ; then
	if [ -e /instboot${INSTL#/sysroot/boot/efi} ] ; then
		lpull="--url file:///instboot${INSTL#/sysroot/boot/efi}"
	elif [ -e $INSTL ] ; then
		lpull="--url file://$INSTL"
	else
		echo "WARNING WARNING - Local install missing, falling back to network"
		lpull=""
	fi
fi

cmd="ostree pull $lpull --repo=${PHYS_SYSROOT}/ostree/repo ${INSTNAME} ${INSTBR}"
echo running: $cmd
$cmd || fatal "Error: ostree pull failed"
export OSTREE_BOOT_PARTITION="/boot"
ostree admin deploy ${kargs_list} --sysroot=${PHYS_SYSROOT} --os=${INSTOS} ${INSTNAME}:${INSTBR} || fatal "Error: ostree deploy failed"

if [ "$INSTAB" != 1 ] ; then
	# Deploy a second time so a roll back is available from the start
	ostree admin deploy --sysroot=${PHYS_SYSROOT} --os=${INSTOS} ${INSTNAME}:${INSTBR} || fatal "Error: ostree deploy failed"
fi

# Initialize "B" partion if used


if [ "$INSTAB" = "1" ] ; then
	mkdir -p ${PHYS_SYSROOT}_b
	mount -o $mount_flags "${OSTREE_ROOT_DEVICE}_b" "${PHYS_SYSROOT}_b"  || fatal "Error mouting ${OSTREE_ROOT_DEVICE}_b"

	ostree admin --sysroot=${PHYS_SYSROOT}_b init-fs ${PHYS_SYSROOT}_b
	ostree admin --sysroot=${PHYS_SYSROOT}_b os-init ${INSTOS}
	cp ${PHYS_SYSROOT}/ostree/repo/config ${PHYS_SYSROOT}_b/ostree/repo

	if [ ! -d "${PHYS_SYSROOT}_b/boot" ] ; then
		mkdir -p ${PHYS_SYSROOT}_b/boot
	fi

	mount "${OSTREE_BOOT_DEVICE}_b" "${PHYS_SYSROOT}_b/boot" || fatal "Error mouting ${OSTREE_BOOT_DEVICE}_b"


	mkdir -p ${PHYS_SYSROOT}_b/boot/efi
	mount ${fs_dev}1 ${PHYS_SYSROOT}_b/boot/efi

	mkdir -p ${PHYS_SYSROOT}_b/boot/loader.0
	ln -s loader.0 ${PHYS_SYSROOT}_b/boot/loader

	# Prep for Install
	if [ "$BL" = "grub" ] ; then
		mkdir -p ${PHYS_SYSROOT}_b/boot/grub2
		touch ${PHYS_SYSROOT}_b/boot/grub2/grub.cfg
	else
		touch  ${PHYS_SYSROOT}_b/boot/loader/uEnv.txt
	fi

	ostree pull $lpull --repo=${PHYS_SYSROOT}_b/ostree/repo --localcache-repo=${PHYS_SYSROOT}/ostree/repo ${INSTNAME}:${INSTBR} || fatal "ostree pull failed"
	ostree admin deploy ${kargs_list} --sysroot=${PHYS_SYSROOT}_b --os=${INSTOS} ${INSTBR} || fatal "ostree deploy failed"
fi

# Replace/install boot loader
if [ -e ${PHYS_SYSROOT}/boot/0/boot/efi/EFI ] ; then
	cp -r  ${PHYS_SYSROOT}/boot/0/boot/efi/EFI ${PHYS_SYSROOT}/boot/efi/
	echo "# GRUB Environment Block" > ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
	if [ "$INSTAB" != "1" ] ; then
	    printf "ab=0\n" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
	else
	    echo -n "#####" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
	fi
	printf "boot_tried_count=0\n" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
	echo -n "###############################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
fi
if [ -e ${PHYS_SYSROOT}/boot/loader/uEnv.txt ] ; then
	bootdir=$(grep ^bootdir= ${PHYS_SYSROOT}/boot/loader/uEnv.txt)
	bootdir=${bootdir#bootdir=}
	if [ "$bootdir" != "" ] && [ -e "${PHYS_SYSROOT}/boot$bootdir" ] ; then
		cp -r ${PHYS_SYSROOT}/boot$bootdir/* ${PHYS_SYSROOT}/boot/efi
	fi
	printf "123A" > ${PHYS_SYSROOT}/boot/efi/boot_ab_flag
	# The first 0 is the boot count, the second zero is the boot entry default
	printf '00WR' > ${PHYS_SYSROOT}/boot/efi/boot_cnt
	if [ "$INSTAB" != "1" ] ; then
		printf '1' > ${PHYS_SYSROOT}/boot/efi/no_ab
	else
		rm -f  ${PHYS_SYSROOT}/boot/efi/no_ab
	fi

fi

# Late curl exec

if [ "${LCURL}" != "" -a "${LCURL}" != "none" ] ; then
	curl ${LCURL} --output /lcurl
	export LCURL="none"
	chmod 755 /lcurl
	/lcurl ${LCURLARG}
fi

# Modify fstab if not using fluxdata
# Caution... If someone resets the /etc/fstab with OSTree this change is lost...
mkdir /var1
if [ "$INSTFLUX" != "1" ] ; then
	if [ "$BL" = "grub" ] ; then
		sed -i -e "s#^LABEL=fluxdata.*#${PHYS_SYSROOT}/ostree/deploy/${INSTOS}/var /var none bind 0 0#" ${PHYS_SYSROOT}/boot/?/ostree/etc/fstab
		if [ "$INSTAB" = 1 ] ; then
			sed -i -e "s#^LABEL=fluxdata.*#${PHYS_SYSROOT}/ostree/deploy/${INSTOS}/var /var none bind 0 0#" ${PHYS_SYSROOT}_b/boot/?/ostree/etc/fstab
		fi
	elif [ "$BL" = "ufsd" ] ; then
		sed -i -e "s#^LABEL=fluxdata.*#${PHYS_SYSROOT}/ostree/deploy/${INSTOS}/var /var none bind 0 0#" ${PHYS_SYSROOT}/ostree/?/etc/fstab
		if [ "$INSTAB" = 1 ] ; then
			sed -i -e "s#^LABEL=fluxdata.*#${PHYS_SYSROOT}/ostree/deploy/${INSTOS}/var /var none bind 0 0#" ${PHYS_SYSROOT}_b/ostree/?/etc/fstab
		fi
	else
		fatal "Error: bl=$BL is not supported"
	fi
	mount --bind ${PHYS_SYSROOT}/ostree/deploy/${INSTOS}/var /var1
else
	mount -o $mount_flags LABEL=fluxdata /var1
fi
if [ -d ${PHYS_SYSROOT}/boot/0/ostree/var ] ; then
	tar -C ${PHYS_SYSROOT}/boot/0/ostree/var/ --xattrs --xattrs-include='*' -cf - . | \
	tar --xattrs --xattrs-include='*' -xf - -C /var1 2> /dev/null
elif [ -d ${PHYS_SYSROOT}/ostree/1/var ] ; then
	tar -C ${PHYS_SYSROOT}/ostree/1/var/ --xattrs --xattrs-include='*' -cf - . | \
	tar --xattrs --xattrs-include='*' -xf - -C /var1 2> /dev/null
fi
umount /var1

if [ "$INSTPOST" = "ishell" ] ; then
	echo " Entering interactive install shell, please exit to contine when done"
	shell_start
fi

# Clean up and finish
if [ "$INSTAB" = 1 ] ; then
	umount ${PHYS_SYSROOT}_b/boot/efi ${PHYS_SYSROOT}_b/boot ${PHYS_SYSROOT}_b
fi
umount ${PHYS_SYSROOT}/boot/efi ${PHYS_SYSROOT}/boot ${PHYS_SYSROOT}

for e in otaboot otaboot_b otaroot otaroot_b fluxdata; do
	if [ -e /dev/mapper/luks${e} ] ; then
		cryptsetup luksClose luks${e}
	fi
done

udevadm control -e

sync
sync
sync
echo 3 > /proc/sys/vm/drop_caches

if [ "$INSTPOST" = "halt" ] ; then
	echo o > /proc/sysrq-trigger
	while [ 1 ] ; do sleep 60; done
elif [ "$INSTPOST" = "shell" ] ; then
	echo " Entering post-install debug shell, exit to reboot."
	shell_start
elif [ "$INSTPOST" = "exit" ] ; then
	exit 0
fi
lreboot
exit 0
