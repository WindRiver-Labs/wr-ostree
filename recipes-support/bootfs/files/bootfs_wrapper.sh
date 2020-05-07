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

dir=$(pwd)
source $OECORE_NATIVE_SYSROOT/usr/bin/_create_full_image_h.sh
deploy="${WORK_DIR}/deploy"
_ENVFILE=""
INITRD_PACKAGES="
    ostree ostree-switchroot
    initramfs-ostree bash
    kmod bzip2 gnupg kbd
    util-linux util-linux-setsid
    util-linux-mount util-linux-blkid
    util-linux-lsblk util-linux-fdisk
    util-linux-fsck util-linux-blockdev
    dosfstools curl udev mdadm
    base-passwd rng-tools e2fsprogs-tune2fs
    e2fsprogs-resize2fs pv gzip findutils
    tar grep sed gawk busybox busybox-udhcpc
"
create_merged_usr_symlinks() {
    rootfs=$1
    cd $rootfs
    dirs="bin sbin lib lib64 lib32"
    for d in $dirs; do
        [ ! -e $d -a -e usr/$d ] && ln -snf usr/$d $d
    done
    cd -
}

create_ostree_initrd(){
    RAM_ROOTFS_LIST="$INITRD_PACKAGES"
    create_ram_rootfs
    create_merged_usr_symlinks ${RAM_ROOTFS_DIR}/rootfs
    add_gpg_key ${RAM_ROOTFS_DIR}/rootfs
    create_initrd
    mv ${RAM_ROOTFS_DIR}/wrlinux-image-initramfs.rootfs.cpio.gz $deploy/initramfs-ostree-image.cpio.gz
}

create_ostree_bootloader_and_kernel(){
    MNT_ROOTFS_LIST="grub-efi kernel-image"
    create_mount_rootfs
    cp ${MNT_ROOTFS_DIR}/rootfs/boot/EFI/BOOT/bootx64.efi $deploy
    cp ${MNT_ROOTFS_DIR}/rootfs/boot/bzImage $deploy

	# Workaround wic create
    cp ${MNT_ROOTFS_DIR}/rootfs/boot/EFI/BOOT/bootx64.efi $deploy/grub-efi-bootx64.efi
}

add_gpg_key() {
    rootfs=$1
    gpg_path="$OECORE_NATIVE_SYSROOT/usr/share/bootfs/boot_keys"
    if [ -f $gpg_path/pubring.gpg ]; then
        cp $gpg_path/pubring.gpg $rootfs/usr/share/ostree/trusted.gpg.d/
    fi  
    if [ -f $gpg_path/pubkbx.gpg ]; then
        cp $gpg_path/pubkbx.gpg $rootfs/usr/share/ostree/trusted.gpg.d/
    fi  
}

BOOTFS_S="
    initramfs-ostree-image.cpio.gz
    bzImage
    bootx64.efi
    grub-efi-bootx64.efi
"
is_create_deploy() {
    for f in $BOOTFS_S;do
        if [ ! -e $deploy/$f ]; then
            echo "$deploy/$f not found"
            return 0
        fi
    done
    return 1
}

create_deploy(){
    is_create_deploy || return

    do_clean
    mkdir -p $deploy
    RPM_REPO="%PACKAGE_FEED_URIS%/%PACKAGE_FEED_BASE_PATHS%"
    prepare_work
    create_ostree_bootloader_and_kernel
    create_ostree_initrd
}

get_image_name() {
    local_repo_dir="$1"
    if [ -n "$local_repo_dir" ]; then
        d=`find $local_repo_dir -name heads`
        ls -tr $d|tail -1
        return
    fi

    builddir=`mktemp -d ./buildXXXX`
    builddir=`realpath $builddir`
    cd $builddir
    wget -q -r -np -R "index.html*" "$OSTREE_REMOTE_URL/refs/heads/"
    d=`find . -name heads`
    ls -tr $d|tail -1
    cd - >/dev/null
    rm -rf $builddir
    return
}

usage() {
        cat<<EOF
usage: $0 [args]

This command will build a small boot image which can be used for
deployment with OSTree.

Local Install Options:
 -l <dir> Use a different directory for an install from a local
          repository

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

INST_URL=""
LOCAL_REPO_DIR=""
while getopts "a:Bb:d:e:hLl:Nns:u:w" opt; do
    case ${opt} in
        e)
            _ENVFILE=$OPTARG
            ;;
        l)
            LOCAL_REPO_DIR=$OPTARG
            if [ "$LOCAL_REPO_DIR" = "0" ]; then
                echo "-l 0 is not supported by sdk"
                usage
                exit 1
            fi
            ;;
        L)
            echo "-L is not supported by sdk"
            usage
            exit 1
            ;;
        u)
            INST_URL=$OPTARG
            ;;
        h)
            usage
    esac
done

pseudo
create_deploy

cd $dir
ENVFILE="${WORK_DIR}/bootfs.env"
if [ -z "$_ENVFILE" ]; then
    _ENVFILE=$OECORE_NATIVE_SYSROOT/usr/share/bootfs/bootfs_common.env
fi
cp $_ENVFILE $ENVFILE
sed -i "s#^DEPLOY_DIR_IMAGE=.*#DEPLOY_DIR_IMAGE='$deploy'#g" $ENVFILE
sed -i "s#^IMAGE_ROOTFS=.*#IMAGE_ROOTFS='$PWD/bootfs'#g" $ENVFILE
sed -i "s#^STAGING_KERNEL_DIR=.*#STAGING_KERNEL_DIR='$deploy'#g" $ENVFILE
export IMAGE_ROOTFS
export DEPLOY_DIR_IMAGE
export IMAGE_BASENAME
export STAGING_KERNEL_DIR
eval `cat $ENVFILE`

if [ "$INST_URL" != "" ] ; then
    OSTREE_REMOTE_URL="$INST_URL"
fi

if ! grep -q IMAGE_BASENAME $ENVFILE; then
    echo "IMAGE_BASENAME=`get_image_name $LOCAL_REPO_DIR`" >> $ENVFILE
fi
$OECORE_NATIVE_SYSROOT/usr/share/bootfs/scripts/bootfs.sh -s 0 $@ -e $ENVFILE
