#!/bin/bash
set -x

add_gpg_key() {
    rootfs=$1
    gpg_path=$2
    if [ -f $gpg_path/pubring.gpg ]; then
        cp $gpg_path/pubring.gpg $rootfs/usr/share/ostree/trusted.gpg.d/pubring.gpg
    fi
    if [ -f $gpg_path/pubring.kbx ]; then
        cp $gpg_path/pubring.kbx $rootfs/usr/share/ostree/trusted.gpg.d/pubkbx.gpg
    fi
}

add_gpg_key $1 $2
