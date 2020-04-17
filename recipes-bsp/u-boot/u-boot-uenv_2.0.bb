SUMMARY = "U-Boot boot.scr SD boot environment generation for ARM targets"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

INHIBIT_DEFAULT_DEPS = "1"
PACKAGE_ARCH = "${MACHINE_ARCH}"

DEPENDS = "u-boot-mkimage-native"

inherit deploy

DEFAULT_DTB ??= ""
OSTREE_UBOOT_CMD ??= "bootz"
OSTREE_BOOTSCR ??= "fs_links"
OSTREE_NET_INSTALL ??= "1"
OSTREE_NETINST_ARGS ??= "instab=${OSTREE_USE_AB}"
OSTREE_NETINST_BRANCH ??= "core-image-minimal"
OSTREE_NETINST_DEV ??= "/dev/mmcblk0"

bootscr_env_import() {
	cat <<EOF > ${WORKDIR}/uEnv.txt
setenv machine_name ${MACHINE}
setenv bretry 32
if test \${skip_script_fdt} != yes; then setenv fdt_file $default_dtb; fi
setenv A 5
setenv B 7
setenv ex _b
setenv filesize 99
fatsize mmc \${mmcdev}:1 no_ab
if test \${filesize} = 1;then setenv ex;setenv B \$A;fi
setenv mmcpart \$A
setenv rootpart ostree_root=LABEL=otaroot\${labelpre}
setenv bootpart ostree_boot=LABEL=otaboot\${labelpre}
setenv mmcpart_r \$B
setenv rootpart_r ostree_root=LABEL=otaroot\${ex}\${labelpre}
setenv bootpart_r ostree_boot=LABEL=otaboot\${ex}\${labelpre}
setenv bpart A
if fatload mmc \${mmcdev}:1 \${loadaddr} boot_ab_flag;then setexpr.l bpartv *\${loadaddr} \& 0xffffffff; if test \${bpartv} = 42333231;then setenv bpart B;fi;fi
setenv obpart \${bpart}
setexpr loadaddr1 \${loadaddr} + 1
setexpr loadaddr2 \${loadaddr} + 2
setexpr bct_addr \${loadaddr} + 200
setexpr bct_addr1 \${loadaddr} + 201
mw.l \${bct_addr} 52573030
setenv cntv 30
setenv bdef 30
setenv switchab if test \\\${bpart} = B\\;then setenv bpart A\\;else setenv bpart B\\;fi
if fatload mmc \${mmcdev}:1 \${loadaddr} boot_cnt;then setexpr.w cntv0 *\${loadaddr2};if test \${cntv0} = 5257;then setexpr.b cntv *\${loadaddr};setexpr.b bdef *\${loadaddr1};fi;fi
if test \${bdef} = 31;then run switchab;fi
if test \${cntv} > \${bretry};then run switchab;setenv cntv 30;if test \${bdef} = 31; then setenv bdef 30;else setenv bdef 31;fi;else setexpr.b cntv \${cntv} + 1;fi
mw.b \${bct_addr} \${cntv}
mw.b \${bct_addr1} \${bdef}
fatwrite mmc \${mmcdev}:1 \${bct_addr} boot_cnt 4
if test \${no_menu} != yes; then
 if test \${bdef} = 30;then
  setenv bootmenu_0 Boot Primary volume \${bpart}=
  setenv bootmenu_1 Boot Rollback=setenv bdef 31\;run switchab
 else
  setenv bootmenu_0 Boot Rollback \${bpart}=
  setenv bootmenu_1 Boot Primary volume=setenv bdef 30\;run switchab
 fi
 bootmenu \${menutimeout}
fi
if test \${bdef} = 30;then echo "==Booting default \${bpart}==";else echo "==Booting Rollback \${bpart}==";fi
if test \${bpart} = B; then
 setenv mmcpart \$B;
 setenv rootpart ostree_root=LABEL=otaroot\${ex}\${labelpre};
 setenv bootpart ostree_boot=LABEL=otaboot\${ex}\${labelpre};
 setenv mmcpart_r \$A;
 setenv rootpart_r ostree_root=LABEL=otaroot\${labelpre};
 setenv bootpart_r ostree_boot=LABEL=otaboot\${labelpre};
fi
if test -n \${rollback_f} && test \${rollback_f} = yes;then setenv bdef 31;setenv mmcpart \${mmcpart_r};setenv rootpart \${rootpart_r};setenv bootpart \${bootpart_r};echo "FORCED ROLLBACK";fi
setenv loadenvscript ext4load mmc \${mmcdev}:\${mmcpart} \${loadaddr} /loader/uEnv.txt
run loadenvscript && env import -t \${loadaddr} \${filesize}
setenv loadkernel ext4load mmc \${mmcdev}:\${mmcpart} \${loadaddr} /\${kernel_image}
setenv loadramdisk ext4load mmc \${mmcdev}:\${mmcpart} \${initrd_addr} /\${ramdisk_image}
setenv loaddtb ext4load mmc \${mmcdev}:\${mmcpart} \${fdt_addr} /\${bootdir}/\${fdt_file}
if test \${skip_script_wd} != yes; then setenv wdttimeout 120000; fi
run loadramdisk
run loaddtb
run loadkernel
if test \${bdef} = 31 && test "\${ex}" != "_b"; then
setenv bootargs \${bootargs2} \${bootpart} \${rootpart} console=\${console},\${baudrate} \${smp} flux=fluxdata\${labelpre}
else
setenv bootargs \${bootargs} \${bootpart} \${rootpart} console=\${console},\${baudrate} \${smp} flux=fluxdata\${labelpre}
fi
${OSTREE_UBOOT_CMD} \${loadaddr} \${initrd_addr} \${fdt_addr}
EOF
}

