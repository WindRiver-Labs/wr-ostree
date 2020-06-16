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
        self._create_symlinks()

    def _create_cpio_gz(self):

        try:
            cmd = "cd %s && find . | sort | cpio --reproducible -o -H newc > %s/%s.rootfs.cpio" % \
                 (self.target_rootfs, self.deploydir, self.image_fullname)
            self.logger.debug("> Executing: %s" % cmd)
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            if output: self.logger.debug(output.decode("utf-8"))
        except subprocess.CalledProcessError as e:
            self.logger.debug("Exit code %d. Output:\n%s" % (e.returncode, e.output.decode("utf-8")))


        try:
            cmd = "cd %s && gzip -f -9 -n -c --rsyncable %s.rootfs.cpio > %s.rootfs.cpio.gz && rm %s.rootfs.cpio" % \
                (self.deploydir, self.image_fullname, self.image_fullname, self.image_fullname)
            self.logger.debug("> Executing: %s" % cmd)
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            if output: self.logger.debug(output.decode("utf-8"))
        except subprocess.CalledProcessError as e:
            self.logger.debug("Exit code %d. Output:\n%s" % (e.returncode, e.output.decode("utf-8")))

    def _create_symlinks(self):
        dst = os.path.join(self.deploydir, self.image_linkname + ".cpio.gz")
        src = os.path.join(self.deploydir, self.image_fullname + ".rootfs.cpio.gz")

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
