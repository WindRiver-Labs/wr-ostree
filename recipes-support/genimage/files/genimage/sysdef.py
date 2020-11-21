import logging
import sys
import os
import shlex
import subprocess
import yaml

import genimage.utils as utils

logger = logging.getLogger('appsdk')

def install_contains(guest_yamls, args):
    extra_options = "-w %s/sub_workdir -o %s/sub_deploy" % (args.workdir, args.outdir)
    if args.no_clean:
        extra_options += " --no-clean"
    if args.no_validate:
        extra_options += " --no-validate"

    for yaml_file in guest_yamls:
        with open(yaml_file) as f:
            d = yaml.load(f, Loader=yaml.FullLoader) or dict()

        if "image_type" not in d:
            logger.error("The %s does not has an image_type section", yaml_file)
            sys.exit(1)
        image_type = d['image_type']
        if "vmdk" in image_type or \
           "vdi" in image_type or \
           "ostree_repo" in image_type or \
           "ustart" in image_type or \
           "wic" in image_type:

            if args.gpgpath:
                extra_options += " -g %s" % self.args.gpgpath

            utils.run_cmd("genimage -d %s %s" % (yaml_file, extra_options), shell=True)
        elif "container" in image_type:
            utils.run_cmd("gencontainer -d %s %s" % (yaml_file, extra_options), shell=True)
        else:
            logger.error("The contains section does not support %s", image_type)
            sys.exit(1)

def install_scripts(scripts, destdir):
    if scripts is None or destdir is None:
        return
    utils.mkdirhier(destdir)

    for s in scripts:
        dst = os.path.basename(s)
        # Inform users that scripts are run alpha-numerically
        if not dst[0].isnumeric() and not dst.endswith(".dat"):
            logger.warn("The scripts are run alpha-numerically, please add prefix `[0-9][0-9]_' to %s", s)

        dst = os.path.join(destdir, dst)
        utils.copyfile(s, dst)
        utils.run_cmd_oneshot("chmod 755  %s" % dst)

def install_files(files, target_rootfs):
    for e in files:
        if 'src' not in e or 'dst' not in e:
            logger.error("Incorrect files:\n%s", e)
            continue

        src = e['src']
        dst = e['dst']
        if not dst.startswith(target_rootfs):
            dst = target_rootfs + dst
        if "/etc/sysdef/run_on_upgrade.d/" in dst:
            dst = dst.replace("/etc/sysdef/run_on_upgrade.d/",
                              "/etc/sysdef/run_on_upgrade.d/%s/" % utils.get_today())
        if not os.path.isdir(dst):
            utils.mkdirhier(os.path.dirname(dst))
        if dst.endswith("/"):
            utils.mkdirhier(dst)

        if src.startswith("http:") or src.startswith("https:") or src.startswith("ftp:"):
            cmd = "wget --progress=dot -c -t 2 -T 30 --passive-ftp --no-check-certificate %s" % src
            if os.path.isdir(dst):
                cmd += " -P %s" % dst
            else:
                cmd += " -O %s" % shlex.quote(dst)
            try:
                logger.debug(cmd)
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
                output = output.decode('utf-8')
                logger.debug('output: %s' % output)
            except subprocess.CalledProcessError as e:
                raise Exception("%s\n%s" % (str(e), e.output.decode('utf-8')))
        else:
            if os.path.isdir(dst):
                dst = os.path.join(dst, os.path.basename(src))
            src = os.path.realpath(src)
            logger.debug("%s -> %s" % (src, dst))
            utils.copyfile(src, dst)

        mode = e['mode'] if 'mode' in e else 664
        if os.path.isdir(dst):
            dst = os.path.join(dst, os.path.basename(src))
        utils.run_cmd_oneshot("chmod %s %s" % (mode, dst))


