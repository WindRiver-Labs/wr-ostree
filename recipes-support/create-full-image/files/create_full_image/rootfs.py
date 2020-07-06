import os
import os.path
import subprocess
import yaml
from collections import OrderedDict

from create_full_image.package_manager import DnfRpm
import create_full_image.utils as utils

class Rootfs(object):
    def __init__(self,
                 workdir,
                 data_dir,
                 machine,
                 pkg_feeds,
                 packages,
                 logger,
                 target_rootfs=None):

        self.workdir = workdir
        self.data_dir = data_dir
        self.machine = machine
        self.pkg_feeds = pkg_feeds
        self.packages = packages
        self.logger = logger
        if target_rootfs:
            self.target_rootfs = target_rootfs
        else:
            self.target_rootfs = os.path.join(self.workdir, "rootfs")
        self.packages_yaml = os.path.join(self.workdir, "packages.yaml")

        self.pm = DnfRpm(self.workdir, self.target_rootfs, self.machine, logger)
        self.pm.create_configs()

    def _pre_rootfs(self):
        os.environ['IMAGE_ROOTFS'] = self.pm.target_rootfs
        os.environ['libexecdir'] = '/usr/libexec'

        pre_rootfs_dir = os.path.join(self.data_dir, 'pre_rootfs')
        if not os.path.exists(pre_rootfs_dir):
            return

        self.logger.info("pre_rootfs_dir %s" % pre_rootfs_dir)
        for script in os.listdir(pre_rootfs_dir):
            script_full = os.path.join(pre_rootfs_dir, script)
            self.logger.info("script %s" % script_full)
            if not os.access(script_full, os.X_OK):
                self.logger.info("not script %s" % script_full)
                continue

            self.logger.debug("> Executing %s preprocess rootfs..." % script)

            try:
                output = subprocess.check_output(script_full, stderr=subprocess.STDOUT)
                if output: self.logger.debug(output.decode("utf-8"))
            except subprocess.CalledProcessError as e:
                self.logger.debug("Exit code %d. Output:\n%s" % (e.returncode, e.output.decode("utf-8")))

    def _post_rootfs(self):
        post_rootfs_dir = os.path.join(self.data_dir, 'post_rootfs')
        if not os.path.exists(post_rootfs_dir):
            return

        for script in os.listdir(post_rootfs_dir):
            script_full = os.path.join(post_rootfs_dir, script)
            if not os.access(script_full, os.X_OK):
                continue

            self.logger.debug("> Executing %s postprocess rootfs..." % script)
            try:
                output = subprocess.check_output(script_full, stderr=subprocess.STDOUT)
                if output: self.logger.debug(output.decode("utf-8"))
            except subprocess.CalledProcessError as e:
                self.logger.debug("Exit code %d. Output:\n%s" % (e.returncode, e.output.decode("utf-8")))

    def create(self):
        self._pre_rootfs()

        self.pm.update()
        self.pm.insert_feeds_uris(self.pkg_feeds)
        self.pm.install(self.packages)
        self.pm.run_intercepts()

        self._post_rootfs()

    def image_list_installed_packages(self):
        data = OrderedDict()
        for k, v in self.pm.list_installed().items():
            data[k] = v

        with open(self.packages_yaml, "w") as f:
            utils.ordered_dump(data, f, Dumper=yaml.SafeDumper)
            self.logger.debug("Save Installed Packages Yaml FIle to : %s" % (self.packages_yaml))

        return data
