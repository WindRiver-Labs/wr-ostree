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
           file://bootfs_common.env \
          "

FILES_${PN} += "${datadir}/bootfs \
	"

do_install() {
    install -d ${D}${datadir}/bootfs/scripts/
    install -m 0755 ${LAYER_PATH_ostree-layer}/scripts/bootfs.sh ${D}${datadir}/bootfs/scripts/

    install -m 0644 ${S}/bootfs_common.env ${D}${datadir}/bootfs/

    sed -i -e "s:%OSTREE_USE_AB%:${OSTREE_USE_AB}:g" \
           -e "s#%OSTREE_REMOTE_URL%#${OSTREE_REMOTE_URL}#g" \
           -e "s:%OSTREE_FLUX_PART%:${OSTREE_FLUX_PART}:g" \
           -e "s:%OSTREE_GRUB_USER%:${OSTREE_GRUB_USER}:g" \
           -e "s:%OSTREE_FDISK_BLM%:${OSTREE_FDISK_BLM}:g" \
           -e "s:%OSTREE_FDISK_FSZ%:${OSTREE_FDISK_FSZ}:g" \
           -e "s:%OSTREE_FDISK_BSZ%:${OSTREE_FDISK_BSZ}:g" \
           -e "s:%OSTREE_FDISK_RSZ%:${OSTREE_FDISK_RSZ}:g" \
           -e "s:%OSTREE_FDISK_VSZ%:${OSTREE_FDISK_VSZ}:g" \
           -e "s:%BOOT_GPG_NAME%:${BOOT_GPG_NAME}:g" \
           -e "s:%BOOT_GPG_PASSPHRASE%:${BOOT_GPG_PASSPHRASE}:g" \
       ${D}${datadir}/bootfs/bootfs_common.env

    install -d ${D}${datadir}/bootfs/boot_keys
    install -m 0644 ${OSTREE_GRUB_PW_FILE} ${D}${datadir}/bootfs/boot_keys/ostree_grub_pw
    cp -rf  ${BOOT_KEYS_DIR}/* ${D}${datadir}/bootfs/boot_keys/

    install -d ${D}${bindir}
    install -m 0755 ${S}/bootfs_wrapper.sh ${D}${bindir}/bootfs.sh

    sed -i -e "s#%PACKAGE_FEED_URIS%#${PACKAGE_FEED_URIS}#g" \
           -e "s#%PACKAGE_FEED_BASE_PATHS%#${PACKAGE_FEED_BASE_PATHS}#g" \
       ${D}${bindir}/bootfs.sh

    gpg_path="${GPG_PATH}"
    if [ -z "$gpg_path" ] ; then
        gpg_path="${TMPDIR}/.gnupg"
    fi
    if [ -n "${OSTREE_GPGID}" ] ; then
        FAIL=1
        if [ -f $gpg_path/pubring.gpg ]; then
            cp $gpg_path/pubring.gpg ${D}${datadir}/bootfs/boot_keys/pubring.gpg
            FAIL=0
        fi
        if [ -f $gpg_path/pubring.kbx ]; then
            cp $gpg_path/pubring.kbx ${D}${datadir}/bootfs/boot_keys//pubkbx.gpg
            FAIL=0
        fi
        if $FAIL = 1; then
            bb.fatal "Could not locate the public gpg signing key for OSTree"
        fi
    fi
}

inherit nativesdk
