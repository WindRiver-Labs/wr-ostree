SUMMARY = "Full image create script"
DESCRIPTION = "Provide a tools to create full image."
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

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
"

# Required by do_rootfs's intercept_scripts in sdk
RDEPENDS_${PN} += "nativesdk-gdk-pixbuf \
                   nativesdk-kmod \
"

SRC_URI = "\
           file://COPYING \
           file://crossscripts/depmodwrapper \
           file://crossscript_wrapper.in \
           file://add_path.sh \
           file://genimage/__init__.py \
           file://genimage/utils.py \
           file://genimage/constant.py.in \
           file://genimage/package_manager.py \
           file://genimage/rootfs.py \
           file://genimage/image.py \
           file://genimage/container.py \
           file://genimage/data/pre_rootfs/create_merged_usr_symlinks.sh \
           file://genimage/data/post_rootfs/add_gpg_key.sh \
           file://genimage/scripts/run.do_image_ostree \
           file://genimage/scripts/run.do_image_otaimg \
           file://genimage/scripts/run.do_image_wic \
           file://METADATA.in \
           file://README.md \
           file://setup.py \
"

S = "${WORKDIR}/sources"

inherit nativesdk setuptools3

do_unpack[vardeps] += "MACHINE PACKAGE_FEED_BASE_PATHS PACKAGE_FEED_ARCHS PACKAGE_FEED_URIS"
do_unpack_append() {
    bb.build.exec_func('do_create_cross_cmd_wrapper', d)
    bb.build.exec_func('do_write_py_template', d)
    bb.build.exec_func('do_copy_src', d)
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

CROSS_CMDS ?= " \
    /usr/bin/shlibsign \
    /usr/bin/glib-compile-schemas \
"
python do_create_cross_cmd_wrapper () {
    # cmd_wrapper.in -> shlibsign or ...
    cross_cmds = (d.getVar("CROSS_CMDS") or "").split()
    dest = os.path.join(d.getVar("WORKDIR"), "crossscripts")
    wrapper_template = os.path.join(d.getVar("WORKDIR"),"crossscript_wrapper.in")
    with open(wrapper_template, "r") as template:
        cmd_content = template.read()
        for cmd in cross_cmds:
            cmd_name = os.path.basename(cmd)
            with open(os.path.join(dest, cmd_name), "w") as cmd_f:
                cmd_f.write(cmd_content.replace("@COMMAND@", cmd))
}


do_install_append() {
	install -d ${D}${bindir}/crossscripts
	install -m 0755 ${WORKDIR}/crossscripts/* ${D}${bindir}/crossscripts
	install -d ${D}${datadir}/genimage/
	cp -rf ${WORKDIR}/genimage/data ${D}${datadir}/genimage/
	cp -rf ${WORKDIR}/genimage/scripts ${D}${datadir}/genimage/
	mkdir -p ${D}${SDKPATHNATIVE}/environment-setup.d
	install -m 0755 ${WORKDIR}/add_path.sh ${D}${SDKPATHNATIVE}/environment-setup.d
	install -d ${D}${datadir}/genimage/rpm_keys/
	cp ${OSTREE_GPGDIR}/RPM-GPG-PRIVKEY-${OSTREE_GPGID} ${D}${datadir}/genimage/rpm_keys/

	install -d ${D}${datadir}/genimage/data/wic/
	cp -f ${LAYER_PATH_ostree-layer}/wic/ostree-*.wks.in ${D}${datadir}/genimage/data/wic/

}

python __anonymous () {
    remote_uris = get_remote_uris(d.getVar('PACKAGE_FEED_URIS') or "",
                                  d.getVar('PACKAGE_FEED_BASE_PATHS') or "",
                                  d.getVar('PACKAGE_FEED_ARCHS'))
    d.setVar("DEFAULT_PACKAGE_FEED", remote_uris)
}

FILES_${PN} = "${SDKPATHNATIVE}"
