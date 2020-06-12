import logging
import os
import errno
import time
import subprocess
import glob
import stat
import shutil
import re

def set_logger(logger):
    logger.setLevel(logging.DEBUG)

    class ColorFormatter(logging.Formatter):
        FORMAT = ("$BOLD%(name)-s$RESET - %(levelname)s: %(message)s")

        BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(range(8))

        RESET_SEQ = "\033[0m"
        COLOR_SEQ = "\033[1;%dm"
        BOLD_SEQ = "\033[1m"

        COLORS = {
            'WARNING': YELLOW,
            'INFO': GREEN,
            'DEBUG': BLUE,
            'ERROR': RED
        }

        def formatter_msg(self, msg, use_color = True):
            if use_color:
                msg = msg.replace("$RESET", self.RESET_SEQ).replace("$BOLD", self.BOLD_SEQ)
            else:
                msg = msg.replace("$RESET", "").replace("$BOLD", "")
            return msg

        def __init__(self, use_color=True):
            msg = self.formatter_msg(self.FORMAT, use_color)
            logging.Formatter.__init__(self, msg)
            self.use_color = use_color

        def format(self, record):
            levelname = record.levelname
            if self.use_color and levelname in self.COLORS:
                fore_color = 30 + self.COLORS[levelname]
                levelname_color = self.COLOR_SEQ % fore_color + levelname + self.RESET_SEQ
                record.levelname = levelname_color
            return logging.Formatter.format(self, record)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    #ch.setFormatter(ColorFormatter())
    logger.addHandler(ch)

def run_cmd(cmd, logger):
    logger.debug('Running %s' % cmd)
    output = subprocess.check_output(cmd, shell=True)
    output = output.decode('utf-8')
    logger.debug('output: %s' % output)
    return output

def get_today():
    return time.strftime("%Y%m%d%H%M%S")

DEFAULT_MACHINE = "bcm-2xxx-rpi4"

DEFAULT_IMAGE = "wrlinux-image-small"

DEFAULT_PACKAGE_FEED = [
    "http://128.224.153.74/bcm-2xxx-rpi4/rpm/",
]

DEFAULT_IMAGE_FEATURES = []

FEED_ARCHS_DICT = {
    'intel-x86-64': "all any noarch x86 i586 i686 core2_32 corei7_32 intel_x86_64 x86_64 core2_64 corei7_64",
    'bcm-2xxx-rpi4': "all any noarch armv5hf_vfp armv5thf_vfp armv5ehf_vfp armv5tehf_vfp armv6hf_vfp armv6thf_vfp armv7ahf_vfp armv7at2hf_vfp armv7ahf_neon armv7at2hf_neon bcm_2xxx_rpi4 aarch64 armv8a armv8a_crc armv8a_crypto armv8a_crc_crypto cortexa72",
}

# default rootfs: small
DEFAULT_PACKAGES = '''
    packagegroup-core-boot
    kernel-modules
    u-boot-uenv
    i2c-tools
    alsa-utils
    pm-utils
    linux-firmware
    boot-config
    u-boot
    kernel-devicetree
    kernel-image-image
    packagegroup-busybox-replacement
    ostree
    ostree-upgrade-mgr
    os-release
'''.split()

OSTREE_INITRD_PACKAGES = '''
    ostree ostree-switchroot
    initramfs-ostree bash
    kmod bzip2 gnupg kbd
    util-linux util-linux-setsid
    util-linux-mount util-linux-blkid
    util-linux-lsblk util-linux-fdisk
    util-linux-fsck util-linux-blockdev
    dosfstools curl udev mdadm
    base-passwd rng-tools e2fsprogs-tune2fs
    e2fsprogs-resize2fs pv gzip findutils
    tar grep sed gawk busybox busybox-udhcpc
'''.split()

def fake_root(logger, workdir = os.path.join(os.getcwd(),"workdir")):
    native_sysroot = os.environ['OECORE_NATIVE_SYSROOT']
    os.environ['PSEUDO_PREFIX'] = os.path.join(native_sysroot, 'usr')
    os.environ['PSEUDO_LOCALSTATEDIR'] = os.path.join(workdir, 'pseudo')
    os.environ['PSEUDO_NOSYMLINKEXP'] = "1"
    os.environ['PSEUDO_PASSWD'] = "%s:%s" % (os.path.join(workdir, 'rootfs'), os.environ['OECORE_TARGET_SYSROOT'])
    os.environ['LD_PRELOAD'] = os.path.join(native_sysroot, 'usr/lib/pseudo/lib64/libpseudo.so')
    os.environ['LC_ALL'] = "en_US.UTF-8"

def mkdirhier(directory):
    """Create a directory like 'mkdir -p', but does not complain if
    directory already exists like os.makedirs
    """

    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(directory):
            raise e

