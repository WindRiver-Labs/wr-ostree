#!/bin/bash
#  This script will build a mini bootstrap image for a target system.
#
#* Copyright (c) 2019 Jason Wessel - Wind River Systems, Inc.
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


ENVFILE="auto"
PARTSIZE=${PARTSIZE=256}
COMPRESS="${COMPRESS=1}"
DO_BUILD_BOOTFS=1
MODIFY_BOOT_SCR=1
EXTRA_INST_ARGS=""
INST_URL=""
INST_BRANCH=""
INST_DEV=""
SKIP_WIC=0
OUTDIR=$PWD/bootfs

usage() {
        cat<<EOF
usage: $0 [args]

This command will build a small boot image which can be used for
deployment with OSTree.

Network Install options:
 -b <branch>  branch to use for net install instbr=
 -u <url>     url to use for net install insturl=
 -d <device>  device to use for net install instdev=
 -a <args>    Additional kernel boot argument for the install

Image Creation Options:
 -B         Skip build of the bootfs directory and use what ever is in there
 -e <file>  env file for reference image e.g. core-image-minimal.env
 -n         Turn off the commpression of the image
 -N         Do not modify the boot.scr file on the image
 -s <#>     Size in MB of the boot partition (default 256)
            Setting this to zero will make the partition as small as possible
 -w         Skip wic disk creation

EOF
        exit 0
}

fatal() {
	echo "$*"
	exit 1
}

modify_boot_scr() {
	if [ ! -e $OUTDIR/boot.scr ] ; then
		return
	fi
	# Strip off original header
	tail -c+73 $OUTDIR/boot.scr > $OUTDIR/boot.scr.raw
	perl -p -i -e "s#^( *setenv BRANCH) .*#\$1 $INST_BRANCH $EXTRA_INST_ARGS# if (\$_ !~ /oBRANCH/) " $OUTDIR/boot.scr.raw
	if [ -n "$INST_URL" ] ; then
		perl -p -i -e "s#^( *setenv URL) .*#\$1 $INST_URL# if (\$_ !~ /oURL/) " $OUTDIR/boot.scr.raw
	fi
	if [ -n "$INST_DEV" ] ; then
		perl -p -i -e "s#instdev=.*?([ \"])#instdev=$INST_DEV\$1#" $OUTDIR/boot.scr.raw
	fi
	OLDPATH="$PATH"
	PATH=$RECIPE_SYSROOT_NATIVE/usr/bin:$RECIPE_SYSROOT_NATIVE/bin:$PATH
	which mkimage > /dev/null
	if [ $? != 0 ] ; then
		fatal "ERROR: Could not locate mkimage utility"
	fi
	mkimage -A arm -T script -O linux -d $OUTDIR/boot.scr.raw $OUTDIR/boot.scr || fatal "ERROR: mkimage failed"
	rm -f $OUTDIR/boot.scr.raw
	PATH="$OLDPATH"
}

do_cp_and_sig() {
	cp "$1" "$2"
	if [ -e "$1.sig" ] ; then
		cp "$1.sig" "$2.sig"
	fi
	if [ -e "$1.p7b" ] ; then
		cp "$1.p7b" "$2.p7b"
	fi
}

sign_grub() {
	OLDPATH="$PATH"
	PATH=$RECIPE_SYSROOT_NATIVE/usr/bin:$RECIPE_SYSROOT_NATIVE/bin:$PATH
	rm -rf grub-key; mkdir grub-key ; chmod 700 grub-key
	echo allow-loopback-pinentry > grub-key/gpg-agent.conf
	gpg --batch  --passphrase "$BOOT_GPG_PASSPHRASE" --pinentry-mode loopback --homedir grub-key --import "$BOOT_KEYS_DIR/BOOT-GPG-PRIVKEY-$BOOT_GPG_NAME" || fatal "Error importing signing key"
	for e in `ls $OUTDIR/EFI/BOOT/grub.cfg`; do
		echo Signing: $e
		rm -f $e.sig
		echo "$BOOT_GPG_PASSPHRASE" | gpg --pinentry-mode loopback --homedir grub-key -u "$BOOT_GPG_NAME" --batch --detach-sign --passphrase-fd 0 $e || fatal "Error signing $e"
	done
	PATH="$OLDPATH"
}

