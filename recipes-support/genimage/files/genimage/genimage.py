#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
#
# Copyright (C) 2020 Wind River Systems, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

import os
import sys
import subprocess
import logging
import argcomplete
from texttable import Texttable

from genimage.utils import set_logger
from genimage.utils import show_task_info
from genimage.image import CreateWicImage
from genimage.image import CreateVMImage
from genimage.image import CreateOstreeRepo
from genimage.image import CreateOstreeOTA
from genimage.image import CreateBootfs
from genimage.genXXX import GenXXX
from genimage.genXXX import set_parser

import genimage.constant as constant
from genimage.constant import DEFAULT_PACKAGE_FEED
from genimage.constant import DEFAULT_REMOTE_PKGDATADIR
from genimage.constant import DEFAULT_PACKAGES
from genimage.constant import DEFAULT_MACHINE
from genimage.constant import DEFAULT_IMAGE
from genimage.constant import DEFAULT_IMAGE_FEATURES

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def set_parser_genimage(parser=None):
    supported_types = [
        'wic',
        'vmdk',
        'vdi',
        'ostree-repo',
        'ustart',
        'all',
    ]
    parser = set_parser(parser, supported_types)
    parser.add_argument('-g', '--gpgpath',
        default=None,
        help='Specify gpg homedir, it overrides \'gpg_path\' in Yaml, default is /tmp/.lat_gnupg',
        action='store')
    return parser

