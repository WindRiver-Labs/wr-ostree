# Netboot initramfs image.
DESCRIPTION = "OSTree initramfs image"

PACKAGE_INSTALL = "ostree-switchroot initramfs-ostree bash kmod bzip2 sed tar kbd coreutils util-linux grep gawk udev mdadm base-passwd ${ROOTFS_BOOTSTRAP_INSTALL} rng-tools findutils gzip e2fsprogs-tune2fs e2fsprogs-resize2fs pv util-linux-blkid util-linux-lsblk"

PACKAGE_EXCLUDE = "busybox busybox-dev busybox-udhcpc busybox-dbg busybox-ptest busybox-udhcpd busybox-hwclock busybox-syslog"

# Do not pollute the initrd image with rootfs features
IMAGE_FEATURES = ""

export IMAGE_BASENAME = "initramfs-ostree-image"
IMAGE_LINGUAS = ""

LICENSE = "MIT"

IMAGE_FSTYPES = "${INITRAMFS_FSTYPES}"

inherit core-image

IMAGE_ROOTFS_SIZE = "8192"

# Users will often ask for extra space in their rootfs by setting this
# globally.  Since this is a initramfs, we don't want to make it bigger
IMAGE_ROOTFS_EXTRA_SPACE = "0"

BAD_RECOMMENDATIONS += "busybox-syslog"
