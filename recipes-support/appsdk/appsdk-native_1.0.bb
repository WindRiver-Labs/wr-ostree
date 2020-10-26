include appsdk.inc

SRC_URI += " \
    file://0001-do-not-support-subcommand-gensdk.patch \
"
DEPENDS = " \
    genimage-native \
    python3-argcomplete-native \
"

inherit native

do_install_append() {
	install -d ${D}${base_bindir}
	install -m 0755 ${D}${bindir}/appsdk ${D}${base_bindir}/appsdk
	create_wrapper ${D}${bindir}/appsdk PATH='$(dirname `readlink -fn $0`):$PATH'
}

do_install[nostamp] = "1"
