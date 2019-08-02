
OSTREE_INITRAMFS_IMAGE ?= "initramfs-ostree-image"
OSTREE_REPO ?= "${DEPLOY_DIR_IMAGE}/ostree_repo"

OSTREE_BRANCHNAME ?= "${IMAGE_BASENAME}"
OSTREE_OSNAME ?= "wrlinux"
OSTREE_BOOTLOADER_x86 ?= 'grub'
OSTREE_BOOTLOADER_x86-64 ?= 'grub'
OSTREE_BOOTLOADER_arm ?= 'u-boot'
OSTREE_BOOTLOADER_aarch64 ?= 'u-boot'
OSTREE_KERNEL_ARGS ?= "ro rootwait"
OSTREE_SKIP_BOOT_DIFF ?= "0"

OSTREE_GPGID ?= "Wind-River-Linux-Sample"
OSTREE_GPG_PASSPHRASE ?= "windriver"
OSTREE_GPGDIR ?= "${WR_SAMPLE_KEYS_DIR}/rpm_keys"

# Configuration of image upgrade and install variables

OSTREE_USE_AB ?= "1"
OSTREE_REMOTE_NAME ?= "${OSTREE_OSNAME}"
OSTREE_REMOTE_URL ?= ""

# WIC wks configuration variables follow
# The selection of the wks file is:
#   Bootloader - ab/noab

OSTREE_ARCH_WKS_x86 ?= "ostree-grub"
OSTREE_ARCH_WKS_x86-64 ?= "ostree-grub"

OSTREE_ARCH_WKS_arm ?= "ostree-uboot-sd"
OSTREE_ARCH_WKS_arm ?= "ostree-uboot-sd"

OSTREE_ARCH_WKS_aarch64 ?= "ostree-uboot-sd"
OSTREE_ARCH_WKS_aarch6aarch64 ?= "ostree-uboot-sd"

OSTREE_AB_WKS ?= "${@oe.utils.conditional('OSTREE_USE_AB', '1', '-ab', '-noab', d)}"

# Set a fixed size in the wks file for the various partitions from local.conf e.g.
#OSTREE_WKS_EFI_SIZE = "--size=32M --overhead-factor 1"
#OSTREE_WKS_BOOT_SIZE = "--size=300M --overhead-factor 1"
#OSTREE_WKS_ROOT_SIZE = "--size=1024M --overhead-factor 1"
#OSTREE_WKS_FLUX_SIZE = "--size=1024M --overhead-factor 1"

OSTREE_WKS_EFI_SIZE ?= ""
OSTREE_WKS_BOOT_SIZE ?= ""
OSTREE_WKS_ROOT_SIZE ?= ""
OSTREE_WKS_FLUX_SIZE ?= ""


# Parition type for /var
OSTREE_FLUX_PART ?= "${@bb.utils.contains('DISTRO_FEATURES', 'luks', 'luksfluxdata', 'fluxdata',d)}"
