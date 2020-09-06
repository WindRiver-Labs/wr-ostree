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
import yaml
from collections import OrderedDict
import glob

from genimage.utils import set_logger
from genimage.utils import get_today
import genimage.constant as constant
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_PACKAGES
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_IMAGE
from genimage.constant import DEFAULT_IMAGE_FEATURES
from genimage.genXXX import GenXXX
from genimage.genXXX import set_parser

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser_genyaml(parser=None):
    supported_types = [
        'wic',
        'vmdk',
        'vdi',
        'ostree-repo',
        'container',
        'initramfs',
        'ustart',
        'all',
    ]

    return set_parser(parser, supported_types)

class GenYaml(GenXXX):
    """
    * Use Input Yaml and command option to customize and generate new Yaml file:
    """
    def __init__(self, args):
        super(GenYaml, self).__init__(args)

        self.output_yaml = os.path.join(self.outdir, "%s-%s.yaml" % (self.data['name'], self.data['machine']))

    def do_generate(self):
        logger.info("Machine: %s" % self.data['machine'])
        logger.info("Image Name: %s" % self.data['name'])
        logger.info("Image Type: %s" % ' '.join(self.data['image_type']))
        logger.info("Pakcages Number: %d" % len(self.data['packages']))
        logger.debug("Pakcages: %s" % self.data['packages'])
        logger.info("External Packages Number: %d" % len(self.data['external-packages']))
        logger.debug("External Packages: %s" % self.data['external-packages'])
        logger.info("Pakcage Feeds:\n%s\n" % '\n'.join(self.data['package_feeds']))
        logger.debug("GPG Path: %s" % self.data["gpg"]["gpg_path"])

        self._save_output_yaml()


def _main_run_internal(args):
    yaml = GenYaml(args)
    yaml.do_generate()

def _main_run(args):
    try:
        ret = _main_run_internal(args)
    except Exception as e:
            logger.error(e)
            raise

def main_genyaml():
    parser = set_parser_genyaml()
    parser.set_defaults(func=_main_run)
    args = parser.parse_args()
    set_logger(logger, level=args.loglevel, log_path=args.logdir)
    args.func(args)

def set_subparser_genyaml(subparsers=None):
    if subparsers is None:
        sys.exit(1)
    parser_genimage = subparsers.add_parser('genyaml', help='Generate Yaml file from Input Yamls')
    parser_genimage = set_parser_genyaml(parser_genimage)
    parser_genimage.set_defaults(func=_main_run)

if __name__ == "__main__":
    main_genyaml()
