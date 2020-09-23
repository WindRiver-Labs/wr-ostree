#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
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
import logging
import argcomplete
import glob
import yaml

from genimage.utils import set_logger
from genimage.genXXX import GenXXX
from genimage.genXXX import set_parser

import genimage.constant as constant
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_PACKAGES
from genimage.constant import OSTREE_INITRD_PACKAGES
from genimage.constant import DEFAULT_CONTAINER_PACKAGES
from genimage.constant import DEFAULT_IMAGE
from genimage.constant import DEFAULT_INITRD_NAME
from genimage.constant import DEFAULT_CONTAINER_NAME
from genimage.constant import DEFAULT_OCI_CONTAINER_DATA
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_IMAGE_FEATURES

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
    ]

    return set_parser(parser, supported_types)

class GenYaml(GenXXX):
    """
    * Use Input Yaml and command option to customize and generate new Yaml file:
    """
    def __init__(self, args):
        self._set_gen_type(args)

        super(GenYaml, self).__init__(args)

        self.data['include-default-packages'] = "0"

        self.output_yaml = os.path.join(self.outdir, "%s-%s.yaml" % (self.data['name'], self.data['machine']))

        utils.remove(self.deploydir, recurse=True)

    def _set_gen_type(self, args):
        '''
        According to image_type, set generate type:
        genimage for any of ostree_repo, wic, ustart, vmdk, vid
        gencontainer for container
        geninitramfs for initramfs
        '''
        image_types = []

        # Colloect image_type from input yamls
        if args.input:
            for input_glob in args.input:
                if not glob.glob(input_glob):
                    continue
                for yaml_file in glob.glob(input_glob):
                    with open(yaml_file) as f:
                        d = yaml.load(f, Loader=yaml.FullLoader) or dict()
                        if 'image_type' in d:
                            image_types.extend(d['image_type'])

        # Use option --type to override
        if args.type:
            image_types = args.type

        self.gen_type = "genimage"
        if any([i == t for i in image_types for t in ['ostree_repo', 'wic', 'ustart', 'vmdk', 'vdi']]):
            self.gen_type = "genimage"
        elif 'container' in image_types:
            self.gen_type = "gencontainer"
        elif 'initramfs' in image_types:
            self.gen_type = "geninitramfs"

        return

    def _parse_default(self):
        if self.gen_type == "genimage":
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
            self.data['include-default-packages'] = "1"
            self.data['rootfs-pre-scripts'] = ['echo "run script before do_rootfs in $IMAGE_ROOTFS"']
            self.data['rootfs-post-scripts'] = ['echo "run script after do_rootfs in $IMAGE_ROOTFS"']
            self.data['environments'] = ['NO_RECOMMENDATIONS="0"', 'KERNEL_PARAMS="key=value"']
        elif self.gen_type == "gencontainer":
            self.data['name'] = DEFAULT_CONTAINER_NAME
            self.data['machine'] = DEFAULT_MACHINE
            self.data['image_type'] = ['container']
            self.data['package_feeds'] = DEFAULT_PACKAGE_FEED
            self.data['remote_pkgdatadir'] = DEFAULT_REMOTE_PKGDATADIR
            self.data['features'] =  DEFAULT_IMAGE_FEATURES
            self.data['packages'] = DEFAULT_CONTAINER_PACKAGES
            self.data['external-packages'] = []
            self.data['include-default-packages'] = "1"
            self.data['rootfs-pre-scripts'] = ['echo "run script before do_rootfs in $IMAGE_ROOTFS"']
            self.data['rootfs-post-scripts'] = ['echo "run script after do_rootfs in $IMAGE_ROOTFS"']
            self.data['environments'] = ['NO_RECOMMENDATIONS="1"']
            self.data['container_oci'] = DEFAULT_OCI_CONTAINER_DATA
            if DEFAULT_MACHINE == 'intel-x86-64':
                self.data['container_oci']['OCI_IMAGE_ARCH'] = 'x86-64'
            elif DEFAULT_MACHINE == 'bcm-2xxx-rpi4':
                self.data['container_oci']['OCI_IMAGE_ARCH'] = 'aarch64'
            self.data['container_upload_cmd'] = ""
        elif self.gen_type == "geninitramfs":
            self.data['name'] = DEFAULT_INITRD_NAME
            self.data['machine'] = DEFAULT_MACHINE
            self.data['image_type'] = ['initramfs']
            self.data['package_feeds'] = DEFAULT_PACKAGE_FEED
            self.data['remote_pkgdatadir'] = DEFAULT_REMOTE_PKGDATADIR
            self.data['features'] =  DEFAULT_IMAGE_FEATURES
            self.data['packages'] = OSTREE_INITRD_PACKAGES
            self.data['external-packages'] = []
            self.data['include-default-packages'] = "1"
            self.data['rootfs-pre-scripts'] = ['echo "run script before do_rootfs in $IMAGE_ROOTFS"']
            self.data['rootfs-post-scripts'] = ['echo "run script after do_rootfs in $IMAGE_ROOTFS"']
            self.data['environments'] = ['NO_RECOMMENDATIONS="1"']

    def do_generate(self):
        self._save_output_yaml()
        logger.info("Save Yaml FIle to : %s" % (self.output_yaml))

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
    argcomplete.autocomplete(parser)
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
