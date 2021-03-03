import logging
import os
import sys
import shutil
import subprocess
import collections
import re
import tempfile

from genimage.utils import set_logger
from genimage.constant import FEED_ARCHS_DICT
from genimage.constant import DEFAULT_LOCAL_DEB_PACKAGE_FEED
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEB_PACKAGE_FEED_ARCHS
from genimage.package_manager import PackageManager
from genimage.package_manager import failed_postinsts_abort
import genimage.utils as utils
logger = logging.getLogger('appsdk')

def debian_arch_map(machine):
    if machine == "intel-x86-64":
        return "amd64"
    if machine == "bcm-2xxx-rpi4":
        return "arm64"
    return arch

def dpkg_query(cmd_output):
    """
    This method parse the output from the package managerand return
    a dictionary with the information of the packages. This is used
    when the packages are in deb format.
    """
    verregex = re.compile(r' \([=<>]* [^ )]*\)')
    output = dict()
    pkg = ""
    arch = ""
    ver = ""
    filename = ""
    dep = []
    prov = []
    pkgarch = ""
    for line in cmd_output.splitlines()+['']:
        line = line.rstrip()
        if ':' in line:
            if line.startswith("Package: "):
                pkg = line.split(": ")[1]
            elif line.startswith("Architecture: "):
                arch = line.split(": ")[1]
            elif line.startswith("Version: "):
                ver = line.split(": ")[1]
            elif line.startswith("File: ") or line.startswith("Filename:"):
                filename = line.split(": ")[1]
                if "/" in filename:
                    filename = os.path.basename(filename)
            elif line.startswith("Depends: "):
                depends = verregex.sub('', line.split(": ")[1])
                for depend in depends.split(", "):
                    dep.append(depend)
            elif line.startswith("Recommends: "):
                recommends = verregex.sub('', line.split(": ")[1])
                for recommend in recommends.split(", "):
                    dep.append("%s [REC]" % recommend)
            elif line.startswith("PackageArch: "):
                pkgarch = line.split(": ")[1]
            elif line.startswith("Provides: "):
                provides = verregex.sub('', line.split(": ")[1])
                for provide in provides.split(", "):
                    prov.append(provide)

        # When there is a blank line save the package information
        elif not line:
            # IPK doesn't include the filename
            if not filename:
                filename = "%s_%s_%s.ipk" % (pkg, ver, arch)
            if pkg:
                output[pkg] = {"arch":arch, "ver":ver,
                        "filename":filename, "deps": dep, "pkgarch":pkgarch, "provs": prov}
            pkg = ""
            arch = ""
            ver = ""
            filename = ""
            dep = []
            prov = []
            pkgarch = ""

    return output


