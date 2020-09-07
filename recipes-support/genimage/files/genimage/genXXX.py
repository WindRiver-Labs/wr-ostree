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
import logging
import yaml
from collections import OrderedDict
import glob
from abc import ABCMeta, abstractmethod
import argparse
import atexit

from genimage.utils import get_today
from genimage.utils import show_task_info
import genimage.constant as constant
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_PACKAGES
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_IMAGE
from genimage.constant import DEFAULT_IMAGE_FEATURES
from genimage.rootfs import Rootfs

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser(parser=None, supported_types=None):
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

    if supported_types is None:
        supported_types = [
            'wic',
            'vmdk',
            'vdi',
            'ostree-repo',
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
    parser.add_argument('-w', '--workdir',
        default=os.getcwd(),
        help='Specify work dir, default is current working directory',
        action='store')
    parser.add_argument('-t', '--type',
        choices=supported_types,
        help='Specify image type, it overrides \'image_type\' in Yaml',
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
    parser.add_argument('--rootfs-post-script',
        help='Specify extra script to run after do_rootfs',
        action='append')
    parser.add_argument('--rootfs-pre-script',
        help='Specify extra script to run before do_rootfs',
        action='append')
    parser.add_argument('--env',
        help='Specify extra environment to export before do_rootfs: --env NAME=VALUE',
        action='append')
    parser.add_argument("--no-clean",
        help = "Do not cleanup generated rootfs in workdir", action="store_true", default=False)

    parser.add_argument('input',
        help='Input yaml files that the tool can be run against a package feed to generate an image',
        action='store',
        nargs='*')

    return parser
class GenXXX(object, metaclass=ABCMeta):
    """
    This is an abstract class. Do not instantiate this directly.
    """
    def __init__(self, args):
        self.args = args
        self.today = get_today()
        self.data = OrderedDict()

        self._parse_default()
        self._parse_inputyamls()
        self._parse_options()
        self._parse_amend()

        self.image_name = self.data['name']
        self.machine = self.data['machine']
        self.image_type = self.data['image_type']
        self.packages = self.data['packages']
        self.external_packages = self.data['external-packages']
        self.exclude_packages = []
        self.pkg_feeds = self.data['package_feeds']
        self.remote_pkgdatadir = self.data['remote_pkgdatadir']
        self.features = self.data['features']

        self.rootfs_post_scripts = self.data['rootfs-post-scripts']
        self.rootfs_pre_scripts = self.data['rootfs-pre-scripts']
        self.environments = self.data['environments']

        self.outdir = os.path.realpath(self.args.outdir)
        self.deploydir = os.path.join(self.outdir, "deploy")
        self.output_yaml = os.path.join(self.deploydir, "%s-%s.yaml" % (self.image_name, self.machine))
        utils.mkdirhier(self.deploydir)
        self.workdir = os.path.realpath(os.path.join(self.args.workdir, "workdir"))

        self.target_rootfs = None
        self.native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
        self.data_dir = os.path.join(self.native_sysroot, "usr/share/genimage/data")

        logger.info("Machine: %s" % self.machine)
        logger.info("Image Name: %s" % self.image_name)
        logger.info("Image Type: %s" % ' '.join(self.image_type))
        logger.info("Pakcages Number: %d" % len(self.packages))
        logger.debug("Pakcages: %s" % self.packages)
        logger.info("External Packages Number: %d" % len(self.external_packages))
        logger.debug("External Packages: %s" % self.external_packages)
        logger.info("Pakcage Feeds:\n%s\n" % '\n'.join(self.pkg_feeds))
        logger.info("enviroments: %s", self.environments)
        logger.debug("Deploy Directory: %s" % self.outdir)
        logger.debug("GPG Path: %s" % self.data["gpg"]["gpg_path"])
        logger.debug("Work Directory: %s" % self.workdir)

    def _parse_default(self):
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
        self.data['include-default-packages'] = "0"
        self.data['rootfs-pre-scripts'] = ['echo "run script before do_rootfs in $IMAGE_ROOTFS"']
        self.data['rootfs-post-scripts'] = ['echo "run script after do_rootfs in $IMAGE_ROOTFS"']
        self.data['environments'] = ['NO_RECOMMENDATIONS="0"', 'KERNEL_PARAMS="key=value"']

    def _parse_inputyamls(self):
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

        include_default_package = self.data['include-default-packages']
        if 'include-default-packages' in data:
            include_default_package = data['include-default-packages']
        logger.info("Include Default Packages: %s" % include_default_package)

        logger.debug("Input Yaml File Content: %s" % data)
        for key in data:
            if include_default_package != "0" and 'packages' == key:
                self.data[key] += data[key]
                continue
            self.data[key] = data[key]

    def _parse_options(self):
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

        if self.args.rootfs_post_script:
            self.data['rootfs-post-scripts'].extend(self.args.rootfs_post_script)

        if self.args.rootfs_pre_script:
            self.data['rootfs-pre-scripts'].extend(self.args.rootfs_pre_script)

        if self.args.env:
            self.data['environments'].extend(self.args.env)

    def _parse_amend(self):
        # Use default to fill missing params of "ostree" section
        for ostree_param in constant.DEFAULT_OSTREE_DATA:
            if ostree_param not in self.data["ostree"]:
                self.data["ostree"][ostree_param] = constant.DEFAULT_OSTREE_DATA[ostree_param]

        # Use default to fill missing params of "wic" section
        for wic_param in constant.DEFAULT_WIC_DATA:
            if wic_param not in self.data["wic"]:
                self.data["wic"][wic_param] = constant.DEFAULT_WIC_DATA[wic_param]

        if self.data['machine'] != DEFAULT_MACHINE:
            logger.error("MACHINE %s is invalid, SDK is working for %s only" % (self.data['machine'], DEFAULT_MACHINE))
            sys.exit(1)

        if not self.data['package_feeds']:
            logger.error("The package feeds does not exist, please set it")
            sys.exit(1)

        if 'all' in self.data['image_type']:
            self.data['image_type'] = ['ostree-repo', 'wic', 'ustart', 'vmdk', 'vdi']

        # Sort and remove duplicated in list
        for k,v in self.data.items():
            if isinstance(v, list):
                self.data[k] = list(sorted(set(v)))

    def _save_output_yaml(self):
        with open(self.output_yaml, "w") as f:
            utils.ordered_dump(self.data, f, Dumper=yaml.SafeDumper)
            logger.debug("Save Yaml FIle to : %s" % (self.output_yaml))

    def do_prepare(self):
        utils.fake_root(workdir=self.workdir)
        utils.mkdirhier(self.workdir)

        # Cleanup all generated rootfs dir by default
        if not self.args.no_clean:
            cmd = "rm -rf {0}/*/rootfs*".format(self.workdir)
            atexit.register(utils.run_cmd_oneshot, cmd=cmd)

        gpg_data = self.data["gpg"]
        utils.check_gpg_keys(gpg_data)

    def do_post(self):
        pass

    def _do_rootfs_pre(self, rootfs=None):
        if rootfs is None:
            return

        for script_cmd in self.rootfs_post_scripts:
            logger.debug("Add rootfs post script: %s", script_cmd)
            rootfs.add_rootfs_post_scripts(script_cmd)

        for script_cmd in self.rootfs_pre_scripts:
            logger.debug("Add rootfs pre script: %s", script_cmd)
            rootfs.add_rootfs_pre_scripts(script_cmd)

        for env in self.environments:
            k,v = env.split('=', 1)
            v = v.strip('"\'')
            logger.debug("Environment %s=%s", k, v)
            os.environ[k] = v

    def _do_rootfs_post(self, rootfs=None):
        if rootfs is None:
            return

        installed_dict = rootfs.image_list_installed_packages()

        self._save_output_yaml()

        # Generate image manifest
        manifest_name = "{0}/{1}-{2}.manifest".format(self.deploydir, self.image_name, self.machine)
        with open(manifest_name, 'w+') as image_manifest:
            image_manifest.write(utils.format_pkg_list(installed_dict, "ver"))

        self.target_rootfs = rootfs.target_rootfs

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

        self._do_rootfs_pre(rootfs)

        rootfs.create()

        self._do_rootfs_post(rootfs)


