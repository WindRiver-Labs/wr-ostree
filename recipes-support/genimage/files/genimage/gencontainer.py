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
import logging
from texttable import Texttable

from genimage.utils import set_logger
from genimage.utils import show_task_info
from genimage.constant import DEFAULT_CONTAINER_NAME
from genimage.constant import DEFAULT_CONTAINER_PACKAGES
from genimage.constant import DEFAULT_OCI_CONTAINER_DATA
from genimage.constant import DEFAULT_MACHINE
from genimage.container import CreateContainer
from genimage.genXXX import set_parser
from genimage.genXXX import GenXXX

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser_gencontainer(parser=None):
    supported_types = [
        'container',
    ]

    return set_parser(parser, supported_types)


class GenContainer(GenXXX):
    """
    Generate Container Image
    """

    def __init__(self, args):
        super(GenContainer, self).__init__(args)
        self.exclude_packages = ['systemd*']
        self.oci_rootfs_dir = "{0}/{1}-{2}.container.rootfs-oci".format(self.deploydir, self.image_name, self.machine)
        utils.remove(self.oci_rootfs_dir, recurse=True)
        if not self.data['container_upload_cmd'] or self.data['container_upload_cmd'].startswith('#'):
            skopeo_opt = "--dest-tls-verify=false"
            src_image = "oci:%s" % os.path.relpath(self.oci_rootfs_dir)
            dest_image = "docker://pek-lpdfs01:5000/{0}-{1}".format(self.image_name, self.machine)
            self.data['container_upload_cmd'] = "#skopeo copy {0} {1} {2}".format(skopeo_opt, src_image, dest_image)

    def _parse_default(self):
        super(GenContainer, self)._parse_default()

        self.data['name'] = DEFAULT_CONTAINER_NAME
        self.data['image_type'] = ['container']
        self.data['packages'] = DEFAULT_CONTAINER_PACKAGES
        self.data['environments'] = ['NO_RECOMMENDATIONS="1"']
        self.data['container_oci'] = DEFAULT_OCI_CONTAINER_DATA
        if DEFAULT_MACHINE == 'intel-x86-64':
            self.data['container_oci']['OCI_IMAGE_ARCH'] = 'x86-64'
        elif DEFAULT_MACHINE == 'bcm-2xxx-rpi4':
            self.data['container_oci']['OCI_IMAGE_ARCH'] = 'aarch64'
        self.data['container_upload_cmd'] = ""


    @show_task_info("Create Docker Container")
    def do_image_container(self):
        workdir = os.path.join(self.workdir, self.image_name)
        container = CreateContainer(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        target_rootfs=self.target_rootfs,
                        deploydir=self.deploydir,
                        container_oci=self.data['container_oci'])
        container.create()

    def do_upload(self):
        tgz = "{0}-{1}.container.rootfs-oci-{2}-{3}-linux.oci-image.tar".format(self.image_name,
                                                                                self.machine,
                                                                                self.data['container_oci']['OCI_IMAGE_TAG'],
                                                                                self.data['container_oci']['OCI_IMAGE_ARCH'])
        cmd = "tar -xvf {0}".format(tgz)
        utils.run_cmd_oneshot(cmd, cwd=self.deploydir)

        if self.data['container_upload_cmd'] and not self.data['container_upload_cmd'].startswith('#'):
            cmd = self.data['container_upload_cmd']
            logger.info("Run the following command to upload container image:\n   %s", cmd)
            output = subprocess.check_output(cmd, shell=True)
            logger.info("Result: %s", output.decode())
        else:
            logger.info("You could run the following command to upload container image manually:\n   %s", self.data['container_upload_cmd'].replace("#", ""))


    def do_report(self):
        table = Texttable()
        table.set_cols_align(["l", "l"])
        table.set_cols_valign(["t", "t"])

        image_name = "%s-%s" % (self.image_name, self.machine)
        cmd_format = "ls -gh --time-style=+%%Y %s | awk '{$1=$2=$3=$4=$5=\"\"; print $0}'"

        cmd = cmd_format % "{0}.container.tar.bz2".format(image_name)
        output = subprocess.check_output(cmd, shell=True, cwd=self.deploydir)
        table.add_row(["Container Image", output.strip()])

        cmd = "ls {0}.container.rootfs-oci-*-linux.oci-image.tar".format(image_name)
        output = subprocess.check_output(cmd, shell=True, cwd=self.deploydir)
        table.add_row(["OCI Container Image", output.strip()])

        cmd = cmd_format % "{0}.container.tar.bz2.README.md".format(image_name)
        output = subprocess.check_output(cmd, shell=True, cwd=self.deploydir)
        table.add_row(["Container Image Doc", output.strip()])

        logger.info("Deploy Directory: %s\n%s", self.deploydir, table.draw())

def _main_run_internal(args):
    create = GenContainer(args)
    create.do_prepare()
    create.do_rootfs()
    if create.target_rootfs is None:
        logger.error("Create Target Rootfs Failed")
        sys.exit(1)
    else:
        logger.debug("Create Target Rootfs: %s" % create.target_rootfs)

    create.do_image_container()
    create.do_upload()
    create.do_post()
    create.do_report()

def _main_run(args):
    try:
        ret = _main_run_internal(args)
    except Exception as e:
            logger.error(e)
            raise

def main_gencontainer():
    parser = set_parser_gencontainer()
    parser.set_defaults(func=_main_run)
    args = parser.parse_args()
    set_logger(logger, level=args.loglevel, log_path=args.logdir)
    args.func(args)

def set_subparser_gencontainer(subparsers=None):
    if subparsers is None:
        sys.exit(1)
    parser_genimage = subparsers.add_parser('gencontainer', help='Generate Container Image from package feeds for specified machines')
    parser_genimage = set_parser_gencontainer(parser_genimage)
    parser_genimage.set_defaults(func=_main_run)

if __name__ == "__main__":
    main()
