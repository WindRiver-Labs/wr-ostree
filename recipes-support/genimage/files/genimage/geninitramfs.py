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
import subprocess
import logging
from texttable import Texttable
import argcomplete

from genimage.utils import set_logger
from genimage.utils import show_task_info
import genimage.constant as constant
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_INITRD_NAME
from genimage.constant import OSTREE_INITRD_PACKAGES
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_IMAGE_FEATURES
from genimage.image import CreateInitramfs
from genimage.genXXX import set_parser
from genimage.genXXX import GenXXX

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser_geninitramfs(parser=None):
    parser = set_parser(parser, None)
    parser.add_argument('-g', '--gpgpath',
        default=None,
        help='Specify gpg homedir, it overrides \'gpg_path\' in Yaml, default is /tmp/.cbas_gnupg',
        action='store')
    return parser

class GenInitramfs(GenXXX):
    """
    Generate Initramfs
    """

    def __init__(self, args):
        super(GenInitramfs, self).__init__(args)
        self.exclude_packages = ['busybox-syslog']
        logger.debug("GPG Path: %s" % self.data["gpg"]["gpg_path"])

    def _parse_default(self):
        self.data['name'] = DEFAULT_INITRD_NAME
        self.data['machine'] = DEFAULT_MACHINE
        self.data['image_type'] = ['initramfs']
        self.data['package_feeds'] = DEFAULT_PACKAGE_FEED
        self.data['remote_pkgdatadir'] = DEFAULT_REMOTE_PKGDATADIR
        self.data['features'] =  DEFAULT_IMAGE_FEATURES
        self.data["gpg"] = constant.DEFAULT_GPG_DATA
        self.data['packages'] = OSTREE_INITRD_PACKAGES
        self.data['external-packages'] = []
        self.data['include-default-packages'] = "1"
        self.data['rootfs-pre-scripts'] = ['echo "run script before do_rootfs in $IMAGE_ROOTFS"']
        self.data['rootfs-post-scripts'] = ['echo "run script after do_rootfs in $IMAGE_ROOTFS"']
        self.data['environments'] = ['NO_RECOMMENDATIONS="1"']

    def _parse_options(self):
        super(GenInitramfs, self)._parse_options()
        if self.args.gpgpath:
            self.data["gpg"]["gpg_path"] = os.path.realpath(self.args.gpgpath)

    def _parse_amend(self):
        super(GenInitramfs, self)._parse_amend()
        if len(self.data['image_type']) != 1 or 'initramfs' not in self.data['image_type']:
            logger.error("Only 'initramfs' image_type is supported\nIncorrect setting: %s", self.data['image_type'])
            sys.exit(1)

    def _do_rootfs_pre(self, rootfs=None):
        if rootfs is None:
            return

        super(GenInitramfs, self)._do_rootfs_pre(rootfs)

        script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'add_gpg_key.sh')
        script_cmd = "{0} {1} {2}".format(script_cmd, rootfs.target_rootfs, self.data['gpg']['gpg_path'])
        rootfs.add_rootfs_post_scripts(script_cmd)

    def do_prepare(self):
        super(GenInitramfs, self).do_prepare()
        gpg_data = self.data["gpg"]
        utils.check_gpg_keys(gpg_data)

    @show_task_info("Create Initramfs")
    def do_ostree_initramfs(self):
        if self.image_name == DEFAULT_INITRD_NAME:
            logger.info("Replace eixsted %s as initrd for appsdk genimage", DEFAULT_INITRD_NAME)

        # If the Initramfs exists, reuse it
        image_name = "{0}-{1}.cpio.gz".format(self.image_name, self.machine)
        if self.machine == "bcm-2xxx-rpi4":
            image_name += ".u-boot"


        workdir = os.path.join(self.workdir, self.image_name)

        initrd = CreateInitramfs(
                        image_name = self.image_name,
                        workdir = workdir,
                        machine = self.machine,
                        target_rootfs = self.target_rootfs,
                        deploydir = self.deploydir)
        initrd.create()

    def do_report(self):
        table = Texttable()
        table.set_cols_align(["l", "l"])
        table.set_cols_valign(["t", "t"])

        image_name = "%s-%s" % (self.image_name, self.machine)
        cmd_format = "ls -gh --time-style=+%%Y %s | awk '{$1=$2=$3=$4=$5=\"\"; print $0}'"
        if self.machine == "bcm-2xxx-rpi4":
            cmd = cmd_format % "{0}.cpio.gz.u-boot".format(image_name)
        else:
            cmd = cmd_format % "{0}.cpio.gz".format(image_name)
        output = subprocess.check_output(cmd, shell=True, cwd=self.deploydir)
        table.add_row(["Image", output.strip()])

        logger.info("Deploy Directory: %s\n%s", self.deploydir, table.draw())

def _main_run_internal(args):
    create = GenInitramfs(args)
    create.do_prepare()
    create.do_rootfs()
    if create.target_rootfs is None:
        logger.error("Create Target Rootfs Failed")
        sys.exit(1)
    else:
        logger.debug("Create Target Rootfs: %s" % create.target_rootfs)

    create.do_ostree_initramfs()

    create.do_post()
    create.do_report()

def _main_run(args):
    try:
        ret = _main_run_internal(args)
    except Exception as e:
            logger.error(e)
            raise

def main_geninitramfs():
    parser = set_parser_geninitramfs()
    parser.set_defaults(func=_main_run)
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    set_logger(logger, level=args.loglevel, log_path=args.logdir)
    args.func(args)

def set_subparser_geninitramfs(subparsers=None):
    if subparsers is None:
        sys.exit(1)
    parser_genimage = subparsers.add_parser('geninitramfs', help='Generate Initramfs from package feeds for specified machines')
    parser_genimage = set_parser_geninitramfs(parser_genimage)
    parser_genimage.set_defaults(func=_main_run)

if __name__ == "__main__":
    main()
