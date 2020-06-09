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
"

SRC_URI = "\
           file://COPYING \
           file://create_full_image.sh \
           file://_create_full_image_h.sh \
           file://create_full_image/__init__.py \
           file://create_full_image/utils.py \
           file://METADATA.in \
           file://README.md \
           file://setup.py \
"

S = "${WORKDIR}/sources"

inherit nativesdk setuptools3

do_unpack_append() {
    bb.build.exec_func('do_copy_src', d)
}

do_copy_src() {
    install -m 0755 ${WORKDIR}/create_full_image.sh ${S}/
    install -m 0755 ${WORKDIR}/_create_full_image_h.sh ${S}/
    install -m 0644 ${WORKDIR}/COPYING ${S}/
    install -d ${S}/create_full_image
    install -m 0644 ${WORKDIR}/create_full_image/*.py ${S}/create_full_image
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
	install -d ${D}${bindir}
	install -m 0755 ${S}/create_full_image.sh ${D}${bindir}/
	install -m 0755 ${S}/_create_full_image_h.sh ${D}${bindir}/
}