class GenImage(GenXXX):
    """
    * Create the following images in order:
        - ostree repository
        - wic image
    """

    def __init__(self, args):
        super(GenImage, self).__init__(args)
        logger.debug("GPG Path: %s" % self.data["gpg"]["gpg_path"])

    def _parse_default(self):
        self.data['name'] = DEFAULT_IMAGE
        self.data['machine'] = DEFAULT_MACHINE
        self.data['image_type'] = ['ustart', 'ostree-repo']
        self.data['package_feeds'] = DEFAULT_PACKAGE_FEED
        self.data["ostree"] = constant.DEFAULT_OSTREE_DATA
        self.data["wic"] = constant.DEFAULT_WIC_DATA
        self.data['remote_pkgdatadir'] = DEFAULT_REMOTE_PKGDATADIR
        self.data['features'] =  DEFAULT_IMAGE_FEATURES
        self.data["gpg"] = constant.DEFAULT_GPG_DATA
        self.data['packages'] = DEFAULT_PACKAGES[DEFAULT_MACHINE]
        self.data['external-packages'] = []
        self.data['include-default-packages'] = "1"
        self.data['rootfs-pre-scripts'] = ['echo "run script before do_rootfs in $IMAGE_ROOTFS"']
        self.data['rootfs-post-scripts'] = ['echo "run script after do_rootfs in $IMAGE_ROOTFS"']
        self.data['environments'] = ['NO_RECOMMENDATIONS="0"', 'KERNEL_PARAMS="key=value"']

    def _parse_inputyamls(self):
        pykwalify_dir = os.path.join(os.environ['OECORE_NATIVE_SYSROOT'], 'usr/share/genimage/data/pykwalify')
        self.pykwalify_schemas = [os.path.join(pykwalify_dir, 'partial-schemas.yaml')]
        self.pykwalify_schemas.append(os.path.join(pykwalify_dir, 'genimage-schema.yaml'))

        super(GenImage, self)._parse_inputyamls()

    def _parse_options(self):
        super(GenImage, self)._parse_options()

        if self.args.type:
            self.data['image_type'] = self.args.type

        if self.args.gpgpath:
            self.data["gpg"]["gpg_path"] = os.path.realpath(self.args.gpgpath)

    def _parse_amend(self):
        super(GenImage, self)._parse_amend()

        # Use default to fill missing params of "ostree" section
        for ostree_param in constant.DEFAULT_OSTREE_DATA:
            if ostree_param not in self.data["ostree"]:
                self.data["ostree"][ostree_param] = constant.DEFAULT_OSTREE_DATA[ostree_param]

        # Use default to fill missing params of "wic" section
        for wic_param in constant.DEFAULT_WIC_DATA:
            if wic_param not in self.data["wic"]:
                self.data["wic"][wic_param] = constant.DEFAULT_WIC_DATA[wic_param]

        if 'all' in self.data['image_type']:
            self.data['image_type'] = ['ostree-repo', 'wic', 'ustart', 'vmdk', 'vdi']

    def _do_rootfs_pre(self, rootfs=None):
        if rootfs is None:
            return

        super(GenImage, self)._do_rootfs_pre(rootfs)

        if self.machine == "bcm-2xxx-rpi4":
            os.environ['OSTREE_CONSOLE'] = self.data["ostree"]['OSTREE_CONSOLE']
            script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'update_boot_scr.sh')
            script_cmd = "{0} {1} {2} {3} {4}".format(script_cmd,
                                                      rootfs.target_rootfs,
                                                      self.image_name,
                                                      self.data["ostree"]['ostree_use_ab'],
                                                      self.data["ostree"]['ostree_remote_url'])
            rootfs.add_rootfs_post_scripts(script_cmd)
        elif self.machine == "intel-x86-64":
            os.environ['OSTREE_CONSOLE'] = self.data["ostree"]['OSTREE_CONSOLE']
            script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'update_grub_cfg.sh')
            script_cmd = "{0} {1}".format(script_cmd, rootfs.target_rootfs)
            rootfs.add_rootfs_post_scripts(script_cmd)

        if 'systemd' in self.packages or 'systemd' in self.external_packages:
            script_cmd = os.path.join(self.data_dir, 'post_rootfs', 'set_systemd_default_target.sh')
            if 'packagegroup-core-x11-xserver' in self.packages:
                script_cmd = "{0} {1} graphical.target".format(script_cmd, rootfs.target_rootfs)
            else:
                script_cmd = "{0} {1} multi-user.target".format(script_cmd, rootfs.target_rootfs)
            rootfs.add_rootfs_post_scripts(script_cmd)

    def _do_rootfs_post(self, rootfs=None):
        if rootfs is None:
            return

        super(GenImage, self)._do_rootfs_post(rootfs)

        # Copy kernel image, boot files, device tree files to deploy dir
        if self.machine == "intel-x86-64":
            for files in ["boot/bzImage*", "boot/efi/EFI/BOOT/*"]:
                cmd = "cp -rf {0}/{1} {2}".format(self.target_rootfs, files, self.deploydir)
                utils.run_cmd_oneshot(cmd)

                cmd = "ln -snf -r {0} {1}".format(os.path.join(self.deploydir, "bootx64.efi"),
                                                  os.path.join(self.deploydir, "grub-efi-bootx64.efi"))
                utils.run_cmd_oneshot(cmd)

        else:
            cmd = "cp -rf {0}/boot/* {1}".format(self.target_rootfs, self.deploydir)
            utils.run_cmd_oneshot(cmd)

        if "include-container-images" in self.data:
            self._include_container_images(rootfs)

    def _include_container_images(self, rootfs):
        utils.run_cmd_oneshot("rm -rf $IMAGE_ROOTFS/var/docker-images/*")

        load_docker_images = os.path.join(rootfs.target_rootfs, "etc/default", "load-docker-images")
        run_docker_images = os.path.join(rootfs.target_rootfs, "etc/default", "run-docker-images")
        auto_start_containers = os.path.join(rootfs.target_rootfs, "etc/default", "auto-start-containers")
        open(run_docker_images, "w").write("")
        open(load_docker_images, "w").write("")
        open(auto_start_containers, "w").write("")

        for d in self.data["include-container-images"]:
            container = d["container-name"]
            utils.run_cmd_oneshot(d["copy-container"])

            # Copy/Pull docker images to target
            cmd = d["add-container"]
            logger.debug(cmd)
            open(load_docker_images, "a").write("%s\n" % cmd)

            # Start the container
            cmd = "docker start %s >/dev/null 2>&1" % container
            # If failed, it means the container does not exist, use docker run to create a new one
            # Insert container name to docker run, and run container in background
            cmd = cmd + " || " + d["run-container"].replace(" run ", " run --name %s -d " % container)
            open(run_docker_images, "a").write("%s\n" % cmd)
            logger.debug(cmd)

            # enable auto startup of the container
            cmd = "systemctl --no-reload enable start-container@%s.service" % container
            open(auto_start_containers, "a").write("%s\n" % cmd)
            logger.debug(cmd)

    def do_prepare(self):
        super(GenImage, self).do_prepare()
        gpg_data = self.data["gpg"]
        utils.check_gpg_keys(gpg_data)

    def do_post(self):
        for f in ["qemu-u-boot-bcm-2xxx-rpi4.bin", "ovmf.qcow2"]:
            qemu_data = os.path.join(self.native_sysroot, "usr/share/qemu_data", f)
            if os.path.exists(qemu_data):
                logger.debug("Deploy %s", f)
                cmd = "cp -f {0} {1}".format(qemu_data, self.deploydir)
                utils.run_cmd_oneshot(cmd)

    @show_task_info("Create Initramfs")
    def do_ostree_initramfs(self):
        # If the Initramfs exists, reuse it
        image_name = "initramfs-ostree-image-{0}.cpio.gz".format(self.machine)
        if self.machine == "bcm-2xxx-rpi4":
            image_name += ".u-boot"

        image = os.path.join(self.deploydir, image_name)
        if os.path.exists(os.path.realpath(image)):
            logger.info("Reuse existed Initramfs")
            return

        image_back = os.path.join(self.native_sysroot, "usr/share/genimage/data/initramfs", image_name)
        if not os.path.exists(image_back):
            logger.error("The initramfs does not exist, please call `appsdk geninitramfs' to build it")
            sys.exit(1)

        logger.info("Reuse existed Initramfs of SDK")
        cmd = "cp -f {0} {1}".format(image_back, self.deploydir)
        utils.run_cmd_oneshot(cmd)

    @show_task_info("Create Wic Image")
    def do_image_wic(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ostree_use_ab = self.data["ostree"].get("ostree_use_ab", '1')
        wks_file = utils.get_ostree_wks(ostree_use_ab, self.machine)
        logger.debug("WKS %s", wks_file)
        image_wic = CreateWicImage(
                        image_name = self.image_name,
                        workdir = workdir,
                        machine = self.machine,
                        target_rootfs = self.target_rootfs,
                        deploydir = self.deploydir,
                        wks_file = wks_file)

        env = self.data['wic'].copy()
        env['WORKDIR'] = workdir
        if self.machine == "bcm-2xxx-rpi4":
            env.update({'OSTREE_SD_BOOT_ALIGN':'4',
                        'OSTREE_SD_UBOOT_WIC1':'',
                        'OSTREE_SD_UBOOT_WIC2':'',
                        'OSTREE_SD_UBOOT_WIC3':'',
                        'OSTREE_SD_UBOOT_WIC4':''})
        image_wic.set_wks_in_environ(**env)

        image_wic.create()

    @show_task_info("Create Vmdk Image")
    def do_image_vmdk(self):
        vmdk = CreateVMImage(image_name=self.image_name,
                             machine=self.machine,
                             deploydir=self.deploydir,
                             vm_type="vmdk")
        vmdk.create()

    @show_task_info("Create Vdi Image")
    def do_image_vdi(self):
        vdi = CreateVMImage(image_name=self.image_name,
                            machine=self.machine,
                            deploydir=self.deploydir,
                            vm_type="vdi")
        vdi.create()

    @show_task_info("Create Ostree Repo")
    def do_ostree_repo(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ostree_repo = CreateOstreeRepo(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        target_rootfs=self.target_rootfs,
                        deploydir=self.deploydir,
                        gpg_path=self.data['gpg']['gpg_path'],
                        gpgid=self.data['gpg']['ostree']['gpgid'],
                        gpg_password=self.data['gpg']['ostree']['gpg_password'])

        ostree_repo.create()

        ostree_repo.gen_env(self.data)

    @show_task_info("Create Ostree OTA")
    def do_ostree_ota(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ostree_ota = CreateOstreeOTA(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        deploydir=self.deploydir,
                        ostree_use_ab=self.data["ostree"]['ostree_use_ab'],
                        ostree_osname=self.data["ostree"]['ostree_osname'],
                        ostree_skip_boot_diff=self.data["ostree"]['ostree_skip_boot_diff'],
                        ostree_remote_url=self.data["ostree"]['ostree_remote_url'],
                        gpgid=self.data["gpg"]['ostree']['gpgid'])

        ostree_ota.create()

    @show_task_info("Create Ustart Image")
    def do_ustart_img(self):
        workdir = os.path.join(self.workdir, self.image_name)
        ustart = CreateBootfs(
                        image_name=self.image_name,
                        workdir=workdir,
                        machine=self.machine,
                        deploydir=self.deploydir)
        ustart.create()

    def do_report(self):
        table = Texttable()
        table.set_cols_align(["l", "l"])
        table.set_cols_valign(["t", "t"])
        table.add_rows([["Type", "Name"]])

        image_name = "%s-%s" % (self.image_name, self.machine)
        cmd_format = "ls -gh --time-style=+%%Y %s | awk '{$1=$2=$3=$4=$5=\"\"; print $0}'"

        output = subprocess.check_output("ls {0}.yaml".format(image_name), shell=True, cwd=self.deploydir)
        table.add_row(["Image Yaml File", output.strip()])

        if any(img_type in self.image_type for img_type in ["ostree-repo", "wic", "ustart", "vmdk", "vdi"]):
            output = subprocess.check_output("ls -d  ostree_repo", shell=True, cwd=self.deploydir)
            table.add_row(["Ostree Repo", output.strip()])

        if "wic" in self.image_type:
            cmd_wic = cmd_format % "{0}.wic".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["WIC Image", output.strip()])

            cmd_wic = cmd_format % "{0}.wic.README.md".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["WIC Image Doc", output.strip()])

            if os.path.exists(os.path.join(self.deploydir, "{0}.qemuboot.conf".format(image_name))):
                cmd_wic = cmd_format % "{0}.qemuboot.conf".format(image_name)
                output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir, stderr=subprocess.STDOUT)
                table.add_row(["WIC Image\nQemu Conf", output.strip()])

        if "vdi" in self.image_type:
            cmd_wic = cmd_format % "{0}.wic.vdi".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["VDI Image", output.strip()])

        if "vmdk" in self.image_type:
            cmd_wic = cmd_format % "{0}.wic.vmdk".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["VMDK Image", output.strip()])

        if "ustart" in self.image_type:
            cmd_wic = cmd_format % "{0}.ustart.img.gz".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["Ustart Image", output.strip()])

            cmd_wic = cmd_format % "{0}.ustart.img.gz.README.md".format(image_name)
            output = subprocess.check_output(cmd_wic, shell=True, cwd=self.deploydir)
            table.add_row(["Ustart Image Doc", output.strip()])

        logger.info("Deploy Directory: %s\n%s", self.deploydir, table.draw())

