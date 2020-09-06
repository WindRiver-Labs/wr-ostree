#!/usr/bin/env python3
#
# Copyright (C) 2020 Wind River Systems, Inc.
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

import os
import sys
import subprocess
import argparse
import logging
import shutil
import atexit
import yaml
from collections import OrderedDict
import time
from texttable import Texttable
import glob

from genimage.utils import set_logger
from genimage.utils import get_today
from genimage.utils import show_task_info
import genimage.constant as constant
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_PACKAGES
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_IMAGE
from genimage.constant import DEFAULT_IMAGE_FEATURES
from genimage.constant import OSTREE_INITRD_PACKAGES
from genimage.rootfs import Rootfs
from genimage.container import CreateContainer
from genimage.image import CreateWicImage
from genimage.image import CreateVMImage
from genimage.image import CreateOstreeRepo
from genimage.image import CreateInitramfs
from genimage.image import CreateOstreeOTA
from genimage.image import CreateBootfs
from genimage.genXXX import GenXXX

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser(
            description='Generate images from package feeds for specified machines',
            epilog='Use %(prog)s --help to get help')
        parser.add_argument('-d', '--debug',
            help = "Enable debug output",
            action='store_const', const=logging.DEBUG, dest='loglevel', default=logging.INFO)
        parser.add_argument('-q', '--quiet',
            help = 'Hide all output except error messages',
            action='store_const', const=logging.ERROR, dest='loglevel')

        parser.add_argument('--log-dir',
            default=None,
            dest='logdir',
            help='Specify dir to save debug messages as log.appsdk regardless of the logging level',
            action='store')

    supported_types = [
        'wic',
        'vmdk',
        'vdi',
        'ostree-repo',
        'container',
        'ustart',
        'all',
    ]

    parser.add_argument('-o', '--outdir',
        default=os.getcwd(),
        help='Specify output dir, default is current working directory',
        action='store')
    parser.add_argument('-g', '--gpgpath',
        default=None,
        help='Specify gpg homedir, it overrides \'gpg_path\' in Yaml, default is /tmp/.cbas_gnupg',
        action='store')
    parser.add_argument('-w', '--workdir',
        default=os.getcwd(),
        help='Specify work dir, default is current working directory',
        action='store')
    parser.add_argument('-t', '--type',
        choices=supported_types,
        help='Specify image type, it overrides \'image_type\' in Yaml, default is all',
        action='append')
    parser.add_argument('-n', '--name',
        help='Specify image name, it overrides \'name\' in Yaml',
        action='store')
    parser.add_argument('-u', '--url',
        help='Specify extra urls of rpm package feeds',
        action='append')
    parser.add_argument('-p', '--pkg',
        help='Specify extra package to be installed',
        action='append')
    parser.add_argument('--pkg-external',
        help='Specify extra external package to be installed',
        action='append')
    parser.add_argument("--no-clean",
        help = "Do not cleanup generated rootfs in workdir", action="store_true", default=False)

    parser.add_argument('input',
        help='Input yaml files that the tool can be run against a package feed to generate an image',
        action='store',
        nargs='*')

    return parser


