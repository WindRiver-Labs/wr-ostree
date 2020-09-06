#!/bin/bash
set -x

## Require environments
# OSTREE_CONSOLE
# KERNEL_PARAMS

# Modify the grub.cfg
update_grub_cfg() {
    rootfs=$1
    if [ ! -e $rootfs/boot/efi/EFI/BOOT/grub.cfg ] ; then
        exit 0
    fi

    sed -i -e "s#^\(set ostree_console\).*#\1=\"$OSTREE_CONSOLE\"#g" $rootfs/boot/efi/EFI/BOOT/grub.cfg
    sed -i -e "s#^\(set kernel_params\).*#\1=\"$KERNEL_PARAMS\"#g" $rootfs/boot/efi/EFI/BOOT/grub.cfg
}

update_grub_cfg $1
