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

from create_full_image.utils import set_logger
from create_full_image.utils import run_cmd
from create_full_image.utils import get_today
from create_full_image.utils import DEFAULT_PACKAGE_FEED
from create_full_image.utils import DEFAULT_PACKAGES
from create_full_image.utils import DEFAULT_MACHINE
from create_full_image.utils import DEFAULT_IMAGE
from create_full_image.utils import DEFAULT_IMAGE_FEATURES

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

        self.image_name = data['name'] if 'name' in data else DEFAULT_MACHINE
        self.machine = data['machine'] if 'machine' in data else DEFAULT_MACHINE
        self.packages = data['packages'] if 'packages' in data else DEFAULT_PACKAGES
        self.pkg_feeds = data['package_feeds'] if 'package_feeds' in data else DEFAULT_PACKAGE_FEED
        self.image_features = data['features'] if 'features' in data else DEFAULT_IMAGE_FEATURES

        self.outdir = self.args.outdir
        self.workdir = self.outdir + "/workdir/" + self.machine

        if self.args.machine:
            self.machine = self.args.machine

        if self.args.url:
            self.pkg_feeds = self.args.url

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







def main():
    create = CreateFullImage()

if __name__ == "__main__":
    main()