class GenImage(GenXXX):
    """
    * Create the following images in order:
        - ostree repository
        - wic image
        - container image
    """

    def __init__(self, args):
        super(GenImage, self).__init__(args)

        self.workdir = os.path.realpath(os.path.join(self.args.workdir, "workdir"))
        utils.fake_root(workdir=self.workdir)
        utils.mkdirhier(self.workdir)

        self.target_rootfs = None
        self.native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
        self.data_dir = os.path.join(self.native_sysroot, "usr/share/genimage/data")

        os.environ['NO_RECOMMENDATIONS'] = self.data.get('NO_RECOMMENDATIONS', '0')

        # Cleanup all generated rootfs dir by default
        if not self.args.no_clean:
            cmd = "rm -rf {0}/*/rootfs*".format(self.workdir)
            atexit.register(utils.run_cmd_oneshot, cmd=cmd)

        logger.debug("Work Directory: %s" % self.workdir)

    def do_prepare(self):
        gpg_data = self.data["gpg"]
        utils.check_gpg_keys(gpg_data)

    def do_post(self):
        for f in ["qemu-u-boot-bcm-2xxx-rpi4.bin", "ovmf.qcow2"]:
            qemu_data = os.path.join(self.native_sysroot, "usr/share/qemu_data", f)
            if os.path.exists(qemu_data):
                logger.debug("Deploy %s", f)
                cmd = "cp -f {0} {1}".format(qemu_data, self.deploydir)
                utils.run_cmd_oneshot(cmd)

    @show_task_info("Create Rootfs")
    def do_rootfs(self):
        workdir = os.path.join(self.workdir, self.image_name)
        pkg_globs = self.features.get("pkg_globs", None)
        image_linguas = self.features.get("image_linguas", None)
        rootfs = Rootfs(workdir,
                        self.data_dir,
                        self.machine,
                        self.pkg_feeds,
                        self.packages,
                        external_packages=self.external_packages,
                        exclude_packages=self.exclude_packages,
                        remote_pkgdatadir=self.remote_pkgdatadir,
                        image_linguas=image_linguas,
                        pkg_globs=pkg_globs)

        if self.machine == "bcm-2xxx-rpi4":
            os.environ['OSTREE_CONSOLE'] = self.data["ostree"]['OSTREE_CONSOLE']
            script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'update_boot_scr.sh')
            script_cmd = "{0} {1} {2} {3} {4}".format(script_cmd,
                                                      rootfs.target_rootfs,
                                                      self.image_name,
                                                      self.data["ostree"]['ostree_use_ab'],
                                                      self.data["ostree"]['ostree_remote_url'])
            rootfs.add_rootfs_post_scripts(script_cmd)
        elif self.machine == "intel-x86-64":
            os.environ['OSTREE_CONSOLE'] = self.data["ostree"]['OSTREE_CONSOLE']
            script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'update_grub_cfg.sh')
            script_cmd = "{0} {1}".format(script_cmd, rootfs.target_rootfs)
            rootfs.add_rootfs_post_scripts(script_cmd)

        if 'systemd' in self.packages or 'systemd' in self.external_packages:
            script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'set_systemd_default_target.sh')
            if 'packagegroup-core-x11-base' in self.packages:
                script_cmd = "{0} {1} graphical.target".format(script_cmd, rootfs.target_rootfs)
            else:
                script_cmd = "{0} {1} multi-user.target".format(script_cmd, rootfs.target_rootfs)
            rootfs.add_rootfs_post_scripts(script_cmd)

        rootfs.create()

        installed_dict = rootfs.image_list_installed_packages()

        self._save_output_yaml()

        # Generate image manifest
        manifest_name = "{0}/{1}-{2}.manifest".format(self.deploydir, self.image_name, self.machine)
        with open(manifest_name, 'w+') as image_manifest:
            image_manifest.write(utils.format_pkg_list(installed_dict, "ver"))

        self.target_rootfs = rootfs.target_rootfs

        # Copy kernel image, boot files, device tree files to deploy dir
        if self.machine == "intel-x86-64":
            for files in ["boot/bzImage*", "boot/efi/EFI/BOOT/*"]:
                cmd = "cp -rf {0}/{1} {2}".format(self.target_rootfs, files, self.deploydir)
                utils.run_cmd_oneshot(cmd)

                cmd = "ln -snf -r {0} {1}".format(os.path.join(self.deploydir, "bootx64.efi"),
                                                  os.path.join(self.deploydir, "grub-efi-bootx64.efi"))
                utils.run_cmd_oneshot(cmd)

        else:
            cmd = "cp -rf {0}/boot/* {1}".format(self.target_rootfs, self.deploydir)
            utils.run_cmd_oneshot(cmd)

    @show_task_info("Create Initramfs")
    def do_ostree_initramfs(self):
        # If the Initramfs exists, reuse it
        image_name = "initramfs-ostree-image-{0}.cpio.gz".format(self.machine)
        if self.machine == "bcm-2xxx-rpi4":
            image_name += ".u-boot"

        image = os.path.join(self.deploydir, image_name)
        if os.path.exists(os.path.realpath(image)):
            logger.info("Reuse existed Initramfs")
            return

        image_back = os.path.join(self.native_sysroot, "usr/share/genimage/data/initramfs", image_name)
        if not os.path.exists(image_back):
            logger.error("The initramfs does not exist, please call `appsdk geninitramfs' to build it")
            sys.exit(1)

        logger.info("Reuse existed Initramfs of SDK")
        cmd = "cp -f {0} {1}".format(image_back, self.deploydir)
        utils.run_cmd_oneshot(cmd)

    @show_task_info("Create Wic Image")
    def do_image_wic(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ostree_use_ab = self.data["ostree"].get("ostree_use_ab", '1')
        wks_file = utils.get_ostree_wks(ostree_use_ab, self.machine)
        logger.debug("WKS %s", wks_file)
        image_wic = CreateWicImage(
                        image_name = self.image_name,
                        workdir = workdir,
                        machine = self.machine,
                        target_rootfs = self.target_rootfs,
                        deploydir = self.deploydir,
                        wks_file = wks_file)

        env = self.data['wic'].copy()
        env['WORKDIR'] = workdir
        if self.machine == "bcm-2xxx-rpi4":
            env.update({'OSTREE_SD_BOOT_ALIGN':'4',
                        'OSTREE_SD_UBOOT_WIC1':'',
                        'OSTREE_SD_UBOOT_WIC2':'',
                        'OSTREE_SD_UBOOT_WIC3':'',
                        'OSTREE_SD_UBOOT_WIC4':''})
        image_wic.set_wks_in_environ(**env)

        image_wic.create()

    @show_task_info("Create Vmdk Image")
    def do_image_vmdk(self):
        vmdk = CreateVMImage(image_name=self.image_name,
                             machine=self.machine,
                             deploydir=self.deploydir,
                             vm_type="vmdk")
        vmdk.create()

    @show_task_info("Create Vdi Image")
    def do_image_vdi(self):
        vdi = CreateVMImage(image_name=self.image_name,
                            machine=self.machine,
                            deploydir=self.deploydir,
                            vm_type="vdi")
        vdi.create()

    @show_task_info("Create Docker Container")
    def do_image_container(self):
        workdir = os.path.join(self.workdir, self.image_name)
        container = CreateContainer(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        target_rootfs=self.target_rootfs,
                        deploydir=self.deploydir)
        container.create()

    @show_task_info("Create Ostree Repo")
    def do_ostree_repo(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ostree_repo = CreateOstreeRepo(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        target_rootfs=self.target_rootfs,
                        deploydir=self.deploydir,
                        gpg_path=self.data['gpg']['gpg_path'],
                        gpgid=self.data['gpg']['ostree']['gpgid'],
                        gpg_password=self.data['gpg']['ostree']['gpg_password'])

        ostree_repo.create()

        ostree_repo.gen_env(self.data)

    @show_task_info("Create Ostree OTA")
    def do_ostree_ota(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ostree_ota = CreateOstreeOTA(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        deploydir=self.deploydir,
                        ostree_use_ab=self.data["ostree"]['ostree_use_ab'],
                        ostree_osname=self.data["ostree"]['ostree_osname'],
                        ostree_skip_boot_diff=self.data["ostree"]['ostree_skip_boot_diff'],
                        ostree_remote_url=self.data["ostree"]['ostree_remote_url'],
                        gpgid=self.data["gpg"]['ostree']['gpgid'])

        ostree_ota.create()

    @show_task_info("Create Ustart Image")
    def do_ustart_img(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ustart = CreateBootfs(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        deploydir=self.deploydir)
        ustart.create()

    def do_report(self):
        table = Texttable()
        table.set_cols_align(["l", "l"])
        table.set_cols_valign(["t", "t"])
        table.add_rows([["Type", "Name"]])

        image_name = "%s-%s" % (self.image_name, self.machine)
        cmd_format = "ls -gh --time-style=+%%Y %s | awk '{$1=$2=$3=$4=$5=\"\"; print $0}'"

        output = subprocess.check_output("ls {0}.yaml".format(image_name), shell=True, cwd=self.deploydir)
        table.add_row(["Image Yaml File", output.strip()])

        if any(img_type in self.image_type for img_type in ["ostree-repo", "wic", "ustart", "vmdk", "vdi"]):
            output = subprocess.check_output("ls -d  ostree_repo", shell=True, cwd=self.deploydir)
            table.add_row(["Ostree Repo", output.strip()])

        if "wic" in self.image_type:
            cmd_wic = cmd_format % "{0}.wic".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["WIC Image", output.strip()])

            cmd_wic = cmd_format % "{0}.wic.README.md".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["WIC Image Doc", output.strip()])

            cmd_wic = cmd_format % "{0}.qemuboot.conf".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["WIC Image\nQemu Conf", output.strip()])

        if "vdi" in self.image_type:
            cmd_wic = cmd_format % "{0}.wic.vdi".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["VDI Image", output.strip()])

        if "vmdk" in self.image_type:
            cmd_wic = cmd_format % "{0}.wic.vmdk".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["VMDK Image", output.strip()])

        if "ustart" in self.image_type:
            cmd_wic = cmd_format % "{0}.ustart.img.gz".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["Ustart Image", output.strip()])

            cmd_wic = cmd_format % "{0}.ustart.img.gz.README.md".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["Ustart Image Doc", output.strip()])

        if "container" in self.image_type:
            cmd_wic = cmd_format % "{0}.container.tar.bz2".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["Container Image", output.strip()])

            cmd_wic = cmd_format % "{0}.container.tar.bz2.README.md".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["Container Image Doc", output.strip()])

        logger.info("Deploy Directory: %s\n%s", self.deploydir, table.draw())

