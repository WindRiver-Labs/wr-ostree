include genimage.inc

inherit native

DEPENDS += " \
    dnf-native \
    rpm-native \
    createrepo-c-native \
    gnupg-native \
    ostree-native \
    python3-pyyaml-native \
    shadow-native \
    coreutils-native \
    cpio-native \
    gzip-native \
    u-boot-mkimage-native \
    pbzip2-native \
    ca-certificates-native \
    glib-networking-native \
    depmodwrapper-cross \
    wget-native \
    sloci-image-native \
    umoci-native \
    skopeo-native \
    python3-texttable-native \
    python3-argcomplete-native \
    python3-pykwalify-native \
    opkg-utils-native \
    poky-native \
    qemu-system-native \
    qemuwrapper-cross \
    systemd-systemctl-native \
"

# Required by do_rootfs's intercept_scripts in sdk
DEPENDS += " \
    gdk-pixbuf-native \
    gtk+3-native \
    kmod-native \
"

# Require by wic
DEPENDS += " \
    parted-native syslinux-native gptfdisk-native dosfstools-native \
    mtools-native bmap-tools-native grub-native cdrtools-native \
    btrfs-tools-native squashfs-tools-native pseudo-native \
    e2fsprogs-native util-linux-native tar-native\
"