create_grub_cfg() {
	if [ "$grubcfg" != "" ] ; then
		echo "Using grub.cfg: $grubcfg"
		cp $grubcfg $OUTDIR/EFI/BOOT/grub.cfg
		return
	fi
	idev=/dev/vda
	if [ "$INST_DEV" != "" ] ; then
		idev=$INST_DEV
	fi
	ostree_dir=${DEPLOY_DIR_IMAGE}/ostree_repo
	iurl="$OSTREE_REMOTE_URL"
	if [ "$INST_URL" != "" ] ; then
		iurl="$INST_URL"
	fi
	bootargs="console=ttyS0,115200 rdinit=/install $EXTRA_INST_ARGS instdev=$idev instname=wrlinux instbr=$INST_BRANCH insturl=$iurl instab=$OSTREE_USE_AB instsf=1"
	if [ "$OSTREE_FLUX_PART" = "luksfluxdata" -a "$EXTRA_INST_ARGS" = "${EXTRA_INST_ARGS/LUKS/}" ] ; then
		bootargs="$bootargs LUKS=1"
	fi
	echo "Using bootargs: $bootargs"
	cat<<EOF> $OUTDIR/EFI/BOOT/grub.cfg
set default="0"
set timeout=3
set color_normal='light-gray/black'
set color_highlight='light-green/blue'

get_efivar -f uint8 -s secured SecureBoot
if [ "\${secured}" = "1" ]; then
    # Enable user authentication to make grub unlockable
    set superusers="$OSTREE_GRUB_USER"
     password_pbkdf2 $OSTREE_GRUB_USER $(cat $OSTREE_GRUB_PW_FILE)
else
    get_efivar -f uint8 -s unprovisioned SetupMode

    if [ "\${unprovisioned}" = "1" ]; then
        set timeout=0

        menuentry "Automatic Certificate Provision" --unrestricted {
            chainloader \${prefix}/LockDown.efi
        }
    fi
fi
menuentry "OSTree Install $idev" --unrestricted {
    set fallback=1
    efi-watchdog enable 0 180
    linux \${prefix}/bzImage $bootargs
    initrd \${prefix}/initrd
}
EOF
}

