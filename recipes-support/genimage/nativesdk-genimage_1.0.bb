#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
include genimage.inc

RDEPENDS_${PN} = "nativesdk-dnf \
                  nativesdk-rpm \
                  nativesdk-createrepo-c \
                  nativesdk-dosfstools \
                  nativesdk-syslinux \
                  nativesdk-mtools \
                  nativesdk-gptfdisk \
                  nativesdk-wic \
                  nativesdk-gnupg \
                  nativesdk-gnupg-gpg \
                  nativesdk-ostree \
                  nativesdk-python3-pyyaml \
                  nativesdk-shadow \
                  nativesdk-coreutils \
                  nativesdk-cpio \
                  nativesdk-gzip \
                  nativesdk-u-boot-mkimage \
                  nativesdk-pbzip2 \
                  nativesdk-ca-certificates \
                  nativesdk-glib-networking \
                  nativesdk-kmod \
                  nativesdk-wget \
                  nativesdk-sloci-image \
                  nativesdk-umoci \
                  nativesdk-skopeo \
                  nativesdk-python3-texttable \
                  nativesdk-python3-argcomplete \
                  nativesdk-python3-pykwalify \
                  nativesdk-bmap-tools \
                  nativesdk-util-linux-uuidgen \
                  nativesdk-perl \
"

# Required by do_rootfs's intercept_scripts in sdk
RDEPENDS_${PN} += "nativesdk-gdk-pixbuf \
                   nativesdk-gtk+3 \
                   nativesdk-kmod \
"

SRC_URI += "\
           file://add_path.sh \
"

inherit nativesdk

do_install_append() {
	mkdir -p ${D}${SDKPATHNATIVE}/environment-setup.d
	install -m 0755 ${WORKDIR}/add_path.sh ${D}${SDKPATHNATIVE}/environment-setup.d
	install -m 0755 ${WORKDIR}/bash_tab_completion.sh ${D}${SDKPATHNATIVE}/environment-setup.d
}

FILES_${PN} = "${SDKPATHNATIVE}"

python __anonymous () {
    override = d.getVar('OVERRIDE')
    machine = d.getVar('MACHINE')
    img_pkgtype = d.getVar('IMAGE_PKGTYPE')
    if machine == 'bcm-2xxx-rpi4':
        d.appendVar('OVERRIDES', ':{0}:aarch64'.format(machine))
        if not d.getVar('PACKAGE_FEED_ARCHS'):
            if img_pkgtype == 'rpm':
                d.setVar('PACKAGE_FEED_ARCHS', 'cortexa72 bcm_2xxx_rpi4 noarch')
            elif img_pkgtype == 'deb':
                d.setVar('PACKAGE_FEED_ARCHS', 'cortexa72 bcm_2xxx_rpi4 all')
    elif machine == 'intel-x86-64':
        d.appendVar('OVERRIDES', ':{0}:x86-64'.format(machine))
        if not d.getVar('PACKAGE_FEED_ARCHS'):
            if img_pkgtype == 'rpm':
                d.setVar('PACKAGE_FEED_ARCHS', 'corei7_64 intel_x86_64 noarch')
            elif img_pkgtype == 'deb':
                d.setVar('PACKAGE_FEED_ARCHS', 'corei7-64 intel_x86_64 all')

    if not d.getVar('PACKAGE_FEED_URIS') or not d.getVar('PACKAGE_FEED_BASE_PATHS'):
        d.setVar('PACKAGE_FEED_URIS', 'https://distro.windriver.com/release/wrlinux/linux-cd/base')
        d.setVar('PACKAGE_FEED_BASE_PATHS', 'WRLinux-CD-Images/intel-x86-64/repos/rpm')

    remote_uris = get_remote_uris(d.getVar('PACKAGE_FEED_URIS') or "",
                                  d.getVar('PACKAGE_FEED_BASE_PATHS') or "",
                                  d.getVar('PACKAGE_FEED_ARCHS'))
    d.setVar("DEFAULT_PACKAGE_FEED", remote_uris)

    d.setVar("DEFAULT_LOCAL_PACKAGE_FEED", "")
}
