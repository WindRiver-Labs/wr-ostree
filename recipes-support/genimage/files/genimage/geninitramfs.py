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
import atexit
import yaml
from collections import OrderedDict
import time
from texttable import Texttable
import glob

from genimage.utils import set_logger
from genimage.utils import get_today
from genimage.utils import show_task_info
import genimage.constant as constant
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_INITRD_NAME
from genimage.constant import DEFAULT_IMAGE_FEATURES
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


class GenInitramfs(object):
    """
    Generate Initramfs
    """

    def __init__(self, args):
        self.args = args

        self.today = get_today()

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

        if not self.args.input:
            logger.info("No Input YAML File, use default setting")
        logger.debug("Yaml File Content: %s" % data)

        self.image_name = data['name'] if 'name' in data else DEFAULT_INITRD_NAME
        self.machine = data['machine'] if 'machine' in data else DEFAULT_MACHINE
        self.image_type = data['image_type'] if 'image_type' in data else ['initramfs']
        self.packages = OSTREE_INITRD_PACKAGES
        if 'packages' in data:
            self.packages = data['packages']
        if self.args.pkg:
            self.packages.extend(self.args.pkg)
        self.packages = list(sorted(set(self.packages)))

        if 'external-packages' in data:
            self.external_packages = data['external-packages']
        else:
            self.external_packages = []
        if self.args.pkg_external:
            self.external_packages.extend(self.args.pkg_external)
        self.external_packages = list(sorted(set(self.external_packages)))

        if 'exclude-packages' not in data:
            data['exclude-packages'] = ['busybox-syslog']

        self.pkg_feeds = data['package_feeds'] if 'package_feeds' in data else DEFAULT_PACKAGE_FEED

        self.remote_pkgdatadir = data['remote_pkgdatadir'] if 'remote_pkgdatadir' in data else DEFAULT_REMOTE_PKGDATADIR

        if self.args.url:
            self.pkg_feeds.extend(self.args.url)
        self.pkg_feeds = list(set(self.pkg_feeds))

        self.features = data['features'] if 'features' in data else DEFAULT_IMAGE_FEATURES

        self.data = data

        self.outdir = os.path.realpath(self.args.outdir)
        self.workdir = os.path.realpath(os.path.join(self.args.workdir, "workdir"))

        utils.fake_root(workdir=self.workdir)
        self.deploydir = os.path.join(self.outdir, "deploy")
        self.output_yaml = os.path.join(self.deploydir, "%s-%s.yaml" % (self.image_name, self.machine))

        for d in [self.workdir, self.deploydir]:
            utils.mkdirhier(d)

        self.target_rootfs = None

        self.ostree_initramfs_name = "initramfs-ostree-image"

        if self.machine != DEFAULT_MACHINE:
            logger.error("MACHINE %s is invalid, SDK is working for %s only" % (self.machine, DEFAULT_MACHINE))
            sys.exit(1)

        if not self.pkg_feeds:
            logger.error("The package feeds does not exist, please set it")
            sys.exit(1)

        if self.args.name:
            self.image_name = self.args.name

        if self.image_name == DEFAULT_INITRD_NAME:
            logger.info("Replace eixsted %s as initrd for appsdk genimage", DEFAULT_INITRD_NAME)

        if self.args.type:
            self.image_type = self.args.type

        # Cleanup all generated rootfs dir by default
        if not self.args.no_clean:
            cmd = "rm -rf {0}/*/rootfs*".format(self.workdir)
            atexit.register(utils.run_cmd_oneshot, cmd=cmd)

        if "gpg" not in self.data:
            self.data["gpg"] = constant.DEFAULT_GPG_DATA
        if self.args.gpgpath:
            self.data["gpg"]["gpg_path"] = self.args.gpgpath

        logger.info("Machine: %s" % self.machine)
        logger.info("Image Name: %s" % self.image_name)
        logger.info("Image Type: %s" % ' '.join(self.image_type))
        logger.info("Pakcages Number: %d" % len(self.packages))
        logger.debug("Pakcages: %s" % self.packages)
        logger.info("External Packages Number: %d" % len(self.external_packages))
        logger.debug("External Packages: %s" % self.external_packages)
        logger.info("Exclude Packages Number: %s" % len(self.data['exclude-packages']))
        logger.debug("Exclude Packages: %s" % self.data['exclude-packages'])
        logger.info("Pakcage Feeds:\n%s\n" % '\n'.join(self.pkg_feeds))
        logger.debug("Deploy Directory: %s" % self.outdir)
        logger.debug("Work Directory: %s" % self.workdir)
        logger.debug("GPG Path: %s" % self.data["gpg"]["gpg_path"])

        self.native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
        self.data_dir = os.path.join(self.native_sysroot, "usr/share/genimage/data")

    def do_prepare(self):
        gpg_data = self.data["gpg"]
        utils.check_gpg_keys(gpg_data)

        if not self.data.get("ostree", None):
            self.data["ostree"] = constant.DEFAULT_OSTREE_DATA
        else:
            for ostree_param in constant.DEFAULT_OSTREE_DATA:
                if ostree_param not in self.data["ostree"]:
                    self.data["ostree"][ostree_param] = constant.DEFAULT_OSTREE_DATA[ostree_param]

        if not self.data.get("wic", None):
            self.data["wic"] = constant.DEFAULT_WIC_DATA
        else:
            for wic_param in constant.DEFAULT_WIC_DATA:
                if wic_param not in self.data["wic"]:
                    self.data["wic"][wic_param] = constant.DEFAULT_WIC_DATA[wic_param]

        os.environ['NO_RECOMMENDATIONS'] = self.data.get('NO_RECOMMENDATIONS', '1')

    def do_post(self):
        for f in ["qemu-u-boot-bcm-2xxx-rpi4.bin", "ovmf.qcow2"]:
            qemu_data = os.path.join(self.native_sysroot, "usr/share/qemu_data", f)
            if os.path.exists(qemu_data):
                logger.debug("Deploy %s", f)
                cmd = "cp -f {0} {1}".format(qemu_data, self.deploydir)
                utils.run_cmd_oneshot(cmd)

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
                        exclude_packages=self.data['exclude-packages'],
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

    def _save_output_yaml(self):
        data = self.data
        data['name'] = self.image_name
        data['machine'] = self.machine
        data['image_type'] = self.image_type
        data['features'] = self.features
        data['package_feeds'] = self.pkg_feeds
        data['remote_pkgdatadir'] = self.remote_pkgdatadir
        data['packages'] = self.packages
        data['external-packages'] = self.external_packages

        with open(self.output_yaml, "w") as f:
            utils.ordered_dump(data, f, Dumper=yaml.SafeDumper)
            logger.debug("Save Yaml FIle to : %s" % (self.output_yaml))

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
