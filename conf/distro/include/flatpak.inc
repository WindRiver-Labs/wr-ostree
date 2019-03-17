REFKIT_DEFAULT_DISTRO_FEATURES += " \
    usrmerge \
    systemd \
    pam \
    flatpak \
"

# Enable D-Bus session bus support, needed by flatpak.
PACKAGECONFIG_append_pn-dbus_df-refkit-config = " user-session"

OSTREE_INITRAMFS_IMAGE ?= "initramfs-ostree-image"
OSTREE_REPO ?= "${DEPLOY_DIR_IMAGE}/ostree_repo"

OSTREE_BRANCHNAME ?= "${IMAGE_BASENAME}"
OSTREE_OSNAME ?= "pulsar-linux"
OSTREE_BOOTLOADER_x86 = 'grub'
OSTREE_BOOTLOADER_x86-64 = 'grub'
OSTREE_BOOTLOADER_arm = 'u-boot'
OSTREE_INITRAMFS_IMAGE ?= "initramfs-ostree-image"
OSTREE_KERNEL_ARGS ?= "rw rootwait rootdelay=2 ostree_root=LABEL=otaroot"

IMAGE_BOOT_FILES_x86 = "grub-efi-bootx64.efi grub.cfg bzImage"
IMAGE_BOOT_FILES_x86-64 = "grub-efi-bootx64.efi grub.cfg bzImage"

OSTREE_GPGID ?= "Wind-River-Linux-Sample"
OSTREE_GPG_PASSPHRASE ?= "windriver"
OSTREE_GPGDIR ?= "${WR_SAMPLE_KEYS_DIR}/rpm_keys"
