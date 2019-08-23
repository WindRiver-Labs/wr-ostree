BANNER[feature_ostree-sample-keys] = "${@'WARNING: You are using the example Wind River gpg signing keys.  These keys are provided as samples and are unsafe to use in production.  Please consider running "layers/meta-secure-core/meta-signing-key/scripts/create-user-key-store.sh".  This script can generate a complete set of new keys and print the variables you should set in the local.conf.' if d.getVar('WR_KEYS_DIR') == d.getVar('WR_SAMPLE_KEYS_DIR') else ''}"

OSTREE_INITRAMFS_IMAGE ?= "initramfs-ostree-image"
OSTREE_REPO ?= "${DEPLOY_DIR_IMAGE}/ostree_repo"

OSTREE_BRANCHNAME ?= "${IMAGE_BASENAME}"
OSTREE_OSNAME ?= "wrlinux"
# This is set to the name of the loader to include into a disk image
# Not all BSPs will need this, so it can be unset by the BSP
OSTREE_BOOTLOADER_INCLUDE ??= "${OSTREE_BOOTLOADER}"
OSTREE_KERNEL_ARGS ??= "ro rootwait"

# The OSTREE_SKIP_BOOT_DIFF can be one of the following:
#   0 = Perform a full fsck and boot diff
#   1 = Skip the FSCK check
#   2 = Skip the FSCK and the boot
OSTREE_SKIP_BOOT_DIFF ??= "2"

OSTREE_GPGID ?= "Wind-River-Linux-Sample"
OSTREE_GPG_PASSPHRASE ?= "windriver"
OSTREE_GPGDIR ?= "${WR_KEYS_DIR}/rpm_keys"

# Configuration of image upgrade and install variables

OSTREE_USE_AB ??= "1"
OSTREE_REMOTE_NAME ??= "${OSTREE_OSNAME}"
OSTREE_REMOTE_URL ??= ""

# WIC wks configuration variables follow
# The selection of the wks file is:
#   Bootloader - ab/noab

OSTREE_ARCH_WKS_x86 ??= "ostree-grub"
OSTREE_ARCH_WKS_x86-64 ??= "ostree-grub"

OSTREE_ARCH_WKS_arm ??= "ostree-uboot-sd"
OSTREE_ARCH_WKS_arm ??= "ostree-uboot-sd"

OSTREE_ARCH_WKS_aarch64 ??= "ostree-uboot-sd"
OSTREE_ARCH_WKS_aarch6aarch64 ??= "ostree-uboot-sd"

OSTREE_AB_WKS ??= "${@oe.utils.conditional('OSTREE_USE_AB', '1', '-ab', '-noab', d)}"

# Set a fixed size in the wks file for the various partitions from local.conf e.g.
#OSTREE_WKS_EFI_SIZE = "--size=32M --overhead-factor 1"
#OSTREE_WKS_BOOT_SIZE = "--size=300M --overhead-factor 1"
#OSTREE_WKS_ROOT_SIZE = "--size=1024M --overhead-factor 1"
#OSTREE_WKS_FLUX_SIZE = "--size=1024M --overhead-factor 1"

OSTREE_WKS_EFI_SIZE ??= "--size=32M"
OSTREE_WKS_BOOT_SIZE ??= ""
OSTREE_WKS_ROOT_SIZE ??= ""
OSTREE_WKS_FLUX_SIZE ??= ""

# Parition type for /var
OSTREE_FLUX_PART ??= "${@bb.utils.contains('DISTRO_FEATURES', 'luks', 'luksfluxdata', 'fluxdata',d)}"

# Name of the boot loader to include in the file system
OSTREE_BOOTLOADER_x86 ??= 'grub'
OSTREE_BOOTLOADER_x86-64 ??= 'grub'
OSTREE_BOOTLOADER_arm ??= 'u-boot'
OSTREE_BOOTLOADER_aarch64 ??= 'u-boot'

# Define any special partitions required where loaders, firmware etc
# live It is intended that these are defined by the BSP as needed
OSTREE_SD_UBOOT_WIC1 ??= "part / --source rawcopy --sourceparams="file=${UBOOT_BINARY}" --ondisk mmcblk --no-table --align 1 --size 1"
OSTREE_SD_UBOOT_WIC2 ??= ""
OSTREE_SD_UBOOT_WIC3 ??= ""
OSTREE_SD_UBOOT_WIC4 ??= ""

# This is set to the name of the loader to include into a disk image
# Not all BSPs will need this, so it can be unset by the BSP
OSTREE_SD_BOOT_ALIGN ??= "4"

# Use this WKS file with wic (WKS_FILE = "${OSTREE_WKS_FILE}" should be set in the feature
# template or local.conf
OSTREE_WKS_FILE ??= "${OSTREE_ARCH_WKS}${OSTREE_AB_WKS}.wks.in"

# Below are additional variables that can be set in local.conf which are the
# defaults for the network installer

# Boot Loader Magic block offset (where the first partition should start)
# NOTE: This is value is numeric in MB only e.g. OSTREE_FDISK_FSZ = "64"
# OSTREE_FDISK_BLM ??= ""
# Size of the Fat / EFI partition
# OSTREE_FDISK_FSZ ??= ""
# Size of the Boot partition
# OSTREE_FDISK_BSZ ??= ""
# Size of the Root partition
# OSTREE_FDISK_RSZ ??= ""

# What uboot command should be used to start the kernel in the boot.scr file
# OSTREE_UBOOT_CMD ??= "bootz"

# Use file system links for the ostree boot mounts (more secure and the default)
#    OSTREE_BOOTSCR ??= "fs_links"
# Or read a uEnv.txt file from the disk which allows kernel args 
# to be controlled via ostree (less secure)
#    OSTREE_BOOTSCR ??= "env_import"
