# Netboot initramfs image.
DESCRIPTION = "OSTree initramfs image"

INITRAMFS_FEATURES ??= "busybox"

PkgsBusyBox = "busybox busybox-udhcpc"
PkgsCoreUtils = "coreutils dhcp-client util-linux-umount util-linux-switch-root iproute2"

INITRAMFS_PKGS = "${@bb.utils.contains('INITRAMFS_FEATURES', 'busybox', "${PkgsBusyBox}", "${PkgsCoreUtils}", d)}"

PACKAGE_INSTALL = "ostree \
  ostree-switchroot \
  initramfs-ostree \
  bash \
  kmod \
  bzip2 \
  gnupg \
  kbd \
  util-linux \
  util-linux-setsid \
  util-linux-mount \
  util-linux-blkid \
  util-linux-lsblk \
  util-linux-fdisk \
  util-linux-fsck \
  util-linux-blockdev \
  dosfstools \
  curl \
  udev \
  mdadm \
  base-passwd \
  rng-tools \
  e2fsprogs-tune2fs \
  e2fsprogs-resize2fs \
  e2fsprogs-e2fsck \
  pv \
  mttyexec \
  gzip \
  findutils \
  tar \
  grep \
  sed \
  gawk \
  glib-networking \
  ca-certificates \
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

# Stop any kind of circular dependency with the flux-ota class
IMAGE_CLASSES_remove = "flux-ota"

inherit core-image image_types_ostree

IMAGE_ROOTFS_SIZE = "8192"

# Users will often ask for extra space in their rootfs by setting this
# globally.  Since this is a initramfs, we don't want to make it bigger
IMAGE_ROOTFS_EXTRA_SPACE = "0"

BAD_RECOMMENDATIONS += "busybox-syslog"

PACKAGE_INSTALL_append = " \
	${@bb.utils.contains('DISTRO_FEATURES', 'luks', 'packagegroup-luks-initramfs', '', d)} \
	${@bb.utils.contains('DISTRO_FEATURES', 'ima', 'packagegroup-ima-initramfs', '', d)} \
"
ROOTFS_POSTPROCESS_COMMAND += "ostree_check_rpm_public_key;add_gpg_key;remove_boot_dir;"

remove_boot_dir() {
	# Remove any image files in the /boot directory
	rm -rf ${IMAGE_ROOTFS}/boot
}

add_gpg_key() {
	gpg_path="${GPG_PATH}"
	if [ -z "$gpg_path" ] ; then
		gpg_path="${TMPDIR}/.gnupg"
	fi
	if [ -n "${OSTREE_GPGID}" ] ; then
		FAIL=1
		if [ -f $gpg_path/pubring.gpg ]; then
			cp $gpg_path/pubring.gpg ${IMAGE_ROOTFS}/usr/share/ostree/trusted.gpg.d/pubring.gpg
			FAIL=0
		fi
		if [ -f $gpg_path/pubring.kbx ]; then
			cp $gpg_path/pubring.kbx ${IMAGE_ROOTFS}/usr/share/ostree/trusted.gpg.d/pubkbx.gpg
			FAIL=0
		fi
		if $FAIL = 1; then
			bb.fatal "Could not locate the public gpg signing key for OSTree"
		fi
	fi
}
