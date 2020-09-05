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


class GenYaml(object):
    """
    * Use Input Yaml and command option to customize and generate new Yaml file:
    """

    def __init__(self, args):
        self.args = args

        self.today = get_today()

        self.data = OrderedDict()

    def do_parse_options(self):
        if self.args.name:
            self.data['name'] = self.args.name

        if self.args.type:
            self.data['image_type'] = self.args.type

        if self.args.url:
            self.data['package_feeds'].extend(self.args.url)

        if self.args.pkg:
            self.data['packages'].extend(self.args.pkg)

        if self.args.pkg_external:
            self.data['external-packages'].extend(self.args.pkg_external)

        if self.args.gpgpath:
            self.data["gpg"]["gpg_path"] = self.args.gpgpath

    def do_parse_inputyamls(self):
        if not self.args.input:
            logger.info("No Input YAML File, use default setting")
            return

        data = dict()
        yaml_files = []
        for input_glob in self.args.input:
            yaml_files.extend(glob.glob(input_glob))

        for yaml_file in yaml_files:
            logger.info("Input YAML File: %s" % yaml_file)
            if not os.path.exists(yaml_file):
                logger.error("Input yaml file '%s' does not exist" % yaml_file)
                sys.exit(1)

            with open(yaml_file) as f:
                d = yaml.load(f, Loader=yaml.FullLoader) or dict()

            for key in d:
                if key not in data:
                    data[key] = d[key]
                    continue

                # Collect packages from all Yaml file as many as possible
                if key == 'packages':
                    data[key].extend(d[key])

                # Except packages, the duplicated param is not allowed
                elif key in data:
                    logger.error("There is duplicated '%s' in Yaml File %s", key, yaml_file)
                    sys.exit(1)

        logger.debug("Input Yaml File Content: %s" % data)
        for key in data:
            self.data[key] = data[key]

    def do_set_default(self):
        self.data['name'] = DEFAULT_IMAGE
        self.data['machine'] = DEFAULT_MACHINE
        self.data['image_type'] = ['ustart', 'ostree-repo']
        self.data['package_feeds'] = DEFAULT_PACKAGE_FEED
        self.data["ostree"] = constant.DEFAULT_OSTREE_DATA
        self.data["wic"] = constant.DEFAULT_WIC_DATA
        self.data['remote_pkgdatadir'] = DEFAULT_REMOTE_PKGDATADIR
        self.data['features'] =  DEFAULT_IMAGE_FEATURES
        self.data["gpg"] = constant.DEFAULT_GPG_DATA
        self.data['packages'] = DEFAULT_PACKAGES[DEFAULT_MACHINE]
        self.data['external-packages'] = []

    def do_fill_missing(self):
        # Use default to fill missing params of "ostree" section
        for ostree_param in constant.DEFAULT_OSTREE_DATA:
            if ostree_param not in self.data["ostree"]:
                self.data["ostree"][ostree_param] = constant.DEFAULT_OSTREE_DATA[ostree_param]

        # Use default to fill missing params of "wic" section
        for wic_param in constant.DEFAULT_WIC_DATA:
            if wic_param not in self.data["wic"]:
                self.data["wic"][wic_param] = constant.DEFAULT_WIC_DATA[wic_param]


    def do_generate(self):
        if self.data['machine'] != DEFAULT_MACHINE:
            logger.error("MACHINE %s is invalid, SDK is working for %s only" % (self.data['machine'], DEFAULT_MACHINE))
            sys.exit(1)

        if not self.data['package_feeds']:
            logger.error("The package feeds does not exist, please set it")
            sys.exit(1)

        if 'all' in self.data['image_type']:
            self.data['image_type'] = ['ostree-repo', 'wic', 'container', 'ustart', 'vmdk', 'vdi']

        self.data['packages'] = list(sorted(set(self.data['packages'])))
        self.data['external-packages'] = list(sorted(set(self.data['external-packages'])))
        self.data['package_feeds'] = list(sorted(set(self.data['package_feeds'])))

        outdir = os.path.realpath(self.args.outdir)
        utils.mkdirhier(outdir)
        output_yaml = os.path.join(outdir, "%s-%s.yaml" % (self.data['name'], self.data['machine']))

        logger.info("Machine: %s" % self.data['machine'])
        logger.info("Image Name: %s" % self.data['name'])
        logger.info("Image Type: %s" % ' '.join(self.data['image_type']))
        logger.info("Pakcages Number: %d" % len(self.data['packages']))
        logger.debug("Pakcages: %s" % self.data['packages'])
        logger.info("External Packages Number: %d" % len(self.data['external-packages']))
        logger.debug("External Packages: %s" % self.data['external-packages'])
        logger.info("Pakcage Feeds:\n%s\n" % '\n'.join(self.data['package_feeds']))
        logger.debug("GPG Path: %s" % self.data["gpg"]["gpg_path"])

        with open(output_yaml, "w") as f:
            utils.ordered_dump(self.data, f, Dumper=yaml.SafeDumper)
            logger.info("Save Yaml FIle to : %s" % (output_yaml))


def _main_run_internal(args):
    yaml = GenYaml(args)
    yaml.do_set_default()
    yaml.do_parse_inputyamls()
    yaml.do_parse_options()
    yaml.do_fill_missing()
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
