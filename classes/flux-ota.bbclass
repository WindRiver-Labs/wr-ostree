IMAGE_INSTALL_append = " ostree os-release"
IMAGE_CLASSES += "image_types_ostree image_types_ota"
IMAGE_FSTYPES += "ostreepush otaimg "

inherit image_types_ostree image_types_ota

IMAGE_TYPEDEP_wic += "otaimg"

WKS_FILE = "${@bb.utils.contains('DISTRO_FEATURES', 'luks', '${IMAGE_BASENAME}-${MACHINE}-luks.wks', '${IMAGE_BASENAME}-${MACHINE}.wks', d)}"
WKS_FILE_DEPENDS = "mtools-native dosfstools-native e2fsprogs-native parted-native"