class AptDeb(PackageManager):
    def __init__(self,
                 workdir = os.path.join(os.getcwd(),"workdir"),
                 target_rootfs = os.path.join(os.getcwd(), "workdir/rootfs"),
                 machine = 'intel-x86-64',
                 remote_pkgdatadir = None):

        super(AptDeb, self).__init__(workdir=workdir,
                                     target_rootfs=target_rootfs,
                                     machine=machine,
                                     remote_pkgdatadir=remote_pkgdatadir)

        self.apt_conf_dir = os.path.join(self.temp_dir, "apt")
        self.apt_conf_file = os.path.join(self.apt_conf_dir, "apt.conf")
        self.apt_get_cmd = shutil.which("apt-get", path=os.getenv('PATH'))
        self.apt_cache_cmd = shutil.which("apt-cache", path=os.getenv('PATH'))

        self.apt_args = os.getenv('APT_ARGS', '')

        self.all_arch_list = DEB_PACKAGE_FEED_ARCHS.split()

    def _configure_apt(self):
        base_archs = debian_arch_map(self.machine)
        base_archs = re.sub(r"_", r"-", base_archs)

        if os.path.exists(self.apt_conf_dir):
            utils.remove(self.apt_conf_dir, True)

        utils.mkdirhier(self.apt_conf_dir)
        utils.mkdirhier(self.apt_conf_dir + "/lists/partial/")
        utils.mkdirhier(self.apt_conf_dir + "/apt.conf.d/")
        utils.mkdirhier(self.apt_conf_dir + "/preferences.d/")

        arch_list = []
        for arch in self.all_arch_list:
            arch_list.append(arch)

        priority = 801
        for arch in arch_list:
            utils.write(
                os.path.join(self.apt_conf_dir, "preferences"), "w+",
                "Package: *\n"
                "Pin: release l=%s\n"
                "Pin-Priority: %d\n\n" % (arch, priority))

            priority += 5

        arch_list.reverse()

        base_arch_list = base_archs.split()

        apt_conf_sample_dir = os.path.join(os.environ['OECORE_NATIVE_SYSROOT'], "etc/apt/apt.conf.sample")
        with open(apt_conf_sample_dir) as apt_conf_sample:
            for line in apt_conf_sample.read().split("\n"):
                match_arch = re.match(r"  Architecture \".*\";$", line)
                architectures = ""
                if match_arch:
                    for base_arch in base_arch_list:
                        architectures += "\"%s\";" % base_arch
                    utils.write(self.apt_conf_file, "w+", "  Architectures {%s};" % architectures)
                    utils.write(self.apt_conf_file, "w+", "  Architecture \"%s\";" % base_archs)
                else:
                    line = re.sub(r"#ROOTFS#", self.target_rootfs, line)
                    line = re.sub(r"#APTCONF#", self.apt_conf_dir, line)
                    line = re.sub(r"Dir .*", "Dir \"%s\"" % os.environ['OECORE_NATIVE_SYSROOT'], line)
                    line = re.sub(r"Bin .*", "Bin \"%s/usr/bin\"" % os.environ['OECORE_NATIVE_SYSROOT'], line)
                    line = re.sub(r"methods .*", "methods \"%s/usr/lib/apt/methods\";" % os.environ['OECORE_NATIVE_SYSROOT'], line)
                    utils.write(self.apt_conf_file, "w+", line)

        target_dpkg_dir = "%s/var/lib/dpkg" % self.target_rootfs
        utils.mkdirhier(os.path.join(target_dpkg_dir, "info"))

        utils.mkdirhier(os.path.join(target_dpkg_dir, "updates"))

        if not os.path.exists(os.path.join(target_dpkg_dir, "status")):
            utils.write(os.path.join(target_dpkg_dir, "status"))
        if not os.path.exists(os.path.join(target_dpkg_dir, "available")):
            utils.write(os.path.join(target_dpkg_dir, "available"))

        utils.mkdirhier(os.path.join("%s/etc/apt" % self.target_rootfs))

    def create_configs(self):
        super(AptDeb, self).create_configs()
        self._configure_apt()

    def insert_feeds_uris(self, remote_uris, save_repo=True):
        super(AptDeb, self).insert_feeds_uris(remote_uris, save_repo)

        for uri in remote_uris:
            uri_has_suite = len(uri.strip().split()) > 1
            if save_repo:
                if not uri_has_suite:
                    utils.write(os.path.join("%s/etc/apt/sources.list" % self.target_rootfs), 'w+', "deb [trusted=yes] %s ./\n" % uri)
                else:
                    utils.write(os.path.join("%s/etc/apt/sources.list" % self.target_rootfs), 'w+', "deb [trusted=yes] %s\n" % uri)

            if utils.is_sdk():
                if not uri_has_suite:
                    utils.write(os.path.join(self.apt_conf_dir, "sources.list"), 'w+', "deb %s ./\n" % uri)
                else:
                    utils.write(os.path.join(self.apt_conf_dir, "sources.list"), 'w+', "deb [trusted=yes] %s\n" % uri)

            # For native build
            elif utils.is_build():
                # Do not use remote package repo to generate image
                if self.remote_pkgdatadir and uri.startswith(self.remote_pkgdatadir):
                    continue

                # Use third party repo to generate image
                if not uri_has_suite:
                    utils.write(os.path.join(self.apt_conf_dir, "sources.list"), 'w+', "deb %s ./\n" % uri)
                else:
                    utils.write(os.path.join(self.apt_conf_dir, "sources.list"), 'w+', "deb [trusted=yes] %s\n" % uri)

        if utils.is_build():
            for uri in DEFAULT_LOCAL_DEB_PACKAGE_FEED:
                if not uri_has_suite:
                    utils.write(os.path.join(self.apt_conf_dir, "sources.list"), 'a+', "deb %s ./\n" % uri)
                else:
                    utils.write(os.path.join(self.apt_conf_dir, "sources.list"), 'a+', "deb [trusted=yes] %s\n" % uri)
                    
    def set_exclude(self, package_exclude = None):
        if not package_exclude:
            return

        self.package_exclude.extend(package_exclude)
        self.package_exclude = list(set(self.package_exclude))
        logger.debug("Set Exclude Packages: %s", self.package_exclude)
        for pkg in self.package_exclude:
            utils.write(
                os.path.join(self.apt_conf_dir, "preferences"), "w+",
                "Package: %s\n"
                "Pin: release *\n"
                "Pin-Priority: -1\n\n" % pkg)

    def _invoke_apt(self, subcmd, subcmd_args, attempt_only=False):
        os.environ['APT_CONFIG'] = self.apt_conf_file
        cmd = "%s %s %s %s" % \
              (self.apt_get_cmd, self.apt_args, subcmd, subcmd_args)

        logger.debug('Running %s' % cmd)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode("utf-8")
            logger.debug('%s' % output)
        except subprocess.CalledProcessError as e:
            if attempt_only:
                logger.debug("Could not invoke apt. Command '%s' "
                             "returned %d:\n%s" % (e.cmd, e.returncode, e.output.decode("utf-8")))
            else:
                raise Exception("Could not invoke apt. Command '%s' "
                         "returned %d:\n%s" % (e.cmd, e.returncode, e.output.decode("utf-8")))
        return output

    def install(self, pkgs, attempt_only=False):
        os.environ['APT_CONFIG'] = self.apt_conf_file

        logger.debug("apt install: %s, attemplt %s" % (pkgs, attempt_only))
        if len(pkgs) == 0:
            return

        subcmd_args = "--allow-downgrades --allow-remove-essential --allow-change-held-packages --allow-unauthenticated --no-remove %s" % \
              (' '.join(pkgs))

        logger.debug("Installing the following packages: %s" % ' '.join(pkgs))
        self._invoke_apt("install", subcmd_args, attempt_only)

        # rename *.dpkg-new files/dirs
        for root, dirs, files in os.walk(self.target_rootfs):
            for d in dirs:
                new_dir = re.sub(r"\.dpkg-new", "", d)
                if d != new_dir:
                    cmd = "mv %s %s" % (d, new_dir)
                    utils.run_cmd_oneshot(cmd, cwd=root)
            for f in files:
                new_file = re.sub(r"\.dpkg-new", "", f)
                if f != new_file:
                    cmd = "mv %s %s" % (f, new_file)
                    utils.run_cmd_oneshot(cmd, cwd=root)

        self._fix_broken_dependencies()

    def remove(self, pkgs, with_dependencies = True):
        logger.debug("remove: %s" % (pkgs))
        if not pkgs:
            return

        os.environ['INTERCEPT_DIR'] = self.intercepts_dir

        if with_dependencies:
            os.environ['APT_CONFIG'] = self.apt_conf_file
            cmd = "%s purge %s" % (self.apt_get_cmd, ' '.join(pkgs))
        else:
            cmd = "%s --admindir=%s/var/lib/dpkg --instdir=%s" \
                  " -P --force-depends %s" % \
                  (shutil.which("dpkg", path=os.getenv('PATH')),
                   self.target_rootfs, self.target_rootfs, ' '.join(pkgs))

        try:
            output = subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT).decode("utf-8")
            logger.debug(output)
        except subprocess.CalledProcessError as e:
            raise Exception("Unable to remove packages. Command '%s' "
                     "returned %d:\n%s" % (e.cmd, e.returncode, e.output.decode("utf-8")))

    def list_installed(self):
        cmd = [shutil.which("dpkg-query", path=os.getenv('PATH')),
               "--admindir=%s/var/lib/dpkg" % self.target_rootfs,
               "-W"]

        cmd.append("-f=Package: ${Package}\nArchitecture: ${PackageArch}\nVersion: ${Version}\nFile: ${Package}_${Version}_${Architecture}.deb\nDepends: ${Depends}\nRecommends: ${Recommends}\nProvides: ${Provides}\n\n")

        try:
            cmd_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).strip().decode("utf-8")
        except subprocess.CalledProcessError as e:
            Exception("Cannot get the installed packages list. Command '%s' "
                     "returned %d:\n%s" % (' '.join(cmd), e.returncode, e.output.decode("utf-8")))

        return dpkg_query(cmd_output)

    def update(self):
        os.environ['APT_CONFIG'] = self.apt_conf_file
        cmd = "%s update" % self.apt_get_cmd

        try:
            subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise Exception("Unable to update the package index files. Command '%s' "
                     "returned %d:\n%s" % (e.cmd, e.returncode, e.output.decode("utf-8")))

    def post_install(self):
        self._mark_packages("installed")
        self._run_pre_post_installs()

    def _fix_broken_dependencies(self):
        logger.debug("fix_broken_dependencies")
        os.environ['APT_CONFIG'] = self.apt_conf_file

        cmd = "%s %s --allow-unauthenticated -f install" % (self.apt_get_cmd, self.apt_args)

        try:
            subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise Exception("Cannot fix broken dependencies. Command '%s' "
                     "returned %d:\n%s" % (cmd, e.returncode, e.output.decode("utf-8")))

    def _run_pre_post_installs(self, package_name=None):
        """
        Run the pre/post installs for package "package_name". If package_name is
        None, then run all pre/post install scriptlets.
        """
        logger.debug("run_pre_post_installs")
        info_dir = self.target_rootfs + "/var/lib/dpkg/info"
        ControlScript = collections.namedtuple("ControlScript", ["suffix", "name", "argument"])
        control_scripts = [
                ControlScript(".preinst", "Preinstall", "install"),
                ControlScript(".postinst", "Postinstall", "configure")]
        status_file = self.target_rootfs + "/var/lib/dpkg/status"
        installed_pkgs = []

        with open(status_file, "r") as status:
            for line in status.read().split('\n'):
                m = re.match(r"^Package: (.*)", line)
                if m is not None:
                    installed_pkgs.append(m.group(1))

        if package_name is not None and not package_name in installed_pkgs:
            return

        os.environ['D'] = self.target_rootfs
        os.environ['OFFLINE_ROOT'] = self.target_rootfs
        os.environ['IPKG_OFFLINE_ROOT'] = self.target_rootfs
        os.environ['OPKG_OFFLINE_ROOT'] = self.target_rootfs
        os.environ['INTERCEPT_DIR'] = self.intercepts_dir
        os.environ['NATIVE_ROOT'] = os.environ['OECORE_NATIVE_SYSROOT']

        for pkg_name in installed_pkgs:
            for control_script in control_scripts:
                p_full = os.path.join(info_dir, pkg_name + control_script.suffix)
                if os.path.exists(p_full):
                    try:
                        logger.debug("Executing %s for package: %s ..." %
                                 (control_script.name.lower(), pkg_name))
                        output = subprocess.check_output([p_full, control_script.argument],
                                stderr=subprocess.STDOUT).decode("utf-8")
                        logger.debug(output)
                    except subprocess.CalledProcessError as e:
                        logger.warning("%s for package %s failed with %d:\n%s" %
                                (control_script.name, pkg_name, e.returncode,
                                    e.output.decode("utf-8")))
                        failed_postinsts_abort([pkg_name], self.temp_dir)

    def _mark_packages(self, status_tag, packages=None):
        """
        This function will change a package's status in /var/lib/dpkg/status file.
        If 'packages' is None then the new_status will be applied to all
        packages
        """
        logger.debug("mark_packages")

        status_file = self.target_rootfs + "/var/lib/dpkg/status"

        with open(status_file, "r") as sf:
            with open(status_file + ".tmp", "w+") as tmp_sf:
                if packages is None:
                    tmp_sf.write(re.sub(r"Package: (.*?)\n((?:[^\n]+\n)*?)Status: (.*)(?:unpacked|installed)",
                                        r"Package: \1\n\2Status: \3%s" % status_tag,
                                        sf.read()))
                else:
                    if type(packages).__name__ != "list":
                        raise TypeError("'packages' should be a list object")

                    status = sf.read()
                    for pkg in packages:
                        status = re.sub(r"Package: %s\n((?:[^\n]+\n)*?)Status: (.*)(?:unpacked|installed)" % pkg,
                                        r"Package: %s\n\1Status: \2%s" % (pkg, status_tag),
                                        status)

                    tmp_sf.write(status)

            utils.run_cmd_oneshot("mv %s.tmp %s" % (status_file, status_file))

    def _handle_intercept_failure(self, registered_pkgs):
        logger.debug("_handle_intercept_failure")
        self._mark_packages("unpacked", registered_pkgs.split())