bootscr_fs_links() {
	NETINST_ARGS="${OSTREE_NETINST_ARGS}"

	cat <<EOF > ${WORKDIR}/uEnv.txt
${OSTREE_BOOTSCR_PRECMD}
setenv machine_name ${MACHINE}
test -n \${fdtcontroladdr} && setenv fdt_addr \${fdtcontroladdr}
setenv bretry 32
if test \${skip_script_fdt} != yes; then setenv fdt_file $default_dtb; fi
setenv ninst ${OSTREE_NET_INSTALL}
setenv A 5
setenv B 7
setenv ex _b
setenv filesize 99
fatsize mmc \${mmcdev}:1 no_ab
if test \${filesize} = 1;then setenv ex;setenv B \$A;fi
setenv mmcpart \$A
setenv rootpart ostree_root=LABEL=otaroot\${labelpre}
setenv bootpart ostree_boot=LABEL=otaboot\${labelpre}
setenv mmcpart_r \$B
setenv rootpart_r ostree_root=LABEL=otaroot\${ex}\${labelpre}
setenv bootpart_r ostree_boot=LABEL=otaboot\${ex}\${labelpre}
setenv bpart A
if fatload mmc \${mmcdev}:1 \${loadaddr} boot_ab_flag;then setexpr.l bpartv *\${loadaddr} \& 0xffffffff; if test \${bpartv} = 42333231;then setenv bpart B;fi;fi
setenv obpart \${bpart}
setexpr loadaddr1 \${loadaddr} + 1
setexpr loadaddr2 \${loadaddr} + 2
setexpr bct_addr \${loadaddr} + 200
setexpr bct_addr1 \${loadaddr} + 201
mw.l \${bct_addr} 52573030
setenv cntv 30
setenv bdef 30
setenv switchab if test \\\${bpart} = B\\;then setenv bpart A\\;else setenv bpart B\\;fi
if fatload mmc \${mmcdev}:1 \${loadaddr} boot_cnt;then setexpr.w cntv0 *\${loadaddr2};if test \${cntv0} = 5257;then setexpr.b cntv *\${loadaddr};setexpr.b bdef *\${loadaddr1};fi;fi
if test \${bdef} = 31;then run switchab;fi
if test \${cntv} -gt \${bretry};then run switchab;setenv cntv 30;if test \${bdef} = 31; then setenv bdef 30;else setenv bdef 31;fi;else setexpr.b cntv \${cntv} + 1;fi
mw.b \${bct_addr} \${cntv}
mw.b \${bct_addr1} \${bdef}
fatwrite mmc \${mmcdev}:1 \${bct_addr} boot_cnt 4
if test -n \${oURL}; then
 setenv URL "\${oURL}"
else
 setenv URL "${OSTREE_REMOTE_URL}"
fi
if test -n \${oBRANCH}; then
 setenv BRANCH \${oBRANCH}
else
 setenv BRANCH ${OSTREE_NETINST_BRANCH}
fi
setenv fdtargs
setenv netinstpre
if test -n \${use_fdtdtb} || test \${use_fdtdtb} -ge 1; then
 fdt addr \${fdt_addr}
 if test \${use_fdtdtb} -ge 2; then
  fdt get value fdtargs /chosen bootargs
 fi
else
 setenv netinstpre "fatload mmc \${mmcdev}:1 \${fdt_addr} \${fdt_file};"
fi
setenv exinargs
setenv instdef "$NETINST_ARGS"
if test -n \${ninstargs}; then
 setenv netinst "\${ninstargs}"
else
 setenv netinst "\${netinstpre}fatload mmc \${mmcdev}:1 \${loadaddr} ${OSTREE_KERNEL};fatload mmc \${mmcdev}:1 \${initrd_addr} initramfs; setenv bootargs \\"\${fdtargs} \${instdef} \${exinargs}\\";${OSTREE_UBOOT_CMD} \${loadaddr} \${initrd_addr} \${fdt_addr}"
fi
setenv autoinst echo "!!!Autostarting ERASE and INSTALL, you have 5 seconds to reset the board!!!"\;sleep 5\;run netinst
if test "\${no_autonetinst}" != 1 && test -n \${URL} ; then
 if test "\${ex}" != "_b"; then
  if test ! -e mmc \${mmcdev}:\$mmcpart 1/vmlinuz && test ! -e mmc \${mmcdev}:\$mmcpart 2/vmlinuz; then
    run autoinst
  fi
 else
  if test ! -e mmc \${mmcdev}:\$mmcpart 1/vmlinuz && test ! -e mmc \${mmcdev}:\$mmcpart_r 1/vmlinuz; then
    run autoinst
  fi
 fi
fi
if test \${no_menu} != yes; then
 setenv go 0
 if test \${bdef} = 30;then
  setenv bootmenu_0 Boot Primary volume \${bpart}=setenv go 1
  setenv bootmenu_1 Boot Rollback=setenv bdef 31\;run switchab\;setenv go 1
 else
  setenv bootmenu_0 Boot Rollback \${bpart}=\;setenv go 1
  setenv bootmenu_1 Boot Primary volume=setenv bdef 30\;run switchab\;setenv go 1
 fi
 if test -n \${URL} && test \${ninst} = 1; then
  setenv bootmenu_2 Re-install from ostree_repo=run netinst
 else
  setenv bootmenu_2
 fi
 if bootmenu \${menutimeout}; then echo ""; else setenv go 1; fi
else
 setenv go 1
fi
if test \${go} = 1; then
if test \${bdef} = 30;then echo "==Booting default \${bpart}==";else echo "==Booting Rollback \${bpart}==";fi
if test \${bpart} = B; then
 setenv mmcpart \$B;
 setenv rootpart ostree_root=LABEL=otaroot\${ex}\${labelpre};
 setenv bootpart ostree_boot=LABEL=otaboot\${ex}\${labelpre};
 setenv mmcpart_r \$A;
 setenv rootpart_r ostree_root=LABEL=otaroot\${labelpre};
 setenv bootpart_r ostree_boot=LABEL=otaboot\${labelpre};
fi
if test -n \${rollback_f} && test \${rollback_f} = yes;then setenv bdef 31;setenv mmcpart \${mmcpart_r};setenv rootpart \${rootpart_r};setenv bootpart \${bootpart_r};echo "FORCED ROLLBACK";fi
if test \${bdef} = 31 && test "\${ex}" != "_b"; then
setenv ostver 2
else
setenv ostver 1
fi
if test \${skip_script_wd} != yes; then setenv wdttimeout 120000; fi
setenv loadkernel ext4load mmc \${mmcdev}:\${mmcpart} \${loadaddr} \${ostver}/vmlinuz
setenv loadramdisk ext4load mmc \${mmcdev}:\${mmcpart} \${initrd_addr} \${ostver}/initramfs
setenv bootargs "\${fdtargs} \${bootpart} ostree=/ostree/\${ostver} \${rootpart} console=\${console},\${baudrate} \${smp} flux=fluxdata\${labelpre}"
if test ! -n \${use_fdtdtb} || test \${use_fdtdtb} -lt 1; then
 setenv loaddtb ext4load mmc \${mmcdev}:\${mmcpart} \${fdt_addr} \${ostver}/\${fdt_file};run loaddtb
fi
run loadramdisk
run loadkernel
${OSTREE_UBOOT_CMD} \${loadaddr} \${initrd_addr} \${fdt_addr}
fi
EOF
}

