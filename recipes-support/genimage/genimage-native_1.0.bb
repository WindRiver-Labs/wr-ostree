include genimage.inc

inherit native

SRC_URI += " \
    file://environment-appsdk-native \
"

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
    qemu-system-native \
    qemuwrapper-cross \
    systemd-systemctl-native \
    bootfs-native \
    bmap-tools-native \
    util-linux-native \
    perl-native \
"

# Required by do_rootfs's intercept_scripts in sdk
DEPENDS += " \
    gdk-pixbuf-native \
    gtk+3-native \
    kmod-native \
"

# Require wic
DEPENDS += " \
    wic-native \
"

# Make sure the existence of rpms required by yaml files
# that are generated by exampleyamls
RPMS_DEPENDS = " \
    wrlinux-image-small:do_rootfs \
    core-image-minimal:do_rootfs \
    core-image-sato:do_rootfs \
    container-base:do_rootfs \
    startup-container:do_package_write_rpm \
    packagegroup-core-boot:do_package_write_rpm \
    packagegroup-xfce-base:do_package_write_rpm \
    lxdm:do_package_write_rpm \
    wr-themes:do_package_write_rpm \
    gsettings-desktop-schemas:do_package_write_rpm \
"
RPMS_DEPENDS_append_intel-x86-64 = " \
    vboxguestdrivers:do_package_write_rpm \
"

# Make sure the existence of ostree initramfs image
do_install[depends] += "initramfs-ostree-image:do_image_complete"
do_install_append() {
    mkdir -p ${D}${base_prefix}/environment-setup.d
    install -m 0755 ${WORKDIR}/bash_tab_completion.sh ${D}${base_prefix}/environment-setup.d
    install ${WORKDIR}/environment-appsdk-native ${D}${base_prefix}/

    install -m 0755 ${RECIPE_SYSROOT}${bindir_native}/crossscripts/qemuwrapper \
        ${D}${bindir}/crossscripts

    install -d ${D}${datadir}/genimage/data/initramfs
    if [ -L ${DEPLOY_DIR_IMAGE}/${INITRAMFS_IMAGE}-${MACHINE}.${INITRAMFS_FSTYPES} ];then
        cp -f ${DEPLOY_DIR_IMAGE}/${INITRAMFS_IMAGE}-${MACHINE}.${INITRAMFS_FSTYPES} \
            ${D}${datadir}/genimage/data/initramfs/
    fi

    install -d ${D}${base_bindir}
    for app in genimage geninitramfs gencontainer genyaml exampleyamls; do
        install -m 0755 ${D}${bindir}/$app ${D}${base_bindir}/$app
        create_wrapper ${D}${bindir}/$app PATH='$(dirname `readlink -fn $0`):$PATH'
    done
}

inherit qemuboot
do_compile[postfuncs] += "do_write_qemuboot_conf_for_genimage"
python do_write_qemuboot_conf_for_genimage() {
    localdata = bb.data.createCopy(d)
    destdir = localdata.expand("${WORKDIR}")
    localdata.setVar('IMGDEPLOYDIR', destdir)
    localdata.setVar('IMAGE_NAME', 'qemuboot_template')
    localdata.setVar('IMAGE_LINK_NAME', 'qemuboot_template')
    if localdata.getVar('MACHINE') == 'bcm-2xxx-rpi4':
        localdata.appendVar('QB_OPT_APPEND', ' -bios @DEPLOYDIR@/qemu-u-boot-bcm-2xxx-rpi4.bin')
    localdata.setVar('QB_MEM', '-m 512')

    bb.build.exec_func('do_write_qemuboot_conf', localdata)
}

do_install[postfuncs] += "copy_qemu_data"
copy_qemu_data() {
    install -d ${D}${datadir}/qemu_data
    if [ -e ${DEPLOY_DIR_IMAGE}/qemu-u-boot-bcm-2xxx-rpi4.bin ]; then
        cp -f ${DEPLOY_DIR_IMAGE}/qemu-u-boot-bcm-2xxx-rpi4.bin ${D}${datadir}/qemu_data/
    fi
    if [ -e ${DEPLOY_DIR_IMAGE}/ovmf.qcow2 ]; then
        cp -f ${DEPLOY_DIR_IMAGE}/ovmf.qcow2 ${D}${datadir}/qemu_data/
    fi

    sed -e '/^staging_bindir_native =/d' \
        -e '/^staging_dir_host =/d' \
        -e '/^staging_dir_native = /d' \
        -e '/^kernel_imagetype =/d' \
        -e 's/^deploy_dir_image =.*$/deploy_dir_image = @DEPLOYDIR@/' \
        -e 's/^image_link_name =.*$/image_link_name = @IMAGE_LINK_NAME@/' \
        -e 's/^image_name =.*$/image_name = @IMAGE_NAME@/' \
        -e 's/^qb_default_fstype =.*$/qb_default_fstype = wic/' \
            ${WORKDIR}/qemuboot_template.qemuboot.conf > \
                ${D}${datadir}/qemu_data/qemuboot.conf.in
}

do_install[nostamp] = "1"

SYSROOT_DIRS_NATIVE += "${base_prefix}/environment-setup.d ${base_prefix}/"

python __anonymous () {
    override = d.getVar('OVERRIDE')
    machine = d.getVar('MACHINE')
    if machine == 'bcm-2xxx-rpi4':
        d.appendVar('OVERRIDES', ':{0}:aarch64'.format(machine))
        if not d.getVar('PACKAGE_FEED_ARCHS'):
            d.setVar('PACKAGE_FEED_ARCHS', 'cortexa72 bcm_2xxx_rpi4 noarch')
        d.appendVarFlag('do_install', 'depends', ' u-boot:do_deploy')
    elif machine == 'intel-x86-64':
        d.appendVar('OVERRIDES', ':{0}:x86-64'.format(machine))
        if not d.getVar('PACKAGE_FEED_ARCHS'):
            d.setVar('PACKAGE_FEED_ARCHS', 'corei7_64 intel_x86_64 noarch')
        d.appendVarFlag('do_install', 'depends', ' ovmf:do_deploy')

    for dep in d.getVar('RPMS_DEPENDS').split():
        d.appendVarFlag('do_populate_sysroot', 'depends', ' ' + dep)

    if not d.getVar('PACKAGE_FEED_URIS') or not d.getVar('PACKAGE_FEED_BASE_PATHS'):
        d.setVar('PACKAGE_FEED_URIS', 'https://distro.windriver.com/release/wrlinux/linux-cd/base')
        d.setVar('PACKAGE_FEED_BASE_PATHS', 'WRLinux-CD-Images/intel-x86-64/repos/rpm')

    if d.getVar('PACKAGE_FEED_URIS') and d.getVar('PACKAGE_FEED_BASE_PATHS'):
        remote_uris = get_remote_uris(d.getVar('PACKAGE_FEED_URIS') or "",
                                      d.getVar('PACKAGE_FEED_BASE_PATHS') or "",
                                      d.getVar('PACKAGE_FEED_ARCHS'))

    d.setVar("DEFAULT_PACKAGE_FEED", remote_uris)

    local_repos = get_remote_uris('file://%s' % (d.getVar('DEPLOY_DIR')),
                                  'rpm',
                                  d.getVar('PACKAGE_FEED_ARCHS'))
    d.setVar("DEFAULT_LOCAL_PACKAGE_FEED", local_repos)
}

EXCLUDE_FROM_WORLD = "1"
