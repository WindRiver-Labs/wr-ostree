#!/bin/bash
set -e

set_systemd_default_target () {
    rootfs=$1
    default_target=$2
    if [ -d $rootfs/etc/systemd/system -a -e $rootfs/usr/lib/systemd/system/$default_target ]; then
        ln -sf /usr/lib/systemd/system/$default_target $rootfs/etc/systemd/system/default.target
    fi
}

set_systemd_default_target $1 $2


