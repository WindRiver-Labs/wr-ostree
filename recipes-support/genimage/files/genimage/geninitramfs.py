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
import time
from texttable import Texttable

from genimage.utils import set_logger
from genimage.utils import show_task_info
from genimage.genimage import GenImage
from genimage.constant import DEFAULT_INITRD_NAME
from genimage.constant import OSTREE_INITRD_PACKAGES
from genimage.rootfs import Rootfs
from genimage.image import CreateInitramfs
import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser_geninitramfs(parser=None):
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
        'initramfs',
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


class GenInitramfs(GenImage):
    """
    Generate Initramfs
    """

    def __init__(self, args):
        super(GenInitramfs, self).__init__(args)

        if self.image_name == DEFAULT_INITRD_NAME:
            logger.info("Replace eixsted %s as initrd for appsdk genimage", DEFAULT_INITRD_NAME)

    def _set_default(self):
        super(GenInitramfs, self)._set_default()

        self.data['name'] = DEFAULT_INITRD_NAME
        self.data['image_type'] = ['initramfs']
        self.data['packages'] = OSTREE_INITRD_PACKAGES
        self.data['exclude-packages'] = ['busybox-syslog']
        self.data['NO_RECOMMENDATIONS'] = '1'

    def do_post(self):
        pass

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

        script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'add_gpg_key.sh')
        script_cmd = "{0} {1} {2}".format(script_cmd, rootfs.target_rootfs, self.data['gpg']['gpg_path'])
        rootfs.add_rootfs_post_scripts(script_cmd)

        rootfs.create()

        installed_dict = rootfs.image_list_installed_packages()

        self._save_output_yaml()

        # Generate image manifest
        manifest_name = "{0}/{1}-{2}.manifest".format(self.deploydir, self.image_name, self.machine)
        with open(manifest_name, 'w+') as image_manifest:
            image_manifest.write(utils.format_pkg_list(installed_dict, "ver"))

        self.target_rootfs = rootfs.target_rootfs

    @show_task_info("Create Initramfs")
    def do_ostree_initramfs(self):
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
        cmd = cmd_format % "{0}.cpio.gz".format(image_name)
        if self.machine == "bcm-2xxx-rpi4":
            cmd += ".u-boot"
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
