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
"

# Required by do_rootfs's intercept_scripts in sdk
RDEPENDS_${PN} += "nativesdk-gdk-pixbuf \
                   nativesdk-kmod \
"

SRC_URI = "\
           file://COPYING \
           file://create_full_image.sh \
           file://_create_full_image_h.sh \
           file://depmodwrapper \
           file://add_path.sh \
           file://create_full_image/__init__.py \
           file://create_full_image/utils.py.in \
           file://create_full_image/package_manager.py \
           file://create_full_image/rootfs.py \
           file://create_full_image/image.py \
           file://create_full_image/container.py \
           file://create_full_image/data/pre_rootfs/create_merged_usr_symlinks.sh \
           file://METADATA.in \
           file://README.md \
           file://setup.py \
"

S = "${WORKDIR}/sources"

inherit nativesdk setuptools3

do_unpack_append() {
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

do_copy_src() {
    install -m 0755 ${WORKDIR}/create_full_image.sh ${S}/
    install -m 0755 ${WORKDIR}/_create_full_image_h.sh ${S}/
    install -m 0644 ${WORKDIR}/COPYING ${S}/
    install -d ${S}/create_full_image
    install -m 0644 ${WORKDIR}/create_full_image/*.py ${S}/create_full_image

    sed -e "s/@MACHINE@/${MACHINE}/g" \
        -e "s#@DEFAULT_PACKAGE_FEED@#${DEFAULT_PACKAGE_FEED}#g" \
	    ${WORKDIR}/create_full_image/utils.py.in > ${S}/create_full_image/utils.py
    chmod 0644 ${S}/create_full_image/utils.py

    install -m 0644 ${WORKDIR}/METADATA.in ${S}
    install -m 0644 ${WORKDIR}/README.md ${S}
    install -m 0644 ${WORKDIR}/setup.py ${S}
}


do_compile_append() {
	sed -i "/remote repo arg/a export RPM_SIGN_PACKAGES=\"${RPM_SIGN_PACKAGES}\"" ${S}/_create_full_image_h.sh
	sed -i "/remote repo arg/a export PACKAGE_FEED_SIGN=\"${PACKAGE_FEED_SIGN}\"" ${S}/_create_full_image_h.sh
	sed -i "/remote repo arg/a export PACKAGE_FEED_ARCHS=\"${PACKAGE_FEED_ARCHS}\"" ${S}/_create_full_image_h.sh
	sed -i "/remote repo arg/a export PACKAGE_FEED_BASE_PATHS=\"${PACKAGE_FEED_BASE_PATHS}\"" ${S}/_create_full_image_h.sh
	sed -i "/remote repo arg/a export PACKAGE_FEED_URIS=\"${PACKAGE_FEED_URIS}\"" ${S}/_create_full_image_h.sh
}

do_install_append() {
	install -d ${D}${bindir}/crossscripts
	install -m 0755 ${S}/create_full_image.sh ${D}${bindir}/
	install -m 0755 ${S}/_create_full_image_h.sh ${D}${bindir}/
	install -m 0755 ${WORKDIR}/depmodwrapper ${D}${bindir}/crossscripts
	install -d ${D}${datadir}/create_full_image/
	cp -rf ${WORKDIR}/create_full_image/data ${D}${datadir}/create_full_image/
	mkdir -p ${D}${SDKPATHNATIVE}/environment-setup.d
	install -m 0755 ${WORKDIR}/add_path.sh ${D}${SDKPATHNATIVE}/environment-setup.d
	install -d ${D}${datadir}/create_full_image/rpm_keys/
	cp ${OSTREE_GPGDIR}/RPM-GPG-PRIVKEY-${OSTREE_GPGID} ${D}${datadir}/create_full_image/rpm_keys/
}

python __anonymous () {
    remote_uris = get_remote_uris(d.getVar('PACKAGE_FEED_URIS') or "",
                                  d.getVar('PACKAGE_FEED_BASE_PATHS') or "",
                                  d.getVar('PACKAGE_FEED_ARCHS'))
    d.setVar("DEFAULT_PACKAGE_FEED", remote_uris)
}

FILES_${PN} = "${SDKPATHNATIVE}"
