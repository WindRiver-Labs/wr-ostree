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

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser_genyaml(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser(
            description='Generate Yaml file from Input Yamls',
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
        'initramfs',
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

    parser.add_argument('input',
        help='Input yaml files',
        action='store',
        nargs='*')

    return parser


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
