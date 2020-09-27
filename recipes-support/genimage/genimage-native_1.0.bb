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

python __anonymous () {
    override = d.getVar('OVERRIDE')
    machine = d.getVar('MACHINE')
    if machine == 'bcm-2xxx-rpi4':
        d.appendVar('OVERRIDES', ':{0}:aarch64'.format(machine))
        if not d.getVar('PACKAGE_FEED_ARCHS'):
            d.setVar('PACKAGE_FEED_ARCHS', 'cortexa72 bcm_2xxx_rpi4 noarch')
    elif machine == 'intel-x86-64':
        d.appendVar('OVERRIDES', ':{0}:x86-64'.format(machine))
        if not d.getVar('PACKAGE_FEED_ARCHS'):
            d.setVar('PACKAGE_FEED_ARCHS', 'corei7_64 intel_x86_64 noarch')

    remote_uris = get_remote_uris('file://%s' % (d.getVar('DEPLOY_DIR')),
                                  'rpm',
                                  d.getVar('PACKAGE_FEED_ARCHS'))
    d.setVar("DEFAULT_PACKAGE_FEED", remote_uris)
}
