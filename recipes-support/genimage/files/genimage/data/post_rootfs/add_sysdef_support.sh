#!/bin/sh
set -x

add_sysdef_support() {
    rootfs=$1
    sysdefdir="${OECORE_NATIVE_SYSROOT}/usr/share/genimage/data/sysdef"
    install -d  ${rootfs}/usr/bin/
    install -m 0755 ${sysdefdir}/sysdef.sh ${rootfs}/usr/bin/

    install -d ${rootfs}/usr/lib/systemd/system/
    install -m 0664 ${sysdefdir}/sysdef.service ${rootfs}/usr/lib/systemd/system/

    systemctl --root ${rootfs}  enable sysdef.service

    mkdir -p ${rootfs}/usr/lib/systemd/system-preset/
    echo "enable sysdef.service" > ${rootfs}/usr/lib/systemd/system-preset/98-sysdef.preset
}

add_sysdef_support $1