def test():
    from genimage.constant import DEFAULT_RPM_PACKAGE_FEED
    from genimage.constant import DEFAULT_PACKAGES, DEFAULT_CONTAINER_PACKAGES
    from genimage.constant import DEFAULT_MACHINE
    from genimage.constant import DEFAULT_IMAGE
    from genimage.utils import  fake_root

    logger = logging.getLogger('appsdk')
    set_logger(logger)
    logger.setLevel(logging.DEBUG)

    fake_root()
    utils.fake_root_set_passwd(os.environ['OECORE_NATIVE_SYSROOT'])
    package = DEFAULT_PACKAGES[DEFAULT_MACHINE]
    #package = DEFAULT_CONTAINER_PACKAGES
    pm = AptDeb(machine=DEFAULT_MACHINE)
    pm.create_configs()
    pm.insert_feeds_uris(DEFAULT_RPM_PACKAGE_FEED)
    #pm.set_exclude(["systemd"])
    pm.update()
    pm.install(package)
    #pm._fix_broken_dependencies()
    #pm.install_complementary("*-src *-dev *-dbg")

    pm._fix_broken_dependencies()
    pm._mark_packages("installed")
    pm._run_pre_post_installs()
    pm.run_intercepts()
    #pm.install([p + '-doc' for p in package], attempt_only = True)
    pm.remove(['grub-efi'])
    pm.remove(['gzip'], with_dependencies=False)


if __name__ == "__main__":
    test()
