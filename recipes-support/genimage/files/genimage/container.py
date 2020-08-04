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
        cmd = "tar --numeric-owner -cf %s/%s.rootfs.tar -C %s ." % \
                (self.deploydir,self.image_fullname, self.target_rootfs)
        utils.run_cmd_oneshot(cmd)

        cmd = "pbzip2 -f -k %s/%s.rootfs.tar" % (self.deploydir, self.image_fullname)
        utils.run_cmd_oneshot(cmd)

        cmd = "rm -f %s/%s.rootfs.tar" % (self.deploydir, self.image_fullname)
        utils.run_cmd_oneshot(cmd)

        self._create_symlinks()

    def _create_symlinks(self):
        dst = os.path.join(self.deploydir, self.image_linkname + ".tar.bz2")
        src = os.path.join(self.deploydir, self.image_fullname + ".rootfs.tar.bz2")

        if os.path.exists(src):
            logger.debug("Creating symlink: %s -> %s" % (dst, src))
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(os.path.basename(src), dst)
        else:
            logger.error("Skipping symlink, source does not exist: %s -> %s" % (dst, src))
