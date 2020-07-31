SUMMARY = "OSTree Network/Disk Image deployment tool"
DESCRIPTION = "Provide a nativesdk command will build a small boot image \
which can be used for deployment with OSTree"
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

S = "${WORKDIR}"

RDEPENDS_${PN} += " \
    nativesdk-bash \
    nativesdk-perl \
    nativesdk-ostree \
    nativesdk-wic \
"

SRC_URI = "file://COPYING \
           file://bootfs_wrapper.sh \
          "

FILES_${PN} += "${datadir}/bootfs \
	"

do_install() {
    install -d ${D}${datadir}/bootfs/scripts/
    install -m 0755 ${LAYER_PATH_ostree-layer}/scripts/bootfs.sh ${D}${datadir}/bootfs/scripts/

    install -d ${D}${datadir}/bootfs/boot_keys
    install -m 0644 ${OSTREE_GRUB_PW_FILE} ${D}${datadir}/bootfs/boot_keys/ostree_grub_pw
    cp -rf  ${BOOT_KEYS_DIR}/* ${D}${datadir}/bootfs/boot_keys/

    install -d ${D}${bindir}
    install -m 0755 ${S}/bootfs_wrapper.sh ${D}${bindir}/bootfs.sh
}

inherit nativesdk
