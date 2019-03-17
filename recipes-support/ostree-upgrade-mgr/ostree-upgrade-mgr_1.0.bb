SUMMARY = "pulsar upgrade config manager"
DESCRIPTION = "Example of how to run some postinstall and postrm \
operations to complete the pulsar upgrade"
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

S = "${WORKDIR}"

SRC_URI = "file://COPYING \
           file://ostree_upgrade_${TARGET_ARCH}.sh \
          "

FILES_${PN} += "/usr/bin/ostree_upgrade.sh \
               "

do_install() {
	install -d ${D}/usr/bin
	if [ "${TARGET_ARCH}" = "x86_64" ]; then
		install -m 0755 ${S}/ostree_upgrade_${TARGET_ARCH}.sh ${D}/usr/bin/ostree_upgrade.sh
	fi
        if [ "${TARGET_ARCH}" = "arm" ]; then
                install -m 0755 ${S}/ostree_upgrade_${TARGET_ARCH}.sh ${D}/usr/bin/ostree_upgrade.sh
        fi
}

DEPENDS += "watchdog"
