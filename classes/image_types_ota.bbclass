# Image to use with u-boot as BIOS and OSTree deployment system

#inherit image_types

# Boot filesystem size in MiB
# OSTree updates may require some space on boot file system for
# boot scripts, kernel and initramfs images
#

do_image_otaimg[depends] += "e2fsprogs-native:do_populate_sysroot \
                             ${@'grub:do_populate_sysroot' if d.getVar('OSTREE_BOOTLOADER', True) == 'grub' else ''} \
                             ${@'virtual/bootloader:do_deploy' if d.getVar('OSTREE_BOOTLOADER', True) == 'u-boot' else ''}"

export FLUXDATA = "${@bb.utils.contains('DISTRO_FEATURES', 'luks', 'luks_fluxdata', 'fluxdata', d)}"
export ROOT_LABEL = "${@bb.utils.contains('DISTRO_FEATURES', 'luks', 'luks_otaroot', 'otaroot', d)}"

calculate_size () {
	BASE=$1
	SCALE=$2
	MIN=$3
	MAX=$4
	EXTRA=$5
	ALIGN=$6

	SIZE=`echo "$BASE * $SCALE" | bc -l`
	REM=`echo $SIZE | cut -d "." -f 2`
	SIZE=`echo $SIZE | cut -d "." -f 1`

	if [ -n "$REM" -o ! "$REM" -eq 0 ]; then
		SIZE=`expr $SIZE \+ 1`
	fi

	if [ "$SIZE" -lt "$MIN" ]; then
		$SIZE=$MIN
	fi

	SIZE=`expr $SIZE \+ $EXTRA`
	SIZE=`expr $SIZE \+ $ALIGN \- 1`
	SIZE=`expr $SIZE \- $SIZE \% $ALIGN`

	if [ -n "$MAX" ]; then
		if [ "$SIZE" -gt "$MAX" ]; then
			return -1
		fi
	fi
	
	echo "${SIZE}"
}

export OSTREE_OSNAME
export OSTREE_BRANCHNAME
export OSTREE_REPO
export OSTREE_BOOTLOADER
export WKS_FULL_PATH

