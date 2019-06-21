# Netboot initramfs image.
DESCRIPTION = "OSTree initramfs image"

INITRAMFS_FEATURES = "busybox"

PkgsBusyBox = "busybox busybox-udhcpc"
PkgsCoreUtils = "coreutils dhcp-client"

INITRAMFS_PKGS = "${@bb.utils.contains('INITRAMFS_FEATURES', 'busybox', "${PkgsBusyBox}", "${PkgsCoreUtils}", d)}"

PACKAGE_INSTALL = "ostree \
  ostree-switchroot \
  initramfs-ostree \
  busybox \
  bash \
  kmod \
  bzip2 \
  gnupg \
  kbd \
  util-linux \
  util-linux-mount \
  util-linux-blkid \
  util-linux-lsblk \
  util-linux-fdisk \
  util-linux-fsck \
  dosfstools \
  curl \
  udev \
  mdadm \
  base-passwd \
  rng-tools \
  e2fsprogs-tune2fs \
  e2fsprogs-resize2fs \
  pv \
  gzip \
  findutils \
  tar \
  grep \
  sed \
  gawk \
  ${INITRAMFS_PKGS} \
"

PACKAGE_EXCLUDE += "python"

# Do not pollute the initrd image with rootfs features
IMAGE_FEATURES = ""

NO_RECOMMENDATIONS = "1"

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

PACKAGE_INSTALL_append = " \
	${@bb.utils.contains('DISTRO_FEATURES', 'luks', 'packagegroup-luks-initramfs', '', d)} \
"

