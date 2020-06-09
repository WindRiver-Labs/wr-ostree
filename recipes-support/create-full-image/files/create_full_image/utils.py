import logging
import os
import time

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
    ch.setFormatter(ColorFormatter())
    logger.addHandler(ch)

def run_cmd(cmd, logger):
    logger.debug('Running %s' % cmd)
    output = subprocess.check_output(cmd, shell=True)
    output = output.decode('utf-8')
    logger.debug('output: %s' % output)
    return output

def get_today():
    return time.strftime("%Y%m%d%H%M%S")

DEFAULT_MACHINE = "intel-x86-64"

DEFAULT_IMAGE = "wrlinux-image-small"

DEFAULT_PACKAGE_FEED = ["http://128.224.153.74/intel-x86-64/rpm"]

DEFAULT_IMAGE_FEATURES = []

# default rootfs: small
DEFAULT_PACKAGES = '''
    grub-efi
    i2c-tools
    intel-microcode
    iucode-tool
    kernel-modules
    lmsensors
    packagegroup-busybox-replacement
    packagegroup-core-boot
    packagegroup-wr-bsps
    rtl8723bs-bt
    run-postinsts
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