def remove(path, recurse=False, ionice=False):
    """Equivalent to rm -f or rm -rf"""
    if not path:
        return
    if recurse:
        for name in glob.glob(path):
            if _check_unsafe_delete_path(path):
                raise Exception('bb.utils.remove: called with dangerous path "%s" and recurse=True, refusing to delete!' % path)
        # shutil.rmtree(name) would be ideal but its too slow
        cmd = [] 
        if ionice:
            cmd = ['ionice', '-c', '3'] 
        subprocess.check_call(cmd + ['rm', '-rf'] + glob.glob(path))
        return
    for name in glob.glob(path):
        try: 
            os.unlink(name)
        except OSError as exc: 
            if exc.errno != errno.ENOENT:
                raise

def _check_unsafe_delete_path(path):
    """
    Basic safeguard against recursively deleting something we shouldn't. If it returns True,
    the caller should raise an exception with an appropriate message.
    NOTE: This is NOT meant to be a security mechanism - just a guard against silly mistakes
    with potentially disastrous results.
    """
    extra = ''
    # HOME might not be /home/something, so in case we can get it, check against it
    homedir = os.environ.get('HOME', '')
    if homedir:
        extra = '|%s' % homedir
    if re.match('(/|//|/home|/home/[^/]*%s)$' % extra, os.path.abspath(path)):
        return True
    return False

def copyfile(src, dest, logger, newmtime = None, sstat = None):
    """
    Copies a file from src to dest, preserving all permissions and
    attributes; mtime will be preserved even when moving across
    filesystems.  Returns true on success and false on failure.
    """
    #print "copyfile(" + src + "," + dest + "," + str(newmtime) + "," + str(sstat) + ")"
    try:
        if not sstat:
            sstat = os.lstat(src)
    except Exception as e:
        logger.warning("copyfile: stat of %s failed (%s)" % (src, e))
        return False

    destexists = 1
    try:
        dstat = os.lstat(dest)
    except:
        dstat = os.lstat(os.path.dirname(dest))
        destexists = 0

    if destexists:
        if stat.S_ISLNK(dstat[stat.ST_MODE]):
            try:
                os.unlink(dest)
                destexists = 0
            except Exception as e:
                pass

    if stat.S_ISLNK(sstat[stat.ST_MODE]):
        try:
            target = os.readlink(src)
            if destexists and not stat.S_ISDIR(dstat[stat.ST_MODE]):
                os.unlink(dest)
            os.symlink(target, dest)
            os.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
            return os.lstat(dest)
        except Exception as e:
            logger.warning("copyfile: failed to create symlink %s to %s (%s)" % (dest, target, e))
            return False

    if stat.S_ISREG(sstat[stat.ST_MODE]):
        try:
            srcchown = False
            if not os.access(src, os.R_OK):
                # Make sure we can read it
                srcchown = True
                os.chmod(src, sstat[stat.ST_MODE] | stat.S_IRUSR)

            # For safety copy then move it over.
            shutil.copyfile(src, dest + "#new")
            os.rename(dest + "#new", dest)
        except Exception as e:
            logger.warning("copyfile: copy %s to %s failed (%s)" % (src, dest, e))
            return False
        finally:
            if srcchown:
                os.chmod(src, sstat[stat.ST_MODE])
                os.utime(src, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))

    else:
        #we don't yet handle special, so we need to fall back to /bin/mv
        a = getstatusoutput("/bin/cp -f " + "'" + src + "' '" + dest + "'")
        if a[0] != 0:
            logger.warning("copyfile: failed to copy special file %s to %s (%s)" % (src, dest, a))
            return False # failure
    try:
        os.lchown(dest, sstat[stat.ST_UID], sstat[stat.ST_GID])
        os.chmod(dest, stat.S_IMODE(sstat[stat.ST_MODE])) # Sticky is reset on chown
    except Exception as e:
        logger.warning("copyfile: failed to chown/chmod %s (%s)" % (dest, e))
        return False

    if newmtime:
        os.utime(dest, (newmtime, newmtime))
    else:
        os.utime(dest, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))
        newmtime = sstat[stat.ST_MTIME]
    return newmtime

def which_wild(pathname, path=None, mode=os.F_OK, *, reverse=False, candidates=False):
    """Search a search path for pathname, supporting wildcards.

    Return all paths in the specific search path matching the wildcard pattern
    in pathname, returning only the first encountered for each file. If
    candidates is True, information on all potential candidate paths are
    included.
    """
    paths = (path or os.environ.get('PATH', os.defpath)).split(':')
    if reverse:
        paths.reverse()

    seen, files = set(), []
    for index, element in enumerate(paths):
        if not os.path.isabs(element):
            element = os.path.abspath(element)

        candidate = os.path.join(element, pathname)
        globbed = glob.glob(candidate)
        if globbed:
            for found_path in sorted(globbed):
                if not os.access(found_path, mode):
                    continue
                rel = os.path.relpath(found_path, element)
                if rel not in seen:
                    seen.add(rel)
                    if candidates:
                        files.append((found_path, [os.path.join(p, rel) for p in paths[:index+1]]))
                    else:
                        files.append(found_path)

    return files
