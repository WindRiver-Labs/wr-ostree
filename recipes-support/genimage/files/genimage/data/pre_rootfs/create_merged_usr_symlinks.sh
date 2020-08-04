#!/bin/sh
set -x

create_merged_usr_symlinks() {
    root="$1"
    install -d $root/usr/bin $root/usr/sbin $root/usr/lib64
    ln --relative -snf $root/usr/bin $root/bin
    ln --relative -snf $root/usr/sbin $root/sbin
    ln --relative -snf $root/usr/lib64 $root/lib64

    install -d $root/usr/lib
    ln --relative -snf $root/usr/lib $root/lib

    # create base links for multilibs
    multi_libdirs="lib32"
    for d in $multi_libdirs; do
        install -d $root/usr/$d
        ln --relative -snf $root/usr/$d $root/$d
    done
}

create_merged_usr_symlinks ${IMAGE_ROOTFS}
