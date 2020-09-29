SUMMARY = "Full image create script"
DESCRIPTION = "Provide a tools to create full image."
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

SRC_URI = "\
           file://COPYING \
           file://bash_tab_completion.sh \
           file://crossscripts/depmodwrapper \
           file://crossscript_wrapper.in \
           file://genimage/__init__.py \
           file://genimage/genimage.py \
           file://genimage/genyaml.py \
           file://genimage/genXXX.py \
           file://genimage/exampleyamls.py \
           file://genimage/geninitramfs.py \
           file://genimage/gencontainer.py \
           file://genimage/utils.py \
           file://genimage/constant.py.in \
           file://genimage/package_manager.py \
           file://genimage/rootfs.py \
           file://genimage/image.py \
           file://genimage/container.py \
           file://genimage/data/pre_rootfs/create_merged_usr_symlinks.sh \
           file://genimage/data/pre_rootfs/update_pkgdata.sh \
           file://genimage/data/post_rootfs/add_gpg_key.sh \
           file://genimage/data/post_rootfs/update_boot_scr.sh \
           file://genimage/data/post_rootfs/update_grub_cfg.sh \
           file://genimage/data/post_rootfs/set_systemd_default_target.sh \
           file://genimage/data/post_rootfs/run.ssh_allow_empty_password \
           file://genimage/data/post_rootfs/run.ssh_allow_root_login \
           file://genimage/data/yaml_example/feature/vboxguestdrivers.yaml \
           file://genimage/data/yaml_example/feature/xfce_desktop.yaml \
           file://genimage/data/yaml_example/feature/set_root_password.yaml \
           file://genimage/data/yaml_example/feature/package_management.yaml \
           file://genimage/data/yaml_example/feature/debug-tweaks.yaml \
           file://genimage/data/yaml_example/images/core-image-minimal.yaml \
           file://genimage/data/yaml_example/images/core-image-sato.yaml \
           file://genimage/data/yaml_example/images/wrlinux-image-small.yaml \
           file://genimage/data/yaml_example/images/container-base.yaml \
           file://genimage/data/yaml_example/images/initramfs-ostree-image.yaml \
           file://genimage/data/yaml_example/machine/intel-x86-64.yaml \
           file://genimage/data/yaml_example/machine/bcm-2xxx-rpi4.yaml \
           file://genimage/data/pykwalify/genimage-schema.yaml \
           file://genimage/data/pykwalify/gencontainer-schema.yaml \
           file://genimage/data/pykwalify/geninitramfs-schema.yaml \
           file://genimage/data/pykwalify/partial-schemas.yaml \
           file://genimage/scripts/run.do_image_ostree \
           file://genimage/scripts/run.do_image_otaimg \
           file://genimage/scripts/run.do_image_wic \
           file://genimage/scripts/run.do_image_oci \
           file://genimage/doc/wic_bcm-2xxx-rpi4.README.md.in \
           file://genimage/doc/ustart_bcm-2xxx-rpi4.README.md.in \
           file://genimage/doc/wic_intel-x86-64.README.md.in \
           file://genimage/doc/ustart_intel-x86-64.README.md.in \
           file://genimage/doc/container.README.md.in \
           file://METADATA.in \
           file://README.md \
           file://setup.py \
"

S = "${WORKDIR}/sources"

inherit setuptools3

inherit image-oci

do_unpack[vardeps] += "MACHINE PACKAGE_FEED_BASE_PATHS PACKAGE_FEED_ARCHS PACKAGE_FEED_URIS"
do_unpack_append() {
    bb.build.exec_func('do_write_py_template', d)
    bb.build.exec_func('do_copy_src', d)
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

# Refer insert_feeds_uris in oe-core/meta/lib/oe/package_manager.py
# https://www.yoctoproject.org/docs/2.2/ref-manual/ref-manual.html#var-PACKAGE_FEED_ARCHS
def get_remote_uris(feed_uris, feed_base_paths, feed_archs):
    def _construct_uris(uris, base_paths):
        """
        Construct URIs based on the following pattern: uri/base_path where 'uri'
        and 'base_path' correspond to each element of the corresponding array
        argument leading to len(uris) x len(base_paths) elements on the returned
        array
        """
        def _append(arr1, arr2, sep='/'):
            res = []
            narr1 = [a.rstrip(sep) for a in arr1]
            narr2 = [a.rstrip(sep).lstrip(sep) for a in arr2]
            for a1 in narr1:
                if arr2:
                    for a2 in narr2:
                        res.append("%s%s%s" % (a1, sep, a2))
                else:
                    res.append(a1)
            return res
        return _append(uris, base_paths)

    remote_uris = []
    for uri in _construct_uris(feed_uris.split(), feed_base_paths.split()):
        if feed_archs is not None:
            for arch in feed_archs.split():
                repo_uri = uri + "/" + arch
                remote_uris.append(repo_uri)
    return ' '.join(remote_uris)

DEFAULT_PACKAGE_FEED = ""

IMAGE_BOOT_FILES ??= ""

do_copy_src() {
    install -m 0644 ${WORKDIR}/COPYING ${S}/
    install -d ${S}/genimage
    install -m 0644 ${WORKDIR}/genimage/*.py ${S}/genimage

    install -m 0644 ${WORKDIR}/METADATA.in ${S}
    install -m 0644 ${WORKDIR}/README.md ${S}
    install -m 0644 ${WORKDIR}/setup.py ${S}
}

python do_write_py_template () {
    # constant.py.in -> constant.py and expand variables
    py_templates = [os.path.join(d.getVar("WORKDIR"),"genimage","constant.py.in")]
    for py_t in py_templates:
        body = "null"
        with open(py_t, "r") as pytf:
            body = pytf.read()
            d.setVar("_PY_TEMPLATE", body)
            body = d.getVar("_PY_TEMPLATE")
        py = os.path.splitext(py_t)[0]
        with open(py, "w") as pyf:
            pyf.write(body)
}

do_install_append() {
	install -d ${D}${datadir}/genimage/
	cp -rf ${WORKDIR}/genimage/data ${D}${datadir}/genimage/
	cp -rf ${WORKDIR}/genimage/scripts ${D}${datadir}/genimage/
	cp -rf ${WORKDIR}/genimage/doc ${D}${datadir}/genimage/
	install -d ${D}${datadir}/genimage/rpm_keys/
	cp ${OSTREE_GPGDIR}/RPM-GPG-PRIVKEY-${OSTREE_GPGID} ${D}${datadir}/genimage/rpm_keys/

	install -d ${D}${datadir}/genimage/data/wic/
	cp -f ${LAYER_PATH_ostree-layer}/wic/ostree-*.wks.in ${D}${datadir}/genimage/data/wic/

	install -d ${D}${bindir}/crossscripts
	install -m 0755 ${WORKDIR}/crossscripts/* ${D}${bindir}/crossscripts
}
