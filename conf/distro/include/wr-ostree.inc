
OSTREE_INITRAMFS_IMAGE ?= "initramfs-ostree-image"
OSTREE_REPO ?= "${DEPLOY_DIR_IMAGE}/ostree_repo"

OSTREE_BRANCHNAME ?= "${IMAGE_BASENAME}"
OSTREE_OSNAME ?= "wrlinux"
OSTREE_BOOTLOADER_x86 = 'grub'
OSTREE_BOOTLOADER_x86-64 = 'grub'
OSTREE_BOOTLOADER_arm = 'u-boot'
OSTREE_INITRAMFS_IMAGE ?= "initramfs-ostree-image"
OSTREE_KERNEL_ARGS ?= "rw rootwait rootdelay=2 ostree_root=LABEL=otaroot"

OSTREE_GPGID ?= "Wind-River-Linux-Sample"
OSTREE_GPG_PASSPHRASE ?= "windriver"
OSTREE_GPGDIR ?= "${WR_SAMPLE_KEYS_DIR}/rpm_keys"