def _main_run_internal(args):
    create = GenImage(args)
    create.do_prepare()
    create.do_rootfs()
    if create.target_rootfs is None:
        logger.error("Create Target Rootfs Failed")
        sys.exit(1)
    else:
        logger.debug("Create Target Rootfs: %s" % create.target_rootfs)

    create.do_ostree_initramfs()

    # WIC image requires ostress repo
    if any(img_type in create.image_type for img_type in ["ostree-repo", "wic", "ustart", "vmdk", "vdi"]):
        create.do_ostree_repo()

    if "wic" in create.image_type or "vmdk" in create.image_type or "vdi" in create.image_type:
        create.do_ostree_ota()
        create.do_image_wic()
        if "vmdk" in create.image_type:
            create.do_image_vmdk()

        if "vdi" in create.image_type:
            create.do_image_vdi()

    if "ustart" in create.image_type:
        create.do_ustart_img()

    create.do_post()
    create.do_report()

def _main_run(args):
    try:
        ret = _main_run_internal(args)
    except Exception as e:
            logger.error(e)
            raise

def main():
    parser = set_parser_genimage()
    parser.set_defaults(func=_main_run)
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    set_logger(logger, level=args.loglevel, log_path=args.logdir)
    args.func(args)

def set_subparser(subparsers=None):
    if subparsers is None:
        sys.exit(1)
    parser_genimage = subparsers.add_parser('genimage', help='Generate images from package feeds for specified machines')
    parser_genimage = set_parser_genimage(parser_genimage)
    parser_genimage.set_defaults(func=_main_run)

if __name__ == "__main__":
    main()
