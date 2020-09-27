include genimage.inc

RDEPENDS_${PN} = "nativesdk-dnf \
                  nativesdk-rpm \
                  nativesdk-createrepo-c \
                  nativesdk-dosfstools \
                  nativesdk-syslinux \
                  nativesdk-mtools \
                  nativesdk-gptfdisk \
                  nativesdk-wic \
                  nativesdk-gnupg \
                  nativesdk-gnupg-gpg \
                  nativesdk-ostree \
                  nativesdk-python3-pyyaml \
                  nativesdk-shadow \
                  nativesdk-coreutils \
                  nativesdk-cpio \
                  nativesdk-gzip \
                  nativesdk-u-boot-mkimage \
                  nativesdk-pbzip2 \
                  nativesdk-ca-certificates \
                  nativesdk-glib-networking \
                  nativesdk-kmod \
                  nativesdk-wget \
                  nativesdk-sloci-image \
                  nativesdk-umoci \
                  nativesdk-skopeo \
                  nativesdk-python3-texttable \
                  nativesdk-python3-argcomplete \
                  nativesdk-python3-pykwalify \
"

# Required by do_rootfs's intercept_scripts in sdk
RDEPENDS_${PN} += "nativesdk-gdk-pixbuf \
                   nativesdk-kmod \
"

SRC_URI += "\
           file://crossscripts/depmodwrapper \
           file://crossscript_wrapper.in \
           file://add_path.sh \
           file://bash_tab_completion.sh \
"

inherit nativesdk

do_unpack_append() {
    bb.build.exec_func('do_create_cross_cmd_wrapper', d)
}

CROSS_CMDS ?= " \
    /usr/bin/shlibsign \
    /usr/bin/glib-compile-schemas \
    /usr/bin/gconftool-2 \
"

QEMU_ARGS[gconftool-2] = "-E GCONF_BACKEND_DIR=$D/usr/lib/GConf/2"

python do_create_cross_cmd_wrapper () {
    # cmd_wrapper.in -> shlibsign or ...
    cross_cmds = (d.getVar("CROSS_CMDS") or "").split()
    dest = os.path.join(d.getVar("WORKDIR"), "crossscripts")
    wrapper_template = os.path.join(d.getVar("WORKDIR"),"crossscript_wrapper.in")
    with open(wrapper_template, "r") as template:
        cmd_content = template.read()
        for cmd in cross_cmds:
            cmd_name = os.path.basename(cmd)
            qemuargs = d.getVarFlag('QEMU_ARGS', cmd_name) or ""
            with open(os.path.join(dest, cmd_name), "w") as cmd_f:
                content = cmd_content.replace("@COMMAND@", cmd)
                content = content.replace("@QEMU_ARGS@", qemuargs)
                cmd_f.write(content)
}

do_install_append() {
	install -d ${D}${bindir}/crossscripts
	install -m 0755 ${WORKDIR}/crossscripts/* ${D}${bindir}/crossscripts

	mkdir -p ${D}${SDKPATHNATIVE}/environment-setup.d
	install -m 0755 ${WORKDIR}/add_path.sh ${D}${SDKPATHNATIVE}/environment-setup.d
	install -m 0755 ${WORKDIR}/bash_tab_completion.sh ${D}${SDKPATHNATIVE}/environment-setup.d
}

FILES_${PN} = "${SDKPATHNATIVE}"

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

    remote_uris = get_remote_uris(d.getVar('PACKAGE_FEED_URIS') or "",
                                  d.getVar('PACKAGE_FEED_BASE_PATHS') or "",
                                  d.getVar('PACKAGE_FEED_ARCHS'))
    d.setVar("DEFAULT_PACKAGE_FEED", remote_uris)
}