IMAGE_CMD_otaimg () {
	if ${@bb.utils.contains('IMAGE_FSTYPES', 'otaimg', 'true', 'false', d)}; then
		if [ -z "$OSTREE_REPO" ]; then
			bbfatal "OSTREE_REPO should be set in your local.conf"
		fi

		if [ -z "$OSTREE_OSNAME" ]; then
			bbfatal "OSTREE_OSNAME should be set in your local.conf"
		fi

		if [ -z "$OSTREE_BRANCHNAME" ]; then
			bbfatal "OSTREE_BRANCHNAME should be set in your local.conf"
		fi

		PHYS_SYSROOT=`mktemp -d ${WORKDIR}/ota-sysroot-XXXXX`

		ostree admin --sysroot=${PHYS_SYSROOT} init-fs ${PHYS_SYSROOT}
		ostree admin --sysroot=${PHYS_SYSROOT} os-init ${OSTREE_OSNAME}
		ostree config --repo=${PHYS_SYSROOT}/ostree/repo set core.add-remotes-config-dir false
		if [ "${OSTREE_SKIP_BOOT_DIFF}" = "1" ] ; then
			ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.skip-boot-diff 1
		fi
		if [ "${OSTREE_USE_AB}" != 1 ] ; then
			ostree config  --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.no-ab 1
		fi
		ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.branch ${OSTREE_BRANCHNAME}
		if [ -n "${OSTREE_REMOTE_URL}" ] ; then
			do_gpg=""
			if [ "${OSTREE_GPGID}" = "" ] ; then
				do_gpg=--no-gpg-verify
			fi
			ostree config --repo=${PHYS_SYSROOT}/ostree/repo set upgrade.remote ${OSTREE_REMOTE_NAME}
			ostree remote --repo=${PHYS_SYSROOT}/ostree/repo add ${do_gpg} ${OSTREE_REMOTE_NAME} ${OSTREE_REMOTE_URL}
		fi


		mkdir -p ${PHYS_SYSROOT}/boot/loader.0
		ln -s loader.0 ${PHYS_SYSROOT}/boot/loader

		if [ "${OSTREE_BOOTLOADER}" = "grub" ]; then
			mkdir -p ${PHYS_SYSROOT}/boot/efi/EFI/BOOT
			if [ -n "${@bb.utils.contains('DISTRO_FEATURES', 'efi-secure-boot', 'Y', '', d)}" ]; then
				cp ${DEPLOY_DIR_IMAGE}/grubx64.efi ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/bootx64.efi
				cp ${DEPLOY_DIR_IMAGE}/grub.cfg.p7b ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/
			else
				cp ${DEPLOY_DIR_IMAGE}/grub-efi-bootx64.efi ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/bootx64.efi
			fi
			cp ${DEPLOY_DIR_IMAGE}/grub.cfg ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/
			#create the OS vendor fallback boot dir
			mkdir ${PHYS_SYSROOT}/boot/efi/EFI/"${@(d.getVar('DISTRO', False) or 'wrlinux')}"
			cp ${DEPLOY_DIR_IMAGE}/grub.cfg ${PHYS_SYSROOT}/boot/efi/EFI/"${@(d.getVar('DISTRO', False) or 'wrlinux')}"

			# Create an empty GRUB Environment Block
			echo "# GRUB Environment Block" > ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
			if [ "${OSTREE_USE_AB}" != "1" ] ; then
				printf "ab=0\n" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
			else
				echo -n "#####" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
			fi
			printf "boot_tried_count=0\n" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
			echo -n "###############################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################" >> ${PHYS_SYSROOT}/boot/efi/EFI/BOOT/boot.env
		elif [ "${OSTREE_BOOTLOADER}" = "u-boot" ]; then
			touch ${PHYS_SYSROOT}/boot/loader/uEnv.txt
		else
			bberror "Invalid bootloader: ${OSTREE_BOOTLOADER}"
		fi;

		ostree --repo=${PHYS_SYSROOT}/ostree/repo pull-local --remote=${OSTREE_OSNAME} ${OSTREE_REPO} ${OSTREE_BRANCHNAME}
		export OSTREE_BOOT_PARTITION="/boot"
		kargs_list=""
		for arg in ${OSTREE_KERNEL_ARGS}; do
			kargs_list="${kargs_list} --karg-append=$arg"
		done

		ostree admin --sysroot=${PHYS_SYSROOT} deploy ${kargs_list} --os=${OSTREE_OSNAME} ${OSTREE_BRANCHNAME}
		if [ "${OSTREE_USE_AB}" != "1" ] ; then
			# Provide a rollback deployment when using a single disk
			ostree admin --sysroot=${PHYS_SYSROOT} deploy --os=${OSTREE_OSNAME} ${OSTREE_BRANCHNAME}
		fi

		if [ -d ${PHYS_SYSROOT}/boot/0/ostree/boot/efi ] ; then
			cp -a ${PHYS_SYSROOT}/boot/0/ostree/boot/efi ${PHYS_SYSROOT}/boot
		fi

		if [ "${OSTREE_BOOTLOADER}" = "u-boot" ]; then
			mkdir -p ${WORKDIR}/rootfs_ota_uboot

			bootdir=$(grep ^bootdir= ${PHYS_SYSROOT}/boot/loader/uEnv.txt)
			bootdir=${bootdir#bootdir=}
			if [ "$bootdir" != "" ] && [ -e "${PHYS_SYSROOT}/boot$bootdir" ] ; then
				cp -r ${PHYS_SYSROOT}/boot$bootdir/*  ${WORKDIR}/rootfs_ota_uboot
			fi
			printf "123A" >  ${WORKDIR}/rootfs_ota_uboot/boot_ab_flag
			# The first 0 is the boot count, the second zero is the boot entry default
			printf '00WR' >  ${WORKDIR}/rootfs_ota_uboot/boot_cnt
			if [ "$INSTAB" != "1" ] ; then
				printf '1' >  ${WORKDIR}/rootfs_ota_uboot/no_ab
			fi
		fi

                #create an image with the free space equal the rootfs size
                wic_deployed_var_path=$(find ${PHYS_SYSROOT}/ostree/deploy/${OSTREE_OSNAME}/deploy/ -maxdepth 2 -name "var"|head -1)
		rm -rf ${WORKDIR}/rootfs_ota_var
		cp ${wic_deployed_var_path} -ar ${WORKDIR}/rootfs_ota_var

		# rootfs data for EFI partition
		if [ -d ${PHYS_SYSROOT}/boot/efi ]; then
			rm -rf ${WORKDIR}/rootfs_ota_efi
			mv ${PHYS_SYSROOT}/boot/efi ${WORKDIR}/rootfs_ota_efi
			mkdir -p ${PHYS_SYSROOT}/boot/efi
		fi

		# boot partition
		# OSTREE needs to create symlinks to locate the real kernel image, and efi partition does not support symlinks

		rm -rf ${WORKDIR}/rootfs_ota_boot
		mv ${PHYS_SYSROOT}/boot ${WORKDIR}/rootfs_ota_boot
		mkdir -p ${PHYS_SYSROOT}/boot

		# rootfs partition
		rm -rf ${WORKDIR}/rootfs_ota
		mv ${PHYS_SYSROOT} ${WORKDIR}/rootfs_ota

	fi
}

IMAGE_TYPEDEP_otaimg = "ostree"
