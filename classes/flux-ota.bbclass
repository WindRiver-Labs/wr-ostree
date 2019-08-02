IMAGE_INSTALL_append = " ostree os-release"
IMAGE_CLASSES += "image_types_ostree image_types_ota"
IMAGE_FSTYPES += "ostreepush otaimg "

inherit image_types_ostree image_types_ota

IMAGE_TYPEDEP_wic += "otaimg"

WKS_FILE_DEPENDS = "mtools-native dosfstools-native e2fsprogs-native parted-native"
