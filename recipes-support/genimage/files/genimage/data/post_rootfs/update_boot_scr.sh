#!/bin/bash
set -x

## Require environments
# OSTREE_CONSOLE

# Modify the boot.scr
update_boot_scr() {
    rootfs=$1
    branch=$2
    ab=$3
    url=$4
    if [ ! -e $rootfs/boot/boot.scr ] ; then
        exit 0
    fi
    tail -c+73 $rootfs/boot/boot.scr > $rootfs/boot/boot.scr.raw

    sed -i -e "s#console=[^ ]* console=[^ ]*#$OSTREE_CONSOLE#g" $rootfs/boot/boot.scr.raw
    perl -p -i -e "s#^( *setenv BRANCH) .*#\$1 $branch# if (\$_ !~ /oBRANCH/) " $rootfs/boot/boot.scr.raw
    perl -p -i -e "s#^( *setenv URL) .*#\$1 $url# if (\$_ !~ /oURL/) " $rootfs/boot/boot.scr.raw
    perl -p -i -e "s#instab=[^ ]* #instab=$ab #" $rootfs/boot/boot.scr.raw

    mkimage -A arm -T script -O linux -d $rootfs/boot/boot.scr.raw $rootfs/boot/boot.scr
    rm -f $rootfs/boot/boot.scr.raw
}

update_boot_scr $1 $2 $3 $4
