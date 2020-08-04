import os
import os.path
import subprocess
import yaml
from collections import OrderedDict

from genimage.package_manager import DnfRpm
import genimage.utils as utils

class Rootfs(object):
    def __init__(self,
                 workdir,
                 data_dir,
                 machine,
                 pkg_feeds,
                 packages,
                 logger,
                 target_rootfs=None,
                 pkg_globs=None):

        self.workdir = workdir
        self.data_dir = data_dir
        self.machine = machine
        self.pkg_feeds = pkg_feeds
        self.packages = packages
        self.logger = logger
        self.pkg_globs = pkg_globs
        if target_rootfs:
            self.target_rootfs = target_rootfs
        else:
            self.target_rootfs = os.path.join(self.workdir, "rootfs")
        self.packages_yaml = os.path.join(self.workdir, "packages.yaml")

        self.pm = DnfRpm(self.workdir, self.target_rootfs, self.machine, logger)
        self.pm.create_configs()

        self.installed_pkgs = OrderedDict()

        utils.fake_root_set_passwd(self.logger, self.target_rootfs)

        self.rootfs_pre_scripts = [os.path.join(self.data_dir, 'pre_rootfs', 'create_merged_usr_symlinks.sh')]
        self.rootfs_post_scripts = []

    def add_rootfs_post_scripts(self, script_cmd=None):
        if script_cmd is None:
            return
        self.rootfs_post_scripts.append(script_cmd)

    def add_rootfs_pre_scripts(self, script_cmd=None):
        if script_cmd is None:
            return
        self.rootfs_pre_scripts.append(script_cmd)

    def _pre_rootfs(self):
        os.environ['IMAGE_ROOTFS'] = self.pm.target_rootfs
        os.environ['libexecdir'] = '/usr/libexec'

        for script in self.rootfs_pre_scripts:
            self.logger.debug("Executing '%s' preprocess rootfs..." % script)
            res, output = utils.run_cmd(script, self.logger, shell=True)
            if res:
                self.logger.error("Executing %s preprocess rootfs failed\nExit code %d. Output:\n%s"
                                   % (script, res, output))
                raise Exception("Executing %s postprocess rootfs failed\nExit code %d. Output:\n%s"
                                   % (script, res, output))

    def _post_rootfs(self):
        for script in self.rootfs_post_scripts:
            self.logger.debug("Executing '%s' postprocess rootfs..." % script)
            res, output = utils.run_cmd(script, self.logger, shell=True)
            if res:
                self.logger.error("Executing %s postprocess rootfs failed\nExit code %d. Output:\n%s"
                                   % (script, res, output))
                raise Exception("Executing %s postprocess rootfs failed\nExit code %d. Output:\n%s"
                                   % (script, res, output))

    def _save_installed(self):
        for k, v in self.pm.list_installed().items():
            self.installed_pkgs[k] = v

        with open(self.packages_yaml, "w") as f:
            utils.ordered_dump(self.installed_pkgs, f, Dumper=yaml.SafeDumper)
            self.logger.debug("Save Installed Packages Yaml FIle to : %s" % (self.packages_yaml))

    def create(self):
        self._pre_rootfs()

        self.pm.update()
        self.pm.insert_feeds_uris(self.pkg_feeds)
        self.pm.install(self.packages)

        self._save_installed()

        self.pm.install_complementary(self.pkg_globs)

        self.pm.run_intercepts()

        self._post_rootfs()

    def image_list_installed_packages(self):
        return self.installed_pkgs
