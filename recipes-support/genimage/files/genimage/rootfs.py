import os
import os.path
import subprocess
import yaml
from collections import OrderedDict
import logging

from genimage.package_manager import DnfRpm
import genimage.utils as utils

logger = logging.getLogger('appsdk')

class Rootfs(object):
    def __init__(self,
                 workdir,
                 data_dir,
                 machine,
                 pkg_feeds,
                 packages,
                 external_packages=[],
                 exclude_packages=[],
                 remote_pkgdatadir=None,
                 target_rootfs=None,
                 image_linguas=None,
                 pkg_globs=None):

        self.workdir = workdir
        self.data_dir = data_dir
        self.machine = machine
        self.pkg_feeds = pkg_feeds
        self.packages = packages
        self.external_packages = external_packages
        self.exclude_packages = exclude_packages

        self.pkg_globs = "" if pkg_globs is None else pkg_globs
        if image_linguas:
            self.pkg_globs += " %s" % self._image_linguas_globs(image_linguas)
            self.packages = list(map(lambda s: "locale-base-%s" % s, image_linguas.split())) + self.packages
        if target_rootfs:
            self.target_rootfs = target_rootfs
        else:
            self.target_rootfs = os.path.join(self.workdir, "rootfs")
        self.packages_yaml = os.path.join(self.workdir, "packages.yaml")

        self.rootfs_pre_scripts = [os.path.join(self.data_dir, 'pre_rootfs', 'create_merged_usr_symlinks.sh')]
        if remote_pkgdatadir and utils.is_sdk():
            script_cmd = os.path.join(self.data_dir, 'pre_rootfs', 'update_pkgdata.sh')
            os.environ['REMOTE_PKGDATADIR'] = remote_pkgdatadir
            self.rootfs_pre_scripts.append(script_cmd)

        if remote_pkgdatadir:
            self.pm = DnfRpm(self.workdir, self.target_rootfs, self.machine, remote_pkgdatadir)
        else:
            self.pm = DnfRpm(self.workdir, self.target_rootfs, self.machine)

        self.pm.create_configs()

        self.installed_pkgs = OrderedDict()

        utils.fake_root_set_passwd(self.target_rootfs)

        self.rootfs_post_scripts = []

    def _image_linguas_globs(self, image_linguas=""):
        logger.debug("image_linguas %s", image_linguas)
        if not image_linguas:
            return ""

        globs = ""
        split_linguas = set()

        for translation in image_linguas.split():
            split_linguas.add(translation)
            split_linguas.add(translation.split('-')[0])

        split_linguas = sorted(split_linguas)

        for lang in split_linguas:
            globs += " *-locale-%s" % lang

        logger.debug("globs %s", globs)
        return globs

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
            logger.debug("Executing '%s' preprocess rootfs..." % script)
            res, output = utils.run_cmd(script, shell=True)
            if res:
                raise Exception("Executing %s postprocess rootfs failed\nExit code %d. Output:\n%s"
                                   % (script, res, output))

    def _post_rootfs(self):
        for script in self.rootfs_post_scripts:
            logger.debug("Executing '%s' postprocess rootfs..." % script)
            res, output = utils.run_cmd(script, shell=True)
            if res:
                raise Exception("Executing %s postprocess rootfs failed\nExit code %d. Output:\n%s"
                                   % (script, res, output))

    def _save_installed(self):
        for k, v in self.pm.list_installed().items():
            self.installed_pkgs[k] = v

        with open(self.packages_yaml, "w") as f:
            utils.ordered_dump(self.installed_pkgs, f, Dumper=yaml.SafeDumper)
            logger.debug("Save Installed Packages Yaml File to : %s" % (self.packages_yaml))

    def create(self):
        self._pre_rootfs()

        self.pm.insert_feeds_uris(self.pkg_feeds, True if 'dnf' in self.packages else False)
        self.pm.update()
        self.pm.set_exclude(self.exclude_packages)
        self.pm.install(self.packages)
        self.pm.install_complementary(self.pkg_globs)

        #
        # We install external packages after packages been installed,
        # because we don't want complementary package logic apply to it.
        #
        duplicate_pkgs = set(self.pm.list_installed().keys()) & set(self.external_packages)
        explicit_duplicate_pkgs = set(self.packages) & set(self.external_packages)
        implicit_duplicate_pkgs = duplicate_pkgs - explicit_duplicate_pkgs
        if explicit_duplicate_pkgs:
            logger.warning("The following packages are specfied both in external-packages and packages: \n\t%s" % '\n\t'.join(sorted(explicit_duplicate_pkgs)))
        if implicit_duplicate_pkgs:
            logger.warning("The following packages are specfied in external-packages, but are brought in by dependencies of packages: \n\t%s" % '\n\t'.join(sorted(implicit_duplicate_pkgs)))
        self.pm.install(self.external_packages)
        self._save_installed()

        self.pm.run_intercepts()

        if 'dnf' in self.packages:
            self.pm.set_dnf_conf()

        self._post_rootfs()

        self._generate_kernel_module_deps()

    def image_list_installed_packages(self):
        return self.installed_pkgs

    def _check_for_kernel_modules(self, modules_dir):
        for root, dirs, files in os.walk(modules_dir, topdown=True):
            for name in files:
                found_ko = name.endswith(".ko")
                if found_ko:
                    return found_ko
        return False

    def _generate_kernel_module_deps(self):
        modules_dir = os.path.join(self.target_rootfs, 'lib', 'modules')
        # if we don't have any modules don't bother to do the depmod
        if not self._check_for_kernel_modules(modules_dir):
            logger.info("No Kernel Modules found, not running depmod")
            return

        for kernel_ver in os.listdir(modules_dir):
            if os.path.isdir(os.path.join(modules_dir, kernel_ver)):
                utils.run_cmd_oneshot("depmodwrapper -a -b {0} {1}".format(self.target_rootfs, kernel_ver))
