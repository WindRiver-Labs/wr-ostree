SUMMARY = "Application SDK Management Tool for CBAS"
DESCRIPTION = "Application SDK Management Tool for CBAS."
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

RDEPENDS_${PN} = "nativesdk-genimage"

SRC_URI = "\
           file://COPYING \
           file://appsdk/__init__.py \
           file://appsdk/appsdk.py \
           file://README.md \
           file://setup.py \
"

inherit nativesdk setuptools3

do_unpack_append() {
    bb.build.exec_func('do_copy_src', d)
}

do_copy_src() {
    install -m 0644 ${WORKDIR}/COPYING ${S}/
    install -d ${S}/appsdk
    install -m 0644 ${WORKDIR}/appsdk/*.py ${S}/appsdk

    install -m 0644 ${WORKDIR}/README.md ${S}
    install -m 0644 ${WORKDIR}/setup.py ${S}
}

FILES_${PN} = "${SDKPATHNATIVE}"
