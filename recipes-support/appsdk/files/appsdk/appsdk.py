#!/usr/bin/env python3

import os
import sys
import stat
import shutil
import subprocess
import re
import glob
import logging
import yaml

from create_full_image.utils import set_logger
from create_full_image.utils import run_cmd
from create_full_image.utils import FEED_ARCHS_DICT
from create_full_image.rootfs import Rootfs
import create_full_image.utils as utils

logger = logging.getLogger('appsdk')

class AppSDK(object):
    """
    AppSDK
    """
    def __init__(self, sdk_output=None, sdkpath=None, deploy_dir=None, sdk_name=None, distro_name="windriver"):
        self.distro_name = distro_name
        if sdk_output != None:
            self.sdk_output = sdk_output
        else:
            # default to "./workdir-sdk"
            self.sdk_output = os.path.join(os.getcwd(), 'workdir-sdk')
        if sdkpath != None:
            self.sdkpath = sdkpath
        else:
            # default to /opt/DISTRO_NAME/appsdk
            self.sdkpath = os.path.join("/opt", self.distro_name, "appsdk")
        logger.debug("sdk_output = {0}, sdkpath={1}".format(self.sdk_output, self.sdkpath))

        if deploy_dir != None:
            self.deploy_dir = deploy_dir
        else:
            # default to "./deploy"
            self.deploy_dir = os.path.join(os.getcwd(), 'deploy')

        if sdk_name != None:
            self.sdk_name = sdk_name
        else:
            # default to "AppSDK"
            self.sdk_name = "AppSDK"

        self.real_multimach_target_sys = os.path.basename(os.environ['OECORE_TARGET_SYSROOT'])
        # current native sysroot dir
        self.native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
        self.data_dir = os.path.join(self.native_sysroot, "usr/share/create_full_image/data")
        self.sdk_sys = os.path.basename(self.native_sysroot)
        self.target_sdk_dir = os.path.dirname(os.path.dirname(self.native_sysroot))
        # new sdk's sysroot dirs
        self.native_sysroot_dir = os.path.abspath(self.sdk_output + '/' + self.sdkpath + '/sysroots/' + self.sdk_sys)

    def generate_sdk(self, target_image_yaml, output_sdk_path = None):
        """
        Generate sdk according to target_image_yaml.
        If output_sdk_path is not specified, use the default one.
        """
        # Check if target_image_yaml exists
        if not os.path.exists(target_image_yaml):
            logger.error("{0} does not exists!".format(target_image_yaml))
            exit(1)
        # Compute self.deploy_dir and self.sdk_name
        if output_sdk_path:
            self.deploy_dir = os.path.dirname(os.path.abspath(output_sdk_path))
            self.sdk_name = os.path.basename(output_sdk_path).split('.sh')[0]
        self.populate_native_sysroot()
        self.populate_target_sysroot(target_image_yaml)
        self.create_sdk_files()
        self.archive_sdk()
        self.create_shar()
        logger.info("New SDK successfully generated: {0}/{1}.sh".format(self.deploy_dir, self.sdk_name))

    def check_sdk(self):
        """
        Sanity check of SDK
        """
        logger.info("Doing sanity check for SDK")
        # Check if relocation is correct in binaries
        ld_path = os.path.join(self.native_sysroot, 'lib/ld-linux-x86-64.so.2')
        if not os.path.exists(ld_path):
            logger.error("SDK Sanity Error: {0} does not exists!".format(ld_path))
            exit(1)
        bin_globs = "{0}/bin/* {0}/usr/bin/*".format(self.native_sysroot).split()
        known_lists = "{0}/bin/gunzip.gzip".format(self.native_sysroot).split()
        binary_file_to_check = None
        for bg in bin_globs:
            for f in glob.glob(bg):
                if not os.path.islink(f) and not os.path.isdir(f) and not f in known_lists:
                    binary_file_to_check = f
                    break
            if binary_file_to_check:
                break
        if not binary_file_to_check:
            logger.error("SDK Sanity Error: {0} does not contain any binaries under /bin and /usr/bin".format(self.native_sysroot))
            exit(1)
        logger.debug("{0} --list {1}".format(ld_path, binary_file_to_check))
        ld_list_cmd = "{0} --list {1}".format(ld_path, binary_file_to_check)
        output = subprocess.check_output(ld_list_cmd, shell=True).decode('utf-8')
        expected_line = "libc.so.6 => {0}/lib/libc.so.6".format(self.native_sysroot)
        if expected_line not in output:
            logger.error("SDK Sanity Error: {0} has relocation problem.".format(binary_file_to_check))
            exit(1)
            
        logger.info("SDK Sanity OK")

    def populate_target_sysroot(self, target_packages_yaml):
        """
        Populate target sysroot sdk_output/sdkpath/sysroots/corei7-64-wrs-linux/
        according to target_packages_yaml
        """
        target_sysroot_dir = os.path.abspath(self.sdk_output + '/' + self.sdkpath + '/sysroots/' + self.real_multimach_target_sys)
        logger.info("Constructing target sysroot '%s'" % target_sysroot_dir)
        if os.path.exists(target_sysroot_dir):
            shutil.rmtree(target_sysroot_dir)
        os.makedirs(target_sysroot_dir)

        # parse yaml file to get the list of packages to be installed
        with open(target_packages_yaml) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            self.image_name = data['name']
            self.machine = data['machine'] 
            self.packages = data['packages']
            self.pkg_feeds = data['package_feeds']
            self.image_features = data['features']

        # qemuwrapper-cross is always needed
        self.packages.append('qemuwrapper-cross')
            
        # prepare pseudo environment
        utils.fake_root(logger)
        
        # install packages into target sysroot dir
        rootfs = Rootfs(self.sdk_output,
                        self.data_dir,
                        self.machine,
                        self.pkg_feeds,
                        self.packages,
                        logger,
                        target_rootfs=target_sysroot_dir,
                        pkg_globs="*-src *-dev *-dbg")

        rootfs.create()

        # Turn absolute links into relative ones
        sysroot_relativelinks_py = os.path.join(self.native_sysroot, 'usr/share/poky/scripts/sysroot-relativelinks.py')
        cmd = "%s %s >/dev/null" % (sysroot_relativelinks_py, target_sysroot_dir)
        logger.info("Running %s ..." % cmd)
        subprocess.check_call(cmd, shell=True)
        logger.info("Finished populating target sysroot")

    def populate_native_sysroot(self):
        """
        Populate native sysroot.
        It's basically a copy of OECORE_NATIVE_SYSROOT, with relocations performed.
        """
        
        logger.info("Constructing native sysroot '%s'" % self.native_sysroot_dir)
        if os.path.exists(self.native_sysroot_dir):
            shutil.rmtree(self.native_sysroot_dir)

        # copy the whole native sysroot
        shutil.copytree(self.native_sysroot, self.native_sysroot_dir, symlinks=True, ignore_dangling_symlinks=True)

        # do relocation, self.target_sdk_dir -> self.sdkpath
        # self.target_sdk_dir is the old prefix, self.sdkpath is the newprefix
        relocate_tmpl_path = os.path.join(self.native_sysroot, 'usr/share/poky/scripts/relocate_sdk.py')
        if not os.path.exists(relocate_tmpl_path):
            logger.error("%s does not exist!" % relocate_tmpl_path)
            raise
        relocate_script_path = os.path.join(self.sdk_output, 'relocate_sdk.py')
        shutil.copyfile(relocate_tmpl_path, relocate_script_path)
        cmd = "sed -i -e 's:##DEFAULT_INSTALL_DIR##:{0}:' {1}".format(self.target_sdk_dir, relocate_script_path)
        subprocess.check_call(cmd, shell=True)
        # create relocate_sdk.sh to do the job to avoid arugment list too long error
        relocate_sh_path = os.path.join(self.sdk_output, 'relocate_sdk.sh')
        cmds = ["#!/bin/bash\n"]
        cmds.append("new_prefix={0}\n".format(self.sdkpath))
        cmds.append("new_dl_path={0}/sysroots/{1}/lib/ld-linux-x86-64.so.2\n".format(self.sdkpath, self.sdk_sys))
        cmds.append('executable_files=$(find {0} -type f \( -perm -0100 -o -perm -0010 -o -perm -0001 \) -printf "%h/%f ")\n'.format(self.native_sysroot_dir))
        cmds.append("python3 {0} $new_prefix $new_dl_path $executable_files\n".format(relocate_script_path))
        with open(relocate_sh_path, 'w') as f:
            f.writelines(cmds)
        os.chmod(relocate_sh_path, 0o755)
        subprocess.check_call('%s' % relocate_sh_path, shell=True)

        # remove the relocation script
        os.unlink(relocate_script_path)
        os.unlink(relocate_sh_path)

        # change symlinks point to $target_sdk_dir to point to $SDKPATH
        self._change_symlinks(self.native_sysroot_dir, self.target_sdk_dir, self.sdkpath)

        # change all text files from $target_sdk_dir to $SDKPATH
        logger.debug("Replacing text files from {0} to {1}".format(self.target_sdk_dir, self.sdkpath))
        self.replace_text_files(self.native_sysroot_dir, self.target_sdk_dir, self.sdkpath)
        
        logger.info("Finished populating native sysroot")

    def replace_text_files(self, rootdir, oldprefix, newprefix, extra_args=""):
        replace_sh_path = self._construct_replace_sh(rootdir, oldprefix, newprefix, extra_args)
        subprocess.check_call('%s' % replace_sh_path, shell=True)

    def _construct_replace_sh(self, rootdir, oldprefix, newprefix, extra_args):
        cmds = """
#!/bin/bash

find {0} {1} -type f | xargs -n100 file | grep ":.*\(ASCII\|script\|source\).*text" | \
    awk -F':' '{left}printf "\\"{4}\\"{newline}", $1{right}' | \
    xargs -n100 sed -i \
        -e "s:{2}:{3}:g"
""".format(rootdir, extra_args, oldprefix, newprefix, '%s', left = '{', right = '}', newline = '\\n')

        replace_sh_path = os.path.join(self.sdk_output, 'replace.sh')
        with open(replace_sh_path, 'w') as f:
            f.write(cmds)
        os.chmod(replace_sh_path, 0o755)
        return replace_sh_path
        
    def _change_symlinks(self, rootdir, old, new):
        """
        Change symlinks under rootdir, replacing the old with new
        """
        for dirPath,subDirEntries,fileEntries in os.walk(rootdir, followlinks=False):
            for e in fileEntries:
                ep = os.path.join(dirPath, e)
                if not os.path.islink(ep):
                    continue
                target_path = os.readlink(ep)
                if not os.path.isabs(target_path):
                    continue
                # ep is a symlink and its target path is abs path
                if old in target_path:
                    new_target_path = target_path.replace(old, new)
                    #logger.debug("%s -> %s" % (ep, new_target_path))
                    os.unlink(ep)
                    os.symlink(new_target_path, ep)

    def create_sdk_files(self):
        """
        Create SDK files.
        Mostly it's a copy of the current SDK, with path modifications.
        """
        logger.info("Creating sdk files")
        # copy site-config-*, version-*, environment-setup-*
        # from self.target_sdk_dir to self.sdk_output/self.sdkpath
        file_globs = "{0}/site-config-* {0}/version-* {0}/environment-setup-*".format(self.target_sdk_dir).split()
        for fg in file_globs:
            for file_path in glob.glob(fg):
                file_basename = os.path.basename(file_path)
                file_dst = self.sdk_output + self.sdkpath + '/' + file_basename
                shutil.copyfile(file_path, file_dst)

        # replace paths in environment-setup-*
        # self.target_sdk_dir -> self.sdkpath
        self.replace_text_files(self.sdk_output + self.sdkpath, self.target_sdk_dir, self.sdkpath, extra_args = "-maxdepth 1")

        # create relocate_sdk.py under sdk_output/sdkpath
        relocate_sdk_tmpl = os.path.join(self.native_sysroot, "usr/share/poky/scripts/relocate_sdk.py")
        relocate_sdk_dst = self.sdk_output + self.sdkpath + '/relocate_sdk.py'
        shutil.copyfile(relocate_sdk_tmpl, relocate_sdk_dst)
        cmd = 'sed -i -e "s:##DEFAULT_INSTALL_DIR##:{0}:" {1}'.format(self.sdkpath, relocate_sdk_dst)
        subprocess.check_call(cmd, shell=True)

        # we don't need to create ld.so.conf as the contents are correct already. This is because we copy the original ld.so.conf and replace the paths in it in populate_native_sysroot()
        logger.info("Finished creating sdk files")

    def archive_sdk(self):
        """
        Archive sdk
        """
        if not os.path.exists(self.deploy_dir):
            os.makedirs(self.deploy_dir)
        logger.info("Archiving sdk from {0}{1} to {2}/{3}.tar.gz".format(self.sdk_output, self.sdkpath, self.deploy_dir, self.sdk_name))
        sdk_archive_cmd = 'cd {0}/{1}; tar --owner=root --group=root -cf - . | xz --memlimit=50% --threads=40 -9 > {2}/{3}.tar.gz'.format(self.sdk_output, self.sdkpath, self.deploy_dir, self.sdk_name)
        subprocess.check_call(sdk_archive_cmd, shell=True)
        logger.info("Finished archiving sdk to {0}/{1}.tar.gz".format(self.deploy_dir, self.sdk_name))

    def _get_sdk_var_dict(self):
        var_dict = {}
        var_dict['SDK_ARCH'] = 'x86_64'
        var_dict['SDKPATH'] = self.sdkpath
        var_dict['SDKEXTPATH'] = '~/wrlinux_appsdk'
        var_dict['OLDEST_KERNEL'] = '3.2.0'
        var_dict['REAL_MULTIMACH_TARGET_SYS'] = self.real_multimach_target_sys
        var_dict['SDK_TITLE'] = 'Wind River AppSDK'
        var_dict['SDK_VERSION'] = ''
        var_dict['SDK_GCC_VER'] = ''
        var_dict['SDK_ARCHIVE_TYPE'] = 'tar.gz'
        
        return var_dict
        
    def create_shar(self):
        """
        Create sh installer for SDK
        It's the installation script + sdk archive
        """
        # copy the template shar extractor script to AppSDK.sh
        shar_extract_tmpl = os.path.join(self.native_sysroot, 'usr/share/poky/meta/files/toolchain-shar-extract.sh')
        if not os.path.exists(shar_extract_tmpl):
            logger.error("{0} does not exist".format(shar_extract_tmpl))
            raise
        shar_extract_sh = self.deploy_dir + '/' + self.sdk_name + '.sh'
        shutil.copyfile(shar_extract_tmpl, shar_extract_sh)

        # copy relocation script to post_install_command
        shar_relocate_tmpl = os.path.join(self.native_sysroot, 'usr/share/poky/meta/files/toolchain-shar-relocate.sh')
        if not os.path.exists(shar_relocate_tmpl):
            logger.error("{0} does not exist".format(shar_extract_tmpl))
            raise
        post_install_command_path = self.sdk_output + '/post_install_command'
        shutil.copyfile(shar_relocate_tmpl, post_install_command_path)

        # create pre_install_command as a placeholder
        pre_install_command_path = self.sdk_output + '/pre_install_command'
        with open(pre_install_command_path, 'w') as f:
            pass

        # substitute SDK_PRE/POST_INSTALL_COMMAND
        sed_cmd = "sed -i -e '/@SDK_PRE_INSTALL_COMMAND@/r {0}' -e '/@SDK_POST_INSTALL_COMMAND@/r {1}' {2}".format(
            pre_install_command_path, post_install_command_path, shar_extract_sh)
        subprocess.check_call(sed_cmd, shell=True)

        # substitute VARS like SDK_ARCH
        var_dict = self._get_sdk_var_dict()
        sed_cmd = """
        sed -i -e 's#@SDK_ARCH@#{SDK_ARCH}#g' \
                -e 's#@SDKPATH@#{SDKPATH}#g' \
                -e 's#@SDKEXTPATH@#{SDKEXTPATH}#g' \
                -e 's#@OLDEST_KERNEL@#{OLDEST_KERNEL}#g' \
                -e 's#@REAL_MULTIMACH_TARGET_SYS@#{REAL_MULTIMACH_TARGET_SYS}#g' \
                -e 's#@SDK_TITLE@#{SDK_TITLE}#g' \
                -e 's#@SDK_VERSION@#{SDK_VERSION}#g' \
                -e '/@SDK_PRE_INSTALL_COMMAND@/d' \
                -e '/@SDK_POST_INSTALL_COMMAND@/d' \
                -e 's#@SDK_GCC_VER@#{SDK_GCC_VER}#g' \
                -e 's#@SDK_ARCHIVE_TYPE@#{SDK_ARCHIVE_TYPE}#g' \
                {shar_extract_sh}
        """.format(
            SDK_ARCH = var_dict['SDK_ARCH'],
            SDKPATH = var_dict['SDKPATH'],
            SDKEXTPATH = var_dict['SDKEXTPATH'],
            OLDEST_KERNEL = var_dict['OLDEST_KERNEL'],
            REAL_MULTIMACH_TARGET_SYS = var_dict['REAL_MULTIMACH_TARGET_SYS'],
            SDK_TITLE = var_dict['SDK_TITLE'],
            SDK_VERSION = var_dict['SDK_VERSION'],
            SDK_GCC_VER = var_dict['SDK_GCC_VER'],
            SDK_ARCHIVE_TYPE = var_dict['SDK_ARCHIVE_TYPE'],
            shar_extract_sh = shar_extract_sh)
        subprocess.check_call(sed_cmd, shell=True)

        # chmod 755
        os.chmod(shar_extract_sh, 0o755)

        # append sdk archive
        sdk_archive_path = self.deploy_dir + '/' + self.sdk_name + '.tar.gz'
        with open(sdk_archive_path, 'rb') as rf:
            with open(shar_extract_sh, 'ab') as wf:
                shutil.copyfileobj(rf, wf)

        # delete the old archive
        os.unlink(sdk_archive_path)

        logger.info("Finished creating shar {0}".format(shar_extract_sh))
        
    def check_sdk_target_sysroots(self):
        """
        Check if there are broken or dangling symlinks in SDK sysroots
        """
        def norm_path(path):
            return os.path.abspath(path)

        # Get scan root
        SCAN_ROOT = norm_path("%s/%s/sysroots/%s" % (self.sdk_output, self.sdkpath, self.real_multimach_target_sys))
        logger.info('Checking SDK sysroots at ' + SCAN_ROOT)

        def check_symlink(linkPath):
            if not os.path.islink(linkPath):
                return

            # whitelist path patterns that are known to have problem
            whitelist_patterns = ["/etc/mtab",
                                  "/var/lock",
                                  "/etc/resolv-conf.systemd",
                                  "/etc/resolv.conf",
                                  "/etc/udev/rules.d/80-net-setup-link.rules",
                                  "/etc/tmpfiles.d/.*.conf",
                                  "/etc/systemd/network/80-wired.network",
                                  ".*\.patch",
                                  "/etc/ld.so.cache"]
            for wp in whitelist_patterns:
                if re.search(wp, linkPath):
                    return
            
            # Compute the target path of the symlink
            linkDirPath = os.path.dirname(linkPath)
            targetPath = os.readlink(linkPath)
            if not os.path.isabs(targetPath):
                targetPath = os.path.join(linkDirPath, targetPath)
            targetPath = norm_path(targetPath)

            if SCAN_ROOT != os.path.commonprefix( [SCAN_ROOT, targetPath] ):
                logger.warning("Escaping symlink {0!s} --> {1!s}".format(linkPath, targetPath))
                return

            if not os.path.exists(targetPath):
                logger.warning("Broken symlink {0!s} --> {1!s}".format(linkPath, targetPath))
                return

            #if os.path.isdir(targetPath):
            #    dir_walk(targetPath)

        def walk_error_handler(e):
            logger.error(str(e))

        def dir_walk(rootDir):
            for dirPath,subDirEntries,fileEntries in os.walk(rootDir, followlinks=False, onerror=walk_error_handler):
                entries = subDirEntries + fileEntries
                for e in entries:
                    ePath = os.path.join(dirPath, e)
                    check_symlink(ePath)

        # start
        dir_walk(SCAN_ROOT)



def test():
    logger.info("testing appsdk.py ...")
    #AppSDK(sys.argv[1], sys.argv[2]).check_sdk_target_sysroots()
    appsdk = AppSDK()
    # Because of fakeroot problem, native sysroot needs to be generated first
    appsdk.populate_native_sysroot()
    appsdk.populate_target_sysroot(sys.argv[1])
    appsdk.check_sdk_target_sysroots()
    appsdk.create_sdk_files()
    appsdk.archive_sdk()
    appsdk.create_shar()

if __name__ == "__main__":
    test()
