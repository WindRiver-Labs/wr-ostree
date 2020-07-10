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

        self.target_rootfs = rootfs.target_rootfs

    def do_ostree_initramfs(self):
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
                        self.ostree_initramfs_name,
                        workdir,
                        self.machine,
                        rootfs.target_rootfs,
                        self.deploydir,
                        logger)
        initrd.create()


    def _save_output_yaml(self, installed_dict):
        data = OrderedDict()
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
        image_wic = CreateWicImage(
                        self.image_name,
                        workdir,
                        self.machine,
                        self.target_rootfs,
                        self.deploydir,
                        logger)
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
                        self.image_name,
                        workdir,
                        self.machine,
                        self.target_rootfs,
                        self.deploydir,
                        logger)
        ostree_repo.create()

def main():
    utils.fake_root(logger)
    create = CreateFullImage()
    create.do_rootfs()
    if create.target_rootfs is None:
        logger.error("Create Target Rootfs Failed")
        sys.exit(1)
    else:
        logger.info("Create Target Rootfs: %s" % create.target_rootfs)

    create.do_ostree_initramfs()

    if "wic" in create.image_type:
        create.do_image_wic()

    if "ostree-repo" in create.image_type:
        create.do_ostree_repo()

    if "container" in create.image_type:
        create.do_image_container()

if __name__ == "__main__":
    main()
