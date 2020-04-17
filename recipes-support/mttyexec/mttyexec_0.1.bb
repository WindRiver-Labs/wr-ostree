SUMMARY = "Service funtion to multiplex one or more serial ports and tty console devices"
HOMEPAGE = "https://github.com/WindRiver-Labs/wr-ostree"
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://mttyexec.c;beginline=5;endline=20;md5=9603747e15893a3537fe4e17873b4d41"

SRC_URI = "file://COPYING \
	file://mttyexec.c \
	file://Makefile"


S = "${WORKDIR}"

do_install() {
	oe_runmake DEST=${D}${bindir} install
}
