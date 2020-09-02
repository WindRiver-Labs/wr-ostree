import subprocess
import os
import os.path
import logging

from genimage import utils
from genimage.image import Image

logger = logging.getLogger('appsdk')

class CreateContainer(Image):
    def _add_keys(self):
        self.date = utils.get_today()
        self.image_fullname = "%s-%s-%s" % (self.image_name, self.machine, self.date)
        self.image_linkname =  "%s-%s" % (self.image_name, self.machine)

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

