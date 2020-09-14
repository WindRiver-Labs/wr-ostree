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
        ota_env['IMAGE_NAME_SUFFIX'] = '.container.rootfs'
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

        cmd = "tar --numeric-owner -cf {0}/{1}.container.rootfs.tar -C {2} .".format(self.deploydir,self.image_fullname, \
                self.target_rootfs)
        utils.run_cmd_oneshot(cmd)

        cmd = "pbzip2 -f -k {0}/{1}.container.rootfs.tar".format(self.deploydir, self.image_fullname)
        utils.run_cmd_oneshot(cmd)

        cmd = "rm -f {0}/{1}.container.rootfs.tar".format(self.deploydir, self.image_fullname)
        utils.run_cmd_oneshot(cmd)

        config_json = os.path.expandvars("$OECORE_NATIVE_SYSROOT/usr/share/genimage/data/oci_config/config.json")
        cmd = "cp -f {0} {1}/{2}.container.config.json".format(config_json, self.deploydir, self.image_fullname)
        utils.run_cmd_oneshot(cmd)

        self._create_oci()

        self._create_symlinks()

    def _create_symlinks(self):
        container_dst = os.path.join(self.deploydir, self.image_linkname + ".container.tar.bz2")
        container_src = os.path.join(self.deploydir, self.image_fullname + ".container.rootfs.tar.bz2")
        config_dst = os.path.join(self.deploydir, "config.json")
        config_src = os.path.join(self.deploydir, self.image_fullname + ".container.config.json")

        for dst, src in [(container_dst, container_src),
                (config_dst, config_src)]:

            if os.path.exists(src):
                logger.debug("Creating symlink: %s -> %s" % (dst, src))
                utils.resymlink(os.path.basename(src), dst)
            else:
                logger.error("Skipping symlink, source does not exist: %s -> %s" % (dst, src))