def _main_run_internal(args):
    create = GenImage(args)
    create.do_prepare()
    create.do_rootfs()
    if create.target_rootfs is None:
        logger.error("Create Target Rootfs Failed")
        sys.exit(1)
    else:
        logger.debug("Create Target Rootfs: %s" % create.target_rootfs)

    create.do_ostree_initramfs()

    # WIC image requires ostress repo
    if any(img_type in create.image_type for img_type in ["ostree-repo", "wic", "ustart", "vmdk", "vdi"]):
        create.do_ostree_repo()

    if "wic" in create.image_type or "vmdk" in create.image_type or "vdi" in create.image_type:
        create.do_ostree_ota()
        create.do_image_wic()
        if "vmdk" in create.image_type:
            create.do_image_vmdk()

        if "vdi" in create.image_type:
            create.do_image_vdi()

    if "container" in create.image_type:
        create.do_image_container()

    if "ustart" in create.image_type:
        create.do_ustart_img()

    create.do_post()
    create.do_report()

def _main_run(args):
    try:
        ret = _main_run_internal(args)
    except Exception as e:
            logger.error(e)
            raise

def main():
    parser = set_parser()
    parser.set_defaults(func=_main_run)
    args = parser.parse_args()
    set_logger(logger, level=args.loglevel, log_path=args.logdir)
    args.func(args)

def set_subparser(subparsers=None):
    if subparsers is None:
        sys.exit(1)
    parser_genimage = subparsers.add_parser('genimage', help='Generate images from package feeds for specified machines')
    parser_genimage = set_parser(parser_genimage)
    parser_genimage.set_defaults(func=_main_run)

if __name__ == "__main__":
    main()