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
import argparse
import logging
import glob
import subprocess
from texttable import Texttable

from genimage.utils import set_logger
from genimage.constant import DEFAULT_MACHINE

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser_exampleyamls(parser=None):
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

    parser.add_argument('-o', '--outdir',
        default=os.getcwd(),
        help='Specify output dir, default is current working directory',
        action='store')

    return parser

def _main_run_internal(args):
    outdir = os.path.join(args.outdir, 'deploy/exampleyamls')

    native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
    yamlexample_dir = os.path.join(native_sysroot, 'usr/share/genimage/data/yaml_example')
    machine_yaml = os.path.join(yamlexample_dir, 'machine', '{0}.yaml'.format(DEFAULT_MACHINE))
    image_yamls = glob.glob(os.path.join(yamlexample_dir, 'images', '*.yaml'))
    for image_yaml in image_yamls:
        if image_yaml.endswith('container-base.yaml'):
            cmd = "genyaml -d -o {0} --type container {1}".format(outdir, image_yaml)
        elif image_yaml.endswith('initramfs-ostree-image.yaml'):
            cmd = "genyaml -d -o {0} --type initramfs {1}".format(outdir, image_yaml)
        else:
            cmd = "genyaml -d -o {0} {1} {2}".format(outdir, machine_yaml, image_yaml)
        utils.run_cmd_oneshot(cmd)

    cmd = "cp -rf {0}/feature {1}/".format(yamlexample_dir, outdir)
    utils.run_cmd_oneshot(cmd)

    table = Texttable()
    table.set_cols_align(["l", "l"])
    table.set_cols_valign(["t", "t"])
    table.add_rows([["Yaml Type", "Name"]])

    output = subprocess.check_output("ls *.yaml", shell=True, cwd=outdir)
    table.add_row(["Image", output])

    output = subprocess.check_output("ls feature/*.yaml", shell=True, cwd=outdir)
    table.add_row(["Feature", output])


    logger.info("Deploy Directory: %s\n%s", outdir, table.draw())

    logger.info("Then, run genimage or genyaml with Yaml Files:\nappsdk genimage <Image>.yaml <Feature>.yaml\nOr\nappsdk genyaml <Image>.yaml <Feature>.yaml")


def _main_run(args):
    try:
        ret = _main_run_internal(args)
    except Exception as e:
            logger.error(e)
            raise

def main_exampleyamls():
    parser = set_parser_exampleyamls()
    parser.set_defaults(func=_main_run)
    args = parser.parse_args()
    set_logger(logger, level=args.loglevel, log_path=args.logdir)
    args.func(args)

def set_subparser_exampleyamls(subparsers=None):
    if subparsers is None:
        sys.exit(1)
    parser_genimage = subparsers.add_parser('exampleyamls', help='Deploy Example Yaml files')
    parser_genimage = set_parser_exampleyamls(parser_genimage)
    parser_genimage.set_defaults(func=_main_run)

if __name__ == "__main__":
    main_exampleyamls()