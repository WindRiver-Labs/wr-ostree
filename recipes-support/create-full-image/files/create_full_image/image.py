from abc import ABCMeta, abstractmethod
import subprocess
import os
import os.path

from create_full_image import utils

class Image(object, metaclass=ABCMeta):
    """
    This is an abstract class. Do not instantiate this directly.
    """
    def __init__(self,
                 image_name,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger):

        self.image_name = image_name
        self.logger = logger
        self.workdir = workdir
        self.machine = machine
        self.target_rootfs = target_rootfs
        self.deploydir = deploydir
        self.logger = logger

        self.date = utils.get_today()

        self.gpgid = ""
        self.gpg_passphase = ""
        self.gpgpath = ""

    def set_gpg(self, gpgid="", gpg_passphase="", gpgpath=""):
        self.gpgid = gpgid
        self.gpg_passphase = gpg_passphase
        self.gpgpath = gpgpath

    @abstractmethod
    def create(self):
        pass


class CreateInitramfs(Image):
    def __init__(self,
                 image_name,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger):

        super(CreateInitramfs, self).__init__(
                 image_name,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger)

        self.image_fullname = "%s-%s-%s" % (self.image_name, self.machine, self.date)
        self.image_linkname =  "%s-%s" % (self.image_name, self.machine)


    def create(self):
        self.logger.info("Create Initramfs")
        self._create_cpio_gz()
        if self.machine == "bcm-2xxx-rpi4":
            self._create_uboot()
        self._create_symlinks()

    def _create_uboot(self):
        cmd = "cd %s && mkimage -A arm64 -O linux -T ramdisk -C none -n %s -d %s.rootfs.cpio.gz %s.rootfs.cpio.gz.u-boot" % \
             (self.deploydir, self.image_fullname, self.image_fullname, self.image_fullname)
        utils.run_cmd_oneshot(cmd, self.logger)

        cmd = "rm %s/%s.rootfs.cpio.gz" % (self.deploydir, self.image_fullname)
        utils.run_cmd_oneshot(cmd, self.logger)

    def _create_cpio_gz(self):
        cmd = "cd %s && find . | sort | cpio --reproducible -o -H newc > %s/%s.rootfs.cpio" % \
             (self.target_rootfs, self.deploydir, self.image_fullname)
        utils.run_cmd_oneshot(cmd, self.logger)

        cmd = "cd %s && gzip -f -9 -n -c --rsyncable %s.rootfs.cpio > %s.rootfs.cpio.gz && rm %s.rootfs.cpio" % \
            (self.deploydir, self.image_fullname, self.image_fullname, self.image_fullname)
        utils.run_cmd_oneshot(cmd, self.logger)

    def _create_symlinks(self):
        dst = os.path.join(self.deploydir, self.image_linkname + ".cpio.gz")
        src = os.path.join(self.deploydir, self.image_fullname + ".rootfs.cpio.gz")
        if self.machine == "bcm-2xxx-rpi4":
            dst = dst + ".u-boot"
            src = src + ".u-boot"

        if os.path.exists(src):
            self.logger.info("Creating symlink: %s -> %s" % (dst, src))
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(os.path.basename(src), dst)
        else:
            self.logger.error("Skipping symlink, source does not exist: %s -> %s" % (dst, src))


class CreateWicImage(Image):
    def create(self):
        self.logger.info("Create Wic Image")


class CreateOstreeRepo(Image):
    def create(self):
        self.logger.info("Create Ostree Repo")
        ostreerepo_env = os.environ.copy()
        ostreerepo_env['IMAGE_ROOTFS'] = self.target_rootfs
        ostreerepo_env['DEPLOY_DIR_IMAGE'] = self.deploydir
        ostreerepo_env['WORKDIR'] = self.workdir
        ostreerepo_env['IMAGE_NAME'] = self.image_name
        ostreerepo_env['MACHINE'] = self.machine

        ostreerepo_env['OSTREE_GPGID'] = self.gpgid
        ostreerepo_env['OSTREE_GPG_PASSPHRASE'] = self.gpg_passphase
        ostreerepo_env['GPGPATH'] = self.gpgpath

        cmd = os.path.expandvars("$OECORE_NATIVE_SYSROOT/usr/share/create_full_image/scripts/run.do_image_ostree")
        res, output = utils.run_cmd(cmd, self.logger, env=ostreerepo_env)
        if res:
            self.logger.error("Executing %s failed\nExit code %d. Output:\n%s"
                               % (cmd, res, output))
            raise Exception("Executing %s failed\nExit code %d. Output:\n%s"
                               % (cmd, res, output))


class CreateOstreeOTA(Image):
    def __init__(self,
                 image_name,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger):

        super(CreateOstreeOTA, self).__init__(
                 image_name,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger)

        self.set_ostree()

    def set_ostree(self,
                   ostree_use_ab="1",
                   ostree_osname="wrlinux",
                   ostree_skip_boot_diff="2",
                   ostree_remote_url=""):

        self.ostree_use_ab = ostree_use_ab
        self.ostree_osname = ostree_osname
        self.ostree_skip_boot_diff = ostree_skip_boot_diff
        self.ostree_remote_url = ostree_remote_url

    def create(self):
        self.logger.info("Create Ostree OTA")
        ota_env = os.environ.copy()
        ota_env['DEPLOY_DIR_IMAGE'] = self.deploydir
        ota_env['WORKDIR'] = self.workdir
        ota_env['IMAGE_NAME'] = self.image_name
        ota_env['MACHINE'] = self.machine

        ota_env['OSTREE_GPGID'] = self.gpgid
        ota_env['OSTREE_USE_AB'] = self.ostree_use_ab
        ota_env['OSTREE_OSNAME'] = self.ostree_osname
        ota_env['OSTREE_SKIP_BOOT_DIFF'] = self.ostree_skip_boot_diff
        ota_env['OSTREE_REMOTE_URL'] = self.ostree_remote_url

        cmd = os.path.expandvars("$OECORE_NATIVE_SYSROOT/usr/share/create_full_image/scripts/run.do_image_otaimg")
        res, output = utils.run_cmd(cmd, self.logger, env=ota_env)
        if res:
            self.logger.error("Executing %s failed\nExit code %d. Output:\n%s"
                               % (cmd, res, output))
            raise Exception("Executing %s failed\nExit code %d. Output:\n%s"
                               % (cmd, res, output))


def test():
    import logging
    from create_full_image.utils import  fake_root
    from create_full_image.utils import  set_logger

    logger = logging.getLogger('image')
    set_logger(logger)
    logger.setLevel(logging.DEBUG)

    fake_root(logger)

    image_name = "initramfs-ostree-image"
    workdir = "/buildarea/raid5/hjia/wrlinux-20/build_master-wr_all_2020061521/build/tmp-glibc/deploy/sdk/dnf/workdir/initramfs-ostree-image"
    machine = "intel-x86-64"
    target_rootfs = "/buildarea/raid5/hjia/wrlinux-20/build_master-wr_all_2020061521/build/tmp-glibc/deploy/sdk/dnf/workdir/initramfs-ostree-image/rootfs/"
    deploydir = "/buildarea/raid5/hjia/wrlinux-20/build_master-wr_all_2020061521/build/tmp-glibc/deploy/sdk/dnf/deploy"
    initrd = CreateInitramfs(
                    image_name,
                    workdir,
                    machine,
                    target_rootfs,
                    deploydir,
                    logger)
    initrd.create()

if __name__ == "__main__":
    test()
