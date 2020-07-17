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
import yaml
from collections import OrderedDict

from create_full_image.utils import set_logger
from create_full_image.utils import get_today
from create_full_image.utils import DEFAULT_PACKAGE_FEED
from create_full_image.utils import DEFAULT_PACKAGES
from create_full_image.utils import DEFAULT_MACHINE
from create_full_image.utils import DEFAULT_IMAGE
from create_full_image.utils import DEFAULT_IMAGE_FEATURES
from create_full_image.utils import OSTREE_INITRD_PACKAGES
from create_full_image.rootfs import Rootfs
from create_full_image.container import CreateContainer
from create_full_image.image import CreateWicImage
from create_full_image.image import CreateOstreeRepo
from create_full_image.image import CreateInitramfs
from create_full_image.image import CreateOstreeOTA

import create_full_image.utils as utils

logger = logging.getLogger('cbas')
set_logger(logger)

class CreateFullImage(object):
    """
    * Create the following images in order:
        - ostree repository
        - wic image
        - container image
    """

    def __init__(self):
        supported_machines = [
            'intel-x86-64',
            'bcm-2xxx-rpi4',
        ]

        self.feed_archs_dict= {
            'intel-x86-64': ['corei7_64', 'intel_x86_64', 'noarch'],
            'bcm-2xxx-rpi4': ['aarch64', 'bcm_2xxx_rpi4', 'noarch'],
        }

        supported_types = [
            'wic',
            'ostree-repo',
            'container',
            'all',
        ]

        parser = argparse.ArgumentParser(
            description='Create images from package feeds for specified machines',
            epilog='Use %(prog)s --help to get help')
        parser.add_argument('-m', '--machine',
            choices=supported_machines,
            help='Specify machine')
        parser.add_argument('-o', '--outdir',
            default=os.getcwd(),
            help='Specify output dir, default is current working directory',
            action='store')
        parser.add_argument('-w', '--workdir',
            default=os.getcwd(),
            help='Specify work dir, default is current working directory',
            action='store')
        parser.add_argument('-t', '--type',
            choices=supported_types,
            help='Specify image type, default is all',
            action='append')
        parser.add_argument('-n', '--name',
            help='Specify image name',
            action='store')
        parser.add_argument('-u', '--url',
            help='Specify urls of rpm package feeds',
            action='append')
        parser.add_argument('-p', '--pkg',
            help='Specify extra package to be installed',
            action='append')
        parser.add_argument('-d', '--debug',
            help = "Enable debug output",
            action='store_const', const=logging.DEBUG, dest='loglevel', default=logging.INFO)
        parser.add_argument('-q', '--quiet',
            help = 'Hide all output except error messages',
            action='store_const', const=logging.ERROR, dest='loglevel')

        parser.add_argument('input',
            help='An input yaml file that the tool can be run against a package feed to generate an image',
            nargs='?')

        self.args = parser.parse_args()

        logger.setLevel(self.args.loglevel)

        self.today = get_today()

        data = dict()
        if self.args.input:
            logger.info("Input YAML File: %s" % self.args.input)
            if not os.path.exists(self.args.input):
                logger.error("Input yaml file '%s' does not exist" % self.args.input)
                sys.exit(1)

            with open(self.args.input) as f:
                data = yaml.load(f, Loader=yaml.FullLoader)
                logger.debug("Yaml File Contentt: %s" % data)
        else:
            logger.info("No Input YAML File, use default setting:")

        self.image_name = data['name'] if 'name' in data else DEFAULT_IMAGE
        self.machine = data['machine'] if 'machine' in data else DEFAULT_MACHINE
        self.packages = data['packages'] if 'packages' in data else DEFAULT_PACKAGES[self.machine]
        self.pkg_feeds = data['package_feeds'] if 'package_feeds' in data else DEFAULT_PACKAGE_FEED
        self.image_features = data['features'] if 'features' in data else DEFAULT_IMAGE_FEATURES

        self.data = data

        self.outdir = self.args.outdir
        self.workdir = os.path.join(self.args.workdir, "workdir")

        self.deploydir = os.path.join(self.outdir, "deploy")
        self.output_yaml = os.path.join(self.deploydir, "%s-%s.yaml" % (self.image_name, self.machine))
        utils.mkdirhier(self.deploydir)

        self.target_rootfs = None

        self.ostree_initramfs_name = "initramfs-ostree-image"

        if self.args.machine:
            self.machine = self.args.machine

        if self.machine != DEFAULT_MACHINE:
            logger.error("MACHINE %s is invalid, SDK is working for %s only" % (self.machine, DEFAULT_MACHINE))
            sys.exit(1)

        if self.args.url:
            self.pkg_feeds = self.args.url

        if not self.pkg_feeds:
            logger.error("The package feeds does not exist, please set it")
            sys.exit(1)

        if self.args.pkg:
            self.packages.extend(self.args.pkg)

        if self.args.name:
            self.image_name = self.args.name

        if self.args.type and 'all' not in self.args.type:
            self.image_type = self.args.type
        else:
            self.image_type = ['ostree-repo', 'wic', 'container']

        logger.info("Machine: %s" % self.machine)
        logger.info("Image Name: %s" % self.image_name)
        logger.info("Image Type: %s" % self.image_type)
        logger.info("Pakcages: %s" % self.packages)
        logger.info("Pakcage Feeds: %s" % self.pkg_feeds)
        logger.debug("Deploy Directory: %s" % self.outdir)
        logger.debug("Work Directory: %s" % self.workdir)

        self.native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
        self.data_dir = os.path.join(self.native_sysroot, "usr/share/create_full_image/data")

    def do_prepare(self):
        if "gpg" in self.data:
            gpg_data = self.data["gpg"]
        else:
            gpg_data = self.data["gpg"] = utils.DEFAULT_GPG_DATA
        utils.check_gpg_keys(gpg_data, logger)

        if "ostree" not in self.data:
            self.data["ostree"] = utils.DEFAULT_OSTREE_DATA

        if "wic" not in self.data:
            self.data["wic"] = utils.DEFAULT_WIC_DATA

    def do_rootfs(self):
        workdir = os.path.join(self.workdir, self.image_name)
        pkg_globs = self.image_features.get("pkg_globs", None)

        rootfs = Rootfs(workdir,
                        self.data_dir,
                        self.machine,
                        self.pkg_feeds,
                        self.packages,
                        logger,
                        pkg_globs=pkg_globs)

        rootfs.create()

        installed_dict = rootfs.image_list_installed_packages()

        self._save_output_yaml(installed_dict)

        # Generate image manifest
        manifest_name = "{0}/{1}-{2}.manifest".format(self.deploydir, self.image_name, self.machine)
        with open(manifest_name, 'w+') as image_manifest:
            image_manifest.write(utils.format_pkg_list(installed_dict, "ver"))

        self.target_rootfs = rootfs.target_rootfs

        # Copy kernel image, boot files, device tree files to deploy dir
        if self.machine == "intel-x86-64":
            for files in ["boot/bzImage*", "boot/efi/EFI/BOOT/*"]:
                cmd = "cp -rf {0}/{1} {2}".format(self.target_rootfs, files, self.deploydir)
                utils.run_cmd_oneshot(cmd, logger)
        else:
            cmd = "cp -rf {0}/boot/* {1}".format(self.target_rootfs, self.deploydir)
            utils.run_cmd_oneshot(cmd, logger)

    def do_ostree_initramfs(self):
        # If the Initramfs exists, reuse it
        image_name = "{0}-{1}.cpio.gz".format(self.ostree_initramfs_name, self.machine)
        if self.machine == "bcm-2xxx-rpi4":
            image_name += ".u-boot"
        image_link = os.path.join(self.deploydir, image_name)
        if os.path.islink(image_link) and os.path.exists(os.path.realpath(image_link)):
            logger.info("Reuse existed Initramfs")
            return

        workdir = os.path.join(self.workdir, self.ostree_initramfs_name)

        rootfs = Rootfs(workdir,
                        self.data_dir,
                        self.machine,
                        self.pkg_feeds,
                        OSTREE_INITRD_PACKAGES,
                        logger)

        rootfs.create()

        rootfs.image_list_installed_packages()

        initrd = CreateInitramfs(
                        image_name = self.ostree_initramfs_name,
                        workdir = workdir,
                        machine = self.machine,
                        target_rootfs = rootfs.target_rootfs,
                        deploydir = self.deploydir,
                        logger = logger)
        initrd.create()


    def _save_output_yaml(self, installed_dict):
        data = self.data
        data['name'] = self.image_name
        data['machine'] = self.machine
        data['features'] = self.image_features
        data['package_feeds'] = self.pkg_feeds
        data['packages'] = list(installed_dict.keys())
        with open(self.output_yaml, "w") as f:
            utils.ordered_dump(data, f, Dumper=yaml.SafeDumper)
            logger.debug("Save Yaml FIle to : %s" % (self.output_yaml))

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
                        wks_file = wks_file,
                        logger = logger)

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

    def do_image_container(self):
        workdir = os.path.join(self.workdir, self.image_name)
        container = CreateContainer(
                        workdir,
                        self.machine,
                        self.target_rootfs,
                        self.deploydir,
                        logger)
        container.create()

    def do_ostree_repo(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ostree_repo = CreateOstreeRepo(
                        image_name = self.image_name,
                        workdir = workdir,
                        machine = self.machine,
                        target_rootfs = self.target_rootfs,
                        deploydir = self.deploydir,
                        logger = logger,
                        gpg_path = self.data['gpg']['gpg_path'],
                        gpgid = self.data['gpg']['ostree']['gpgid'],
                        gpg_password = self.data['gpg']['ostree']['gpg_password'])

        ostree_repo.create()

    def do_ostree_ota(self):
        workdir = os.path.join(self.workdir, self.image_name)
        # ostree_use_ab, ostree_osname, ostree_skip_boot_diff
        # ostree_remote_url, gpgid
        extra_params = self.data["ostree"].copy()
        extra_params.update({'gpgid': self.data["gpg"]['ostree']['gpgid']})
        ostree_ota = CreateOstreeOTA(
                        image_name = self.image_name,
                        workdir = workdir,
                        machine = self.machine,
                        deploydir = self.deploydir,
                        logger = logger,
                        **extra_params)

        ostree_ota.create()


def main():
    utils.fake_root(logger)
    create = CreateFullImage()
    create.do_prepare()
    create.do_rootfs()
    if create.target_rootfs is None:
        logger.error("Create Target Rootfs Failed")
        sys.exit(1)
    else:
        logger.info("Create Target Rootfs: %s" % create.target_rootfs)

    create.do_ostree_initramfs()

    # WIC image requires ostress repo
    if any(img_type in create.image_type for img_type in ["ostree-repo", "wic"]):
        create.do_ostree_repo()

    if "wic" in create.image_type:
        create.do_ostree_ota()
        create.do_image_wic()

    if "container" in create.image_type:
        create.do_image_container()

if __name__ == "__main__":
    main()
