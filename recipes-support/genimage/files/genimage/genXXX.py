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

from genimage.utils import get_today
import genimage.constant as constant
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_PACKAGES
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_IMAGE
from genimage.constant import DEFAULT_IMAGE_FEATURES
from genimage.constant import OSTREE_INITRD_PACKAGES

import genimage.utils as utils

logger = logging.getLogger('appsdk')

class GenXXX(object, metaclass=ABCMeta):
    """
    This is an abstract class. Do not instantiate this directly.
    """
    def __init__(self, args):
        self.args = args
        self.today = get_today()
        self.data = OrderedDict()

        self._set_default()
        self._parse_inputyamls()
        self._parse_options()
        self._fill_missing()

        self.image_name = self.data['name']
        self.machine = self.data['machine']
        self.image_type = self.data['image_type']
        self.packages = self.data['packages']
        self.external_packages = self.data['external-packages']
        self.exclude_packages = self.data['exclude-packages']
        self.pkg_feeds = self.data['package_feeds']
        self.remote_pkgdatadir = self.data['remote_pkgdatadir']
        self.features = self.data['features']

        self.outdir = os.path.realpath(self.args.outdir)
        self.deploydir = os.path.join(self.outdir, "deploy")
        self.output_yaml = os.path.join(self.deploydir, "%s-%s.yaml" % (self.image_name, self.machine))
        utils.mkdirhier(self.deploydir)

        logger.info("Machine: %s" % self.machine)
        logger.info("Image Name: %s" % self.image_name)
        logger.info("Image Type: %s" % ' '.join(self.image_type))
        logger.info("Pakcages Number: %d" % len(self.packages))
        logger.debug("Pakcages: %s" % self.packages)
        logger.info("External Packages Number: %d" % len(self.external_packages))
        logger.debug("External Packages: %s" % self.external_packages)
        logger.info("Exclude Packages Number: %s" % len(self.exclude_packages))
        logger.debug("Exclude Packages: %s" % self.exclude_packages)
        logger.info("NO_RECOMMENDATIONS: %s", self.data['NO_RECOMMENDATIONS'])
        logger.info("Pakcage Feeds:\n%s\n" % '\n'.join(self.pkg_feeds))
        logger.debug("Deploy Directory: %s" % self.outdir)
        logger.debug("GPG Path: %s" % self.data["gpg"]["gpg_path"])

    def _set_default(self):
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
        self.data['exclude-packages'] = []
        self.data['NO_RECOMMENDATIONS'] = '0'

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

        logger.debug("Input Yaml File Content: %s" % data)
        for key in data:
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

    def _fill_missing(self):
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
            self.data['image_type'] = ['ostree-repo', 'wic', 'container', 'ustart', 'vmdk', 'vdi']

        self.data['packages'] = list(sorted(set(self.data['packages'])))
        self.data['external-packages'] = list(sorted(set(self.data['external-packages'])))
        self.data['exclude-packages'] = list(sorted(set(self.data['exclude-packages'])))
        self.data['package_feeds'] = list(sorted(set(self.data['package_feeds'])))

    def _save_output_yaml(self):
        with open(self.output_yaml, "w") as f:
            utils.ordered_dump(self.data, f, Dumper=yaml.SafeDumper)
            logger.debug("Save Yaml FIle to : %s" % (self.output_yaml))