do_compile() {

    default_dtb="${DEFAULT_DTB}"
    if [ "$default_dtb" = "" ] ; then
        for k in `echo ${KERNEL_DEVICETREE} |grep -v dtbo`; do
            default_dtb="$(basename $k)"
	    break;
	done
        bbwarn 'DEFAULT_DTB=""'
	bbwarn "boot.scr set to DEFAULT_DTB=$default_dtb"
    fi
    if [ "${OSTREE_BOOTSCR}" = "fs_links" ] ; then
	bootscr_fs_links
    else
	bootscr_env_import
    fi

    build_date=`date -u +%s`
    sed -i -e  "s/instdate=BUILD_DATE/instdate=@$build_date/" ${WORKDIR}/uEnv.txt

    mkimage -A arm -T script -O linux -d ${WORKDIR}/uEnv.txt ${WORKDIR}/boot.scr
}

FILES_${PN} += "/boot/boot.scr"

do_install() {
        install -d  ${D}/boot
	install -Dm 0644 ${WORKDIR}/boot.scr ${D}/boot/
}

do_deploy() {
	install -Dm 0644 ${WORKDIR}/boot.scr ${DEPLOYDIR}/boot.scr
}
addtask do_deploy after do_compile before do_build

COMPATIBLE_HOST = "(aarch64|arm).*-linux"
