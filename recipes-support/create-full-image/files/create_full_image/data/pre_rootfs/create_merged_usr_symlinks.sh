#!/bin/sh
set -x

create_merged_usr_symlinks() {
    root="$1"
    install -d $root/usr/bin $root/usr/sbin $root/usr/lib64
    ln -snf $root/usr/bin $root/bin
    ln -snf $root/usr/sbin $root/sbin
    ln -snf $root/usr/lib64 $root/lib64

    if [ "/usr/lib" != "/usr/lib64" ]; then
       install -d $root/usr/lib
       ln -snf $root/usr/lib $root/lib
    fi

    # create base links for multilibs
    multi_libdirs="lib32"
    for d in $multi_libdirs; do
        install -d $root/usr/$d
        ln -snf $root/usr/$d $root/$d
    done
}

create_merged_usr_symlinks ${IMAGE_ROOTFS}
