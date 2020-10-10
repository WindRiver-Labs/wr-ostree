import subprocess
import os
import os.path
import logging

from genimage import utils
from genimage.image import Image
from genimage.constant import DEFAULT_OCI_CONTAINER_DATA

logger = logging.getLogger('appsdk')

class CreateContainer(Image):
    def _set_allow_keys(self):
        self.allowed_keys.update({'container_oci'})

    def _add_keys(self):
        self.date = utils.get_today()
        self.image_fullname = "%s-%s-%s" % (self.image_name, self.machine, self.date)
        self.image_linkname =  "%s-%s" % (self.image_name, self.machine)

    def _create_oci(self):
        ota_env = os.environ.copy()
        ota_env['DEPLOY_DIR_IMAGE'] = self.deploydir
        ota_env['IMAGE_NAME'] = self.image_linkname
        ota_env['IMAGE_NAME_SUFFIX'] = '.rootfs'
        ota_env['MACHINE'] = self.machine
        for k in self.container_oci:
            ota_env[k] = self.container_oci[k]

        cmd = os.path.expandvars("$OECORE_NATIVE_SYSROOT/usr/share/genimage/scripts/run.do_image_oci")
        res, output = utils.run_cmd(cmd, env=ota_env)
        if res:
            raise Exception("Executing %s failed\nExit code %d. Output:\n%s"
                               % (cmd, res, output))


    def create(self):
        self._write_readme("container")

        cmd = "rm -rf {0}.rootfs-oci".format(self.image_linkname)
        utils.run_cmd_oneshot(cmd, cwd=self.deploydir)

        self._create_oci()

        cmd = "skopeo copy oci:{0}.rootfs-oci docker-archive:{1}.docker-image.tar.bz2:{2}".format(self.image_linkname, self.image_fullname, self.image_linkname)
        utils.run_cmd_oneshot(cmd, cwd=self.deploydir)

        self._create_symlinks()

    def _create_symlinks(self):
        container_dst = os.path.join(self.deploydir, self.image_linkname + ".docker-image.tar.bz2")
        container_src = os.path.join(self.deploydir, self.image_fullname + ".docker-image.tar.bz2")

        for dst, src in [(container_dst, container_src)]:

            if os.path.exists(src):
                logger.debug("Creating symlink: %s -> %s" % (dst, src))
                utils.resymlink(os.path.basename(src), dst)
            else:
                logger.error("Skipping symlink, source does not exist: %s -> %s" % (dst, src))

