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
import glob
import time
import hashlib
import yaml
from collections import OrderedDict

from create_full_image.utils import set_logger
from create_full_image.utils import run_cmd
from create_full_image.utils import get_today
from create_full_image.utils import DEFAULT_PACKAGE_FEED
from create_full_image.utils import DEFAULT_PACKAGES
from create_full_image.utils import DEFAULT_MACHINE
from create_full_image.utils import DEFAULT_IMAGE
from create_full_image.utils import DEFAULT_IMAGE_FEATURES
from create_full_image.package_manager import DnfRpm
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
        self.workdir = self.outdir + "/workdir/" + self.machine

        self.deploydir = os.path.join(self.outdir, "deploy")
        self.output_yaml = os.path.join(self.deploydir, "%s-%s.yaml" % (self.image_name, self.machine))
        utils.mkdirhier(self.deploydir)
        self.packages_yaml = os.path.join(self.workdir, "packages.yaml")

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

        self.pm = DnfRpm(self.workdir, self.machine, logger)
        self.pm.create_configs()

        self.native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
        self.data_dir = os.path.join(self.native_sysroot, "usr/share/create_full_image/data")

    def do_rootfs(self):
        self._pre_rootfs()

        self.pm.update()
        self.pm.insert_feeds_uris(self.pkg_feeds)
        self.pm.install(self.packages)
        self.pm.run_intercepts()

        self._post_rootfs()

        self.save_output_yaml()

    def _pre_rootfs(self):
        os.environ['IMAGE_ROOTFS'] = self.pm.target_rootfs
        os.environ['libexecdir'] = '/usr/libexec'

        pre_rootfs_dir = os.path.join(self.data_dir, 'pre_rootfs')
        if not os.path.exists(pre_rootfs_dir):
            return

        logger.info("pre_rootfs_dir %s" % pre_rootfs_dir)
        for script in os.listdir(pre_rootfs_dir):
            script_full = os.path.join(pre_rootfs_dir, script)
            logger.info("script %s" % script_full)
            if not os.access(script_full, os.X_OK):
                logger.info("not script %s" % script_full)
                continue

            logger.debug("> Executing %s preprocess rootfs..." % script)

            try:
                output = subprocess.check_output(script_full, stderr=subprocess.STDOUT)
                if output: logger.debug(output.decode("utf-8"))
            except subprocess.CalledProcessError as e:
                logger.debug("Exit code %d. Output:\n%s" % (e.returncode, e.output.decode("utf-8")))

    def _post_rootfs(self):
        post_rootfs_dir = os.path.join(self.data_dir, 'post_rootfs')
        if not os.path.exists(post_rootfs_dir):
            return

        for script in os.listdir(post_rootfs_dir):
            script_full = os.path.join(post_rootfs_dir, script)
            if not os.access(script_full, os.X_OK):
                continue

            logger.debug("> Executing %s postprocess rootfs..." % script)
            try:
                output = subprocess.check_output(script_full, stderr=subprocess.STDOUT)
                if output: logger.debug(output.decode("utf-8"))
            except subprocess.CalledProcessError as e:
                logger.debug("Exit code %d. Output:\n%s" % (e.returncode, e.output.decode("utf-8")))

    def image_list_installed_packages(self):
        data = OrderedDict()
        for k, v in self.pm.list_installed().items():
            data[k] = v
        return data

    def save_output_yaml(self):
        installed_dict = self.image_list_installed_packages()
        with open(self.packages_yaml, "w") as f:
            utils.ordered_dump(installed_dict, f, Dumper=yaml.SafeDumper)
            logger.debug("Save Installed Packages Yaml FIle to : %s" % (self.packages_yaml))

        data = OrderedDict()
        data['name'] = self.image_name
        data['machine'] = self.machine
        data['features'] = self.image_features
        data['package_feeds'] = self.pkg_feeds
        data['packages'] = list(installed_dict.keys())
        with open(self.output_yaml, "w") as f:
            utils.ordered_dump(data, f, Dumper=yaml.SafeDumper)
            logger.debug("Save Yaml FIle to : %s" % (self.output_yaml))


def main():
    utils.fake_root(logger)
    create = CreateFullImage()
    create.do_rootfs()

if __name__ == "__main__":
    main()
