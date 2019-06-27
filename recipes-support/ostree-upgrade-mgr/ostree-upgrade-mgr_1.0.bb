SUMMARY = "pulsar upgrade config manager"
DESCRIPTION = "Example of how to run some postinstall and postrm \
operations to complete the pulsar upgrade"
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

S = "${WORKDIR}"

def get_arch_setting_ostree_mgr(bb, d):
    if d.getVar('TRANSLATED_TARGET_ARCH') in [ 'x86-64', 'i686' ]:
        return "x86_64"
    else:
        return "arm"

ARCH_OSTREE_MGR_SETTING = "${@get_arch_setting_ostree_mgr(bb, d)}"

SRC_URI = "file://COPYING \
           file://ostree_upgrade_${ARCH_OSTREE_MGR_SETTING}.sh \
	   file://ostree_reset.sh \
          "

FILES_${PN} += "/usr/bin/ostree_upgrade.sh \
	/usr/bin/ostree_reset.sh \
	"

do_install() {
	install -d ${D}/usr/bin
	install -m 0755 ${S}/ostree_upgrade_${ARCH_OSTREE_MGR_SETTING}.sh ${D}/usr/bin/ostree_upgrade.sh
	install -m 0755 ${S}/ostree_reset.sh ${D}/usr/bin/ostree_reset.sh
}

DEPENDS += "watchdog"
