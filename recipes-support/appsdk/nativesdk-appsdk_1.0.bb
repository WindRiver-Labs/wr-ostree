include appsdk.inc

RDEPENDS_${PN} = " \
    nativesdk-genimage \
    nativesdk-python3-argcomplete \
"

inherit nativesdk

FILES_${PN} = "${SDKPATHNATIVE}"