build_efi_area() {
	bzimage=$(ls tmp*/deploy/images/*/bzImage)
	initramfs=$(ls tmp*/deploy/images/*/initramfs-ostree-image*.cpio.gz |grep -v rootfs)
	bootx64=$(ls tmp*/deploy/images/*/bootx64.efi 2> /dev/null)
	lockdown=$(ls tmp*/deploy/images/*/LockDown.efi 2> /dev/null)
	mmx64=$(ls tmp*/deploy/images/*/mmx64.efi 2> /dev/null)

	mkdir -p $OUTDIR/EFI/BOOT

	echo "Using grub: $grub"
	echo "Using kernel: $bzimage"
	echo "Using initrd: $initramfs"
	if [ "$bootx64" != "" ] ; then
		echo "Using bootx64.efi: $bootx64"
		cp $bootx64 $OUTDIR/EFI/BOOT/bootx64.efi
	else
		echo "Using bootx64.efi: $grub"
		do_cp_and_sig $grub $OUTDIR/EFI/BOOT/bootx64.efi
	fi

	do_cp_and_sig $grub $OUTDIR/EFI/BOOT/grubx64.efi
	do_cp_and_sig $bzimage $OUTDIR/EFI/BOOT/bzImage
	do_cp_and_sig $initramfs $OUTDIR/EFI/BOOT/initrd
	if [ "$lockdown" != "" ] ; then
		do_cp_and_sig $lockdown $OUTDIR/EFI/BOOT/LockDown.efi
	fi
	if [ "$mmx" != "" ] ; then
		do_cp_and_sig $mmx64 $OUTDIR/EFI/BOOT/mmx64.efi
	fi
	create_grub_cfg
	if [ "$lockdown" != "" ] ; then
		sign_grub
	fi
}


build_bootfs() {
	echo "Building: bootfs"
	rm -rf $OUTDIR
	$FAKEROOTCMD mkdir -p $OUTDIR
	# Copy IMAGE_BOOT_FILES
	set -f
	bfiles="${IMAGE_BOOT_FILES}"
	for f in $bfiles; do
		set +f
		argFROM=$(echo "$f" |sed -e 's#;.*##')
		argTO=$(echo "$f" |sed -e 's#.*;##')
		if [ "$argFROM" != "$argTO" ] ; then
			if [ ! -e $OUTDIR/$argTO ] ; then
				d=$(dirname $OUTDIR/$argTO)
				[ ! -d $d ] && mkdir $d
				cp ${DEPLOY_DIR_IMAGE}/$argFROM $OUTDIR/$argTO
			else
				fatal "Error locating: $argFROM"
			fi
		else
			cp ${DEPLOY_DIR_IMAGE}/$f $OUTDIR
		fi
	done
	set +f
	# check for grub
	grub=$(ls tmp*/deploy/images/*/grub*.efi 2> /dev/null)
	if [ "$grub" != "" ] ; then
		build_efi_area
	fi
}

write_wic() {
	if [ $SKIP_WIC = 1 ] ; then
		return
	fi
	echo "Writing: ustart.img and ustart.img.bmap"
	rm -rf out-tmp
	cmd="wic create -e ustart -v . -m -s ustart.wks -o out-tmp"
	$cmd || fatal "Error running: $cmd"
	mv out-tmp/*.direct ustart.img
	mv out-tmp/*.bmap ustart.img.bmap
	rmdir out-tmp
	if [ "$COMPRESS" = "1" ] ; then
		echo "Compressing image and writing: ustart.img.gz"
		gzip -f ustart.img
	fi
	echo "=================== SUCCESS ====================="
	echo "==== Write image to device with command below ==="
	echo "================================================="
	if [ "$COMPRESS" = "1" ] ; then
		echo "bmaptool copy --bmap ustart.img.bmap ustart.img.gz /dev/YOUR_DISK_DEVICE"
	else
		echo "bmaptool copy --bmap ustart.img.bmap ustart.img /dev/YOUR_DISK_DEVICE"
	fi
}

while getopts "a:Bb:d:e:hNns:u:w" opt; do
	case ${opt} in
		a)
			EXTRA_INST_ARGS=$OPTARG
			;;
		b)
			INST_BRANCH=$OPTARG
			;;
		B)
			DO_BUILD_BOOTFS=0
			;;
		d)
			INST_DEV=$OPTARG
			;;
		e)
			ENVFILE=$OPTARG
			;;
		s)
			PARTSIZE=$OPTARG
			;;
		n)
			COMPRESS=0
			;;
		N)
			MODIFY_BOOT_SCR=0
			;;
		u)
			INST_URL=$OPTARG
			;;
		h)
			usage
			;;
		w)
			SKIP_WIC=1
			;;
		*)
			usage
			;;
	esac
done

### Main ###

which perl > /dev/null
if [ $? != 0 ] ; then
	fatal "Could not locate perl binary in PATH";
fi

if [ "$ENVFILE" = "" -o "$ENVFILE" = "auto" ] ; then
	# Generate an env file if possible...
	latest=`ls -tr tmp*/deploy/images/*/ostree_repo/refs/heads/|tail -1`
	if [ "$latest" = "" ] ; then
		fatal "ERROR: No .env found in tmp*/deploy/images/*/*.env"
	fi
	ENVFILE=$PWD/$latest.env
	if [ ! -e $ENVFILE ] ; then
		echo "Running bitbake -e $latest > $ENVFILE"
		bitbake -e $latest > $ENVFILE || fatal "Error running bitbake"
	else
		echo "Using cached: $ENVFILE"
	fi
fi

if [ ! -e "$ENVFILE" -a "$ENVFILE" != "${ENVFILE%.env}" ] ; then
	echo "Running bitbake -e ${ENVFILE%.env} > $ENVFILE"
	bitbake -e -e ${ENVFILE%.env} > $ENVFILE || fatal "Error running bitbake"
fi

echo "Env settings from: $ENVFILE"

cp $ENVFILE ustart.env
eval `grep ^FAKEROOTCMD $ENVFILE`
eval `grep ^RECIPE_SYSROOT_NATIVE $ENVFILE`
eval `grep ^IMAGE_BOOT_FILES $ENVFILE`
eval `grep ^DEPLOY_DIR_IMAGE $ENVFILE`
eval `grep ^IMAGE_BASENAME $ENVFILE`
eval `grep ^BOOT_ $ENVFILE`
eval `grep ^OSTREE_ $ENVFILE | perl -p -e '($a,$b) = split(/=/,$_,2); $a =~ s/-/_/g; $_ = "$a=$b"'`

if [ "$INST_URL" != "" ] ; then
	OSTREE_REMOTE_URL="$INST_URL"
fi
if [ "$OSTREE_REMOTE_URL" = "" ] ; then
	fatal 'ERROR: OSTREE_REMOTE_URL = "your_ostree_repo_url" must be defined in local.conf'
fi

export PSEUDO_PREFIX=$RECIPE_SYSROOT_NATIVE/usr
export PSEUDO_LOCALSTATEDIR=$PWD/pseudo
export PSEUDO_PASSWD=$PWD/rootfs/etc
export PSEUDO_NOSYMLINKEXP=1

if [ -z "$INST_BRANCH" ] ; then
	INST_BRANCH=$IMAGE_BASENAME
fi

[ $DO_BUILD_BOOTFS = 1 ] && build_bootfs
[ $MODIFY_BOOT_SCR = 1 ] && modify_boot_scr

echo "Writing: ustart.wks"

if [ "$grub" != "" ] ; then
	echo "bootloader --ptable gpt" > ustart.wks
else
	echo "bootloader --ptable msdos" > ustart.wks
fi
PARTSZ=""
if [ "$PARTSIZE" != "0" ] ; then
	PARTSZ="--fixed-size=$PARTSIZE"
fi
echo "part / --source rootfs --rootfs-dir=$OUTDIR --ondisk sda --fstype=vfat --label boot --active --align 2048 $PARTSZ" >> ustart.wks

write_wic
exit 0

# TODO... 
# Instructions for trail with a sample disk
# ../layers/wr-ostree/scripts/bootfs.sh -n
# qemu-img create -f raw img 10G
# dd if=ustart.img of=img conv=notrunc
# LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH swtpm socket --tpm2 --tpmstate dir=$PWD/my_tpm --ctrl type=unixio,path=$PWD/my_tpm/tpm-sock & qemu-system-x86_64 --enable-kvm --nographic -vnc :5 -drive file=OVMF_CODE.fd,format=raw,readonly,if=pflash,unit=0 -drive if=pflash,format=raw,unit=1,file=OVMF_VARS.fd -chardev "socket,id=chrtpm0,path=$PWD/my_tpm/tpm-sock" -tpmdev 'emulator,id=tpm0,chardev=chrtpm0' -device 'tpm-tis,tpmdev=tpm0' -drive file=img,if=virtio,format=raw -m 1024 -serial mon:stdio -netdev type=user,id=h1,tftp=bootfs,bootfile=EFI/BOOT/bootx64.efi -device e1000,netdev=h1,mac=00:55:55:01:01:01 -usbdevice tablet -cpu qemu64,+ssse3,+sse4.1,+sse4.2,+x2apic,rdrand -device virtio-rng-pci