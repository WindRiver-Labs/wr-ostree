import logging
import os
import sys
import shutil
import subprocess
import collections
import hashlib
import re
import tempfile

from genimage.utils import set_logger
from genimage.constant import FEED_ARCHS_DICT
import genimage.utils as utils

logger = logging.getLogger('appsdk')

def failed_postinsts_abort(pkgs, log_path):
    logger.error("""Postinstall scriptlets of %s have failed. If the intention is to defer them to first boot,
then please place them into pkg_postinst_ontarget_${PN} ().
Deferring to first boot via 'exit 1' is no longer supported.
Details of the failure are in %s.""" %(pkgs, log_path))
    sys.exit(1)

class DnfRpm:
    def __init__(self,
                 workdir = os.path.join(os.getcwd(),"workdir"),
                 target_rootfs = os.path.join(os.getcwd(), "workdir/rootfs"),
                 machine = 'intel-x86-64'):

        self.workdir = workdir
        self.target_rootfs = target_rootfs
        
        self.temp_dir = os.path.join(workdir, "temp")
        utils.mkdirhier(self.target_rootfs)
        utils.mkdirhier(self.temp_dir)

        self.feed_archs= FEED_ARCHS_DICT.get(machine)

        self.package_seed_sign = False

        self.bad_recommendations = []
        self.package_exclude = []
        self.primary_arch = machine.replace('-', '_')
        self.machine = machine

        self.pkgdatadir = os.path.join(os.environ['OECORE_NATIVE_SYSROOT'], "usr/share/pkgdata", machine)
        self.oe_pkgdata_util = os.path.join(os.environ['OECORE_NATIVE_SYSROOT'], "usr/share/poky/scripts/oe-pkgdata-util")

        self._initialize_intercepts()

    def _initialize_intercepts(self):
        logger.debug("Initializing intercept dir for %s" % self.target_rootfs)
        # As there might be more than one instance of PackageManager operating at the same time
        # we need to isolate the intercept_scripts directories from each other,
        # hence the ugly hash digest in dir name.
        self.intercepts_dir = os.path.join(self.workdir, "intercept_scripts-%s" %
                                           (hashlib.sha256(self.target_rootfs.encode()).hexdigest()))

        postinst_intercepts_path = "%s/usr/share/poky/scripts/postinst-intercepts" % os.environ['OECORE_NATIVE_SYSROOT']
        postinst_intercepts = utils.which_wild('*', postinst_intercepts_path)

        logger.debug('Collected intercepts:\n%s' % ''.join('  %s\n' % i for i in postinst_intercepts))
        utils.remove(self.intercepts_dir, True)
        utils.mkdirhier(self.intercepts_dir)
        for intercept in postinst_intercepts:
            utils.copyfile(intercept, os.path.join(self.intercepts_dir, os.path.basename(intercept)))

    def _configure_dnf(self):
        # libsolv handles 'noarch' internally, we don't need to specify it explicitly
        archs = [i for i in reversed(self.feed_archs.split()) if i not in ["any", "all", "noarch"]]
        # This prevents accidental matching against libsolv's built-in policies
        if len(archs) <= 1:
            archs = archs + ["bogusarch"]
        # This architecture needs to be upfront so that packages using it are properly prioritized
        #archs = ["sdk_provides_dummy_target"] + archs
        confdir = "%s/%s" %(self.target_rootfs, "etc/dnf/vars/")
        utils.mkdirhier(confdir)
        open(confdir + "arch", 'w').write(":".join(archs))
        distro_codename = None
        open(confdir + "releasever", 'w').write(distro_codename if distro_codename is not None else '')

        open(os.path.join(self.target_rootfs, "etc/dnf/dnf.conf"), 'w').write("")


    def _configure_rpm(self):
        # We need to configure rpm to use our primary package architecture as the installation architecture,
        # and to make it compatible with other package architectures that we use.
        # Otherwise it will refuse to proceed with packages installation.
        platformconfdir = "%s/%s" %(self.target_rootfs, "etc/rpm/")
        rpmrcconfdir = "%s/%s" %(self.target_rootfs, "etc/")
        utils.mkdirhier(platformconfdir)
        open(platformconfdir + "platform", 'w').write("%s-pc-linux\n" % self.primary_arch)
        with open(rpmrcconfdir + "rpmrc", 'w') as f:
            f.write("arch_compat: %s: %s\n" % (self.primary_arch, self.feed_archs if len(self.feed_archs) > 0 else self.primary_arch))
            f.write("buildarch_compat: %s: noarch\n" % self.primary_arch)

        open(platformconfdir + "macros", 'w').write("%_transaction_color 7\n")
        open(platformconfdir + "macros", 'w').write("%_var /var\n")

        if self.machine == "intel-x86-64":
            open(platformconfdir + "macros", 'a').write("%_prefer_color 7\n")

    def create_configs(self):
        logger.debug("create_configs")
        self._configure_dnf()
        self._configure_rpm()

    def _prepare_pkg_transaction(self):
        os.environ['D'] = self.target_rootfs
        os.environ['OFFLINE_ROOT'] = self.target_rootfs
        os.environ['IPKG_OFFLINE_ROOT'] = self.target_rootfs
        os.environ['OPKG_OFFLINE_ROOT'] = self.target_rootfs
        os.environ['INTERCEPT_DIR'] = self.intercepts_dir
        os.environ['NATIVE_ROOT'] = os.environ['OECORE_NATIVE_SYSROOT']
        os.environ['RPM_NO_CHROOT_FOR_SCRIPTS'] = "1"

    def get_gpgkey(self):
        return None

    def insert_feeds_uris(self, remote_uris):
        from urllib.parse import urlparse

        gpg_opts = ''
        if self.package_seed_sign:
            gpg_opts += 'repo_gpgcheck=1\n'
            gpg_opts += 'gpgkey=file://etc/pki/packagefeed-gpg/%s\n' % (self.get_gpgkey())
        else:
            gpg_opts += 'gpgcheck=0\n'

        utils.mkdirhier(os.path.join(self.target_rootfs, "etc", "yum.repos.d"))
        for uri in remote_uris:
            repo_base = "oe-remote-repo" + "-".join(urlparse(uri).path.split("/"))
            repo_name = "OE Remote Repo:" + " ".join(urlparse(uri).path.split("/"))
            repo_uri = uri
            open(os.path.join(self.target_rootfs, "etc", "yum.repos.d", repo_base + ".repo"), 'w').write(
                    "[%s]\nname=%s\nbaseurl=%s\n%s" % (repo_base, repo_name, repo_uri, gpg_opts))

    def _invoke_dnf(self, dnf_args, fatal = True, print_output = True ):
        os.environ['RPM_ETCCONFIGDIR'] = self.target_rootfs
        dnf_cmd = shutil.which("dnf", path=os.getenv('PATH'))
        standard_dnf_args = ["-v", "--rpmverbosity=info", "-y",
                             "-c", os.path.join(self.target_rootfs, "etc/dnf/dnf.conf"),
                             "--setopt=reposdir=%s" %(os.path.join(self.target_rootfs, "etc/yum.repos.d")),
                             "--installroot=%s" % (self.target_rootfs),
                             "--setopt=logdir=%s" % (self.temp_dir)
                            ]
        if hasattr(self, "rpm_repo_dir"):
            standard_dnf_args.append("--repofrompath=oe-repo,%s" % (self.rpm_repo_dir))
        cmd = [dnf_cmd] + standard_dnf_args + dnf_args
        logger.debug('Running %s' % ' '.join(cmd))

        res, output = utils.run_cmd(cmd, print_output=print_output)
        if res:
            if print_output:
                (logger.info, logger.error)[fatal]("Could not invoke dnf. Command "
                     "'%s' returned %d:\n%s" % (' '.join(cmd), res, output))
            else:
                (logger.info, logger.error)[fatal]("Could not invoke dnf. Command "
                     "'%s' returned %d:" % (' '.join(cmd), res))

            raise Exception("Could not invoke dnf. Command "
                     "'%s' returned %d:\n%s" % (' '.join(cmd), res, output))

        return output

    def install(self, pkgs, attempt_only = False):
        logger.debug("dnf install: %s, attemplt %s" % (pkgs, attempt_only))
        if len(pkgs) == 0:
            return
        self._prepare_pkg_transaction()

        exclude_pkgs = (self.bad_recommendations.split() if self.bad_recommendations else [])
        exclude_pkgs += (self.package_exclude.split() if self.package_exclude else [])

        output = self._invoke_dnf((["--skip-broken"] if attempt_only else []) +
                         (["-x", ",".join(exclude_pkgs)] if len(exclude_pkgs) > 0 else []) +
                         (["--setopt=install_weak_deps=False"] if self.bad_recommendations else []) +
                         (["--nogpgcheck"] if not self.package_seed_sign else ["--setopt=gpgcheck=True"]) +
                         ["install"] +
                         pkgs)

        failed_scriptlets_pkgnames = collections.OrderedDict()
        for line in output.splitlines():
            if line.startswith("Error in POSTIN scriptlet in rpm package"):
                failed_scriptlets_pkgnames[line.split()[-1]] = True

        if len(failed_scriptlets_pkgnames) > 0:
            failed_postinsts_abort(list(failed_scriptlets_pkgnames.keys()),
                                   self.temp_dir)

    def remove(self, pkgs, with_dependencies = True):
        logger.debug("dnf remove: %s" % (pkgs))
        if not pkgs:
            return

        self._prepare_pkg_transaction()

        if with_dependencies:
            self._invoke_dnf(["remove"] + pkgs)
        else:
            cmd = shutil.which("rpm", path=os.getenv('PATH'))
            args = ["-e", "-v", "--nodeps", "--root=%s" %self.target_rootfs]
            logger.info("Running %s" % ' '.join([cmd] + args + pkgs))
            res, output = utils.run_cmd([cmd] + args + pkgs)
            if res:
                logger.error("Could not invoke rpm. Command "
                     "'%s' returned %d:\n%s" % (' '.join([cmd] + args + pkgs), res, output))
                raise Exception("Could not invoke rpm. Command "
                     "'%s' returned %d:\n%s" % (' '.join([cmd] + args + pkgs), res, output))


    def upgrade(self):
        self._prepare_pkg_transaction()
        self._invoke_dnf(["upgrade"])

    def autoremove(self):
        self._prepare_pkg_transaction()
        self._invoke_dnf(["autoremove"])

    def list_installed(self):
        output = self._invoke_dnf(["repoquery", "--installed", "--queryformat", "Package: %{name} %{arch} %{version} %{name}-%{version}-%{release}.%{arch}.rpm\nDependencies:\n%{requires}\nRecommendations:\n%{recommends}\nDependenciesEndHere:\n"],
                                  print_output = False)
        packages = {}
        current_package = None
        current_deps = None
        current_state = "initial"
        for line in output.splitlines():
            if line.startswith("Package:"):
                package_info = line.split(" ")[1:]
                current_package = package_info[0]
                package_arch = package_info[1]
                package_version = package_info[2]
                package_rpm = package_info[3]
                packages[current_package] = {"arch":package_arch, "ver":package_version, "filename":package_rpm}
                current_deps = []
            elif line.startswith("Dependencies:"):
                current_state = "dependencies"
            elif line.startswith("Recommendations"):
                current_state = "recommendations"
            elif line.startswith("DependenciesEndHere:"):
                current_state = "initial"
                packages[current_package]["deps"] = current_deps
            elif len(line) > 0:
                if current_state == "dependencies":
                    current_deps.append(line)
                elif current_state == "recommendations":
                    current_deps.append("%s [REC]" % line)

        return packages

    def update(self):
        self._invoke_dnf(["makecache", "--refresh"])

    def _script_num_prefix(self, path):
        files = os.listdir(path)
        numbers = set()
        numbers.add(99)
        for f in files:
            numbers.add(int(f.split("-")[0]))
        return max(numbers) + 1

    def save_rpmpostinst(self, pkg):
        logger.debug("Saving postinstall script of %s" % (pkg))
        cmd = shutil.which("rpm", path=os.getenv('PATH'))
        args = ["-q", "--root=%s" % self.target_rootfs, "--queryformat", "%{postin}", pkg]
        res, output = utils.run_cmd([cmd] + args)
        if res:
            logger.error("Could not invoke rpm. Command "
                     "'%s' returned %d:\n%s" % (' '.join([cmd] + args), res, output))
            raise Exception("Could not invoke rpm. Command "
                     "'%s' returned %d:\n%s" % (' '.join([cmd] + args), res, output))

        # may need to prepend #!/bin/sh to output

        target_path = os.path.join(self.target_rootfs, 'etc/rpm-postinsts/')
        utils.mkdirhier(target_path)
        num = self._script_num_prefix(target_path)
        saved_script_name = os.path.join(target_path, "%d-%s" % (num, pkg))
        open(saved_script_name, 'w').write(output)
        os.chmod(saved_script_name, 0o755)

    def _handle_intercept_failure(self, registered_pkgs):
        rpm_postinsts_dir = self.target_rootfs + '/etc/rpm-postinsts/'
        utils.mkdirhier(rpm_postinsts_dir)

        # Save the package postinstalls in /etc/rpm-postinsts
        for pkg in registered_pkgs.split():
            self.save_rpmpostinst(pkg)

    def _postpone_to_first_boot(self, postinst_intercept_hook):
        with open(postinst_intercept_hook) as intercept:
            registered_pkgs = None
            for line in intercept.read().split("\n"):
                m = re.match(r"^##PKGS:(.*)", line)
                if m is not None:
                    registered_pkgs = m.group(1).strip()
                    break

            if registered_pkgs is not None:
                logger.debug("If an image is being built, the postinstalls for the following packages "
                        "will be postponed for first boot: %s" %
                        registered_pkgs)

                # call the backend dependent handler
                self._handle_intercept_failure(registered_pkgs)

    def run_intercepts(self):
        intercepts_dir = self.intercepts_dir

        logger.debug("Running intercept scripts:")
        os.environ['D'] = self.target_rootfs
        os.environ['STAGING_DIR_NATIVE'] = os.environ['OECORE_NATIVE_SYSROOT']
        os.environ['libdir_native'] = "/usr/lib"

        for script in os.listdir(intercepts_dir):
            script_full = os.path.join(intercepts_dir, script)

            if script == "postinst_intercept" or not os.access(script_full, os.X_OK):
                continue

            # we do not want to run any multilib variant of this
            if script.startswith("delay_to_first_boot"):
                self._postpone_to_first_boot(script_full)
                continue

            logger.debug("> Executing %s intercept ..." % script)
            res, output = utils.run_cmd(script_full)
            if res:
                if "qemuwrapper: qemu usermode is not supported" in output:
                    logger.debug("The postinstall intercept hook '%s' could not be executed due to missing qemu usermode support, details in %s/%s"
                            % (script, self.temp_dir, "log.do_rootfs"))
                    self._postpone_to_first_boot(script_full)
                else:
                    logger.error("The postinstall intercept hook '%s' failed, details in %s/%s" % (script, self.temp_dir, "log.do_rootfs"))
                    raise Exception("The postinstall intercept hook '%s' failed, details in %s/%s" % (script, self.temp_dir, "log.do_rootfs"))

    def install_complementary(self, globs=None):
        """
        Install complementary packages based upon the list of currently installed
        packages e.g. *-src, *-dev, *-dbg, etc. This will only attempt to install
        these packages, if they don't exist then no error will occur.
        """
        if globs is None:
            return

        # we need to write the list of installed packages to a file because the
        # oe-pkgdata-util reads it from a file
        with tempfile.NamedTemporaryFile(mode="w+", prefix="installed-pkgs") as installed_pkgs:
            pkgs = self.list_installed()

            provided_pkgs = set()
            for pkg in pkgs.values():
                provided_pkgs |= set(pkg.get('provs', []))

            output = utils.format_pkg_list(pkgs, "arch")
            installed_pkgs.write(output)
            installed_pkgs.flush()

            cmd = [self.oe_pkgdata_util,
                   "-p", self.pkgdatadir, "glob", installed_pkgs.name,
                   globs]
            res, output = utils.run_cmd(cmd)
            if res:
                logger.error("Could not compute complementary packages list. Command "
                         "'%s' returned %d:\n%s" %
                         (' '.join(cmd), res, output))
                raise Exception("Could not invoke dnf. Command "
                         "'%s' returned %d:\n%s" % (' '.join(cmd), res, output))

            complementary_pkgs = set(output.split())
            skip_pkgs = sorted(complementary_pkgs & provided_pkgs)
            install_pkgs = sorted(complementary_pkgs - provided_pkgs)
            logger.debug("Installing complementary packages ... %s (skipped already provided packages %s)" % (
                ' '.join(install_pkgs),
                ' '.join(skip_pkgs)))
            self.install(install_pkgs, attempt_only=True)

def test():
    from genimage.constant import DEFAULT_PACKAGE_FEED
    from genimage.constant import DEFAULT_PACKAGES
    from genimage.constant import DEFAULT_MACHINE
    from genimage.constant import DEFAULT_IMAGE
    from genimage.utils import  fake_root

    logger = logging.getLogger('dnf')
    set_logger(logger)
    logger.setLevel(logging.DEBUG)

    fake_root()
    package = DEFAULT_PACKAGES[DEFAULT_MACHINE]
    pm = DnfRpm(machine=DEFAULT_MACHINE)
    pm.create_configs()
    pm.update()
    pm.insert_feeds_uris(DEFAULT_PACKAGE_FEED)
    pm.install(package)
    pm.install_complementary("*-src *-dev *-dbg")
    #pm.run_intercepts()
    #pm.install([p + '-doc' for p in package], attempt_only = True)
    #pm.remove(['grub-efi'])


if __name__ == "__main__":
    test()