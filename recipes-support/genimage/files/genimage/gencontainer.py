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

    def _parse_default(self):
        super(GenContainer, self)._parse_default()

        self.data['name'] = DEFAULT_CONTAINER_NAME
        self.data['image_type'] = ['container']
        self.data['packages'] = DEFAULT_CONTAINER_PACKAGES
        self.data['exclude-packages'] = ['systemd*']
        self.data['environments'] = ['NO_RECOMMENDATIONS="1"']

    @show_task_info("Create Docker Container")
    def do_image_container(self):
        workdir = os.path.join(self.workdir, self.image_name)
        container = CreateContainer(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        target_rootfs=self.target_rootfs,
                        deploydir=self.deploydir)
        container.create()

    def do_report(self):
        table = Texttable()
        table.set_cols_align(["l", "l"])
        table.set_cols_valign(["t", "t"])

        image_name = "%s-%s" % (self.image_name, self.machine)
        cmd_format = "ls -gh --time-style=+%%Y %s | awk '{$1=$2=$3=$4=$5=\"\"; print $0}'"

        cmd = cmd_format % "{0}.container.tar.bz2".format(image_name)
        output = subprocess.check_output(cmd, shell=True, cwd=self.deploydir)
        table.add_row(["Container Image", output.strip()])

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
