#!/bin/bash

export WORK_DIR="${PWD}/work_dir"
export MNT_ROOTFS_DIR="${WORK_DIR}/mnt_rootfs"
export RAM_ROOTFS_DIR="${WORK_DIR}/ram_rootfs"
export LOG_DIR="${WORK_DIR}/log_dir"
export IMAGE_TYPE="small"
export WKS_FILE="${IMAGE_TYPE}.wks"
export IMAGE_DIR="${WORK_DIR}/images"
export YUM_REPO_DIR="${MNT_ROOTFS_DIR}/rootfs/etc/yum.repos.d"

export PSEUDO_PREFIX="$OECORE_NATIVE_SYSROOT/usr"
export PSEUDO_LOCALSTATEDIR="${WORK_DIR}/pseudo"
export PSEUDO_NOSYMLINKEXP=1
export PSEUDO_PASSWD="${MNT_ROOTFS_DIR}/rootfs"
export LD_PRELOAD="${OECORE_NATIVE_SYSROOT}/usr/lib/pseudo/lib64/libpseudo.so"

# remote repo arg

#export RPM_REPO="${PWD}/tmp-glibc/deploy/rpm"
RPM_REPO="http://128.224.153.74/intel-x86-64/rpm"
#export APPEND_PKG_LIST="${PWD}/pkg_list"

# default rootfs: small
export MNT_ROOTFS_LIST="
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
"

# RAM rootfs
export RAM_ROOTFS_LIST="
	base-passwd busybox run-postinsts udev
	initramfs-framework-base
	initramfs-module-install
	initramfs-module-install-efi
	initramfs-module-setup-live
	initramfs-module-udev
"

usage(){
	cat<<EOF
This command will create a full image according a rpm package list.

Local Options:
   -r	specify the location of rpm packages
   -l	rpm packages list which will be installed
   -t   Specify image type to be created
   -h   This help information

EOF
	exit 0
}

fatal() {
	echo "$*"
	exit 1
}

check_return(){
	if [ $? -ne 0 ]; then
		fatal $@
	fi
}

file_check(){
	if [  ! -e "${RPM_REPO}" ];then
		fatal "default rpm repo does not exist, run with -r to specify it"
	fi
}

# there are two different rootfs ram and mounted rootfs which have
# two different environment.
export_variant(){
	export D="$1/rootfs"
	export OFFLINE_ROOT="$1/rootfs"
	export IPKG_OFFLINE_ROOT="$1/rootfs"
	export OPKG_OFFLINE_ROOT="$1/rootfs"
	export INTERCEPT_DIR="${OECORE_NATIVE_SYSROOT}/usr/share/poky/scripts/postinst-intercepts"
	export NATIVE_ROOT="$1/rootfs"
	export RPM_ETCCONFIGDIR="$1/rootfs"
	export RPM_NO_CHROOT_FOR_SCRIPTS=1
}

# arg1 is path of rootfs that is operated
dnf_cmd(){
	opt_dir=$1; shift
	dnf -y -v \
		--rpmverbosity=info \
		-c ${opt_dir}/rootfs/etc/dnf/dnf.conf \
		--setopt=reposdir=${opt_dir}/rootfs/etc/yum.repos.d \
		--installroot=${opt_dir}/rootfs \
		--setopt=logdir=${LOG_DIR} \
		--repofrompath=oe-repo,${RPM_REPO} \
		--nogpgcheck \
		$@
}

do_clean(){
	rm ${WORK_DIR} -rf
}

generate_repo_conf(){
	if [ -z "${PACKAGE_FEED_URIS}" ];then
		echo "Error: PACKAGE_FEED_URIS is NULL, remote rpm repo unavailable"
		return
	fi
	for uri in ${PACKAGE_FEED_URIS};do
		for arc in ${PACKAGE_FEED_ARCHS};do
			sub_uri=${uri#*//*/}
			repo_id="wr-remote-repo-${sub_uri////-}-${PACKAGE_FEED_BASE_PATHS}"
			repo_name="$repo_id-${PACKAGE_FEED_BASE_PATHS}.repo"
			echo "[$repo_id-$arc]"  >> ${YUM_REPO_DIR}/$repo_name
			echo "name=${repo_id//-/ }" >> ${YUM_REPO_DIR}/$repo_name
			echo "baseurl=$uri/${PACKAGE_FEED_BASE_PATHS}/$arc" >> ${YUM_REPO_DIR}/$repo_name
			if [ -n "${PACKAGE_FEED_SIGN}" ];then
				echo "repo_gpgcheck=1" >> ${YUM_REPO_DIR}/$repo_name
			fi
			if [ -n "${RPM_SIGN_PACKAGES}" ];then
				echo "gpgcheck=1" >> ${YUM_REPO_DIR}/$repo_name
			else
				echo "gpgcheck=0" >> ${YUM_REPO_DIR}/$repo_name
			fi
			echo >> ${YUM_REPO_DIR}/$repo_name
		done
	done
}

prepare_work(){
	if [ -e ${RPM_REPO} -a ! -e ${RPM_REPO}/repodata ]; then
		echo createrepo_c --update -q ${RPM_REPO}
		# create dnf repo
		createrepo_c --update -q ${RPM_REPO} || check_return "Error: run createrepo_c error"
	fi

	mkdir -p ${MNT_ROOTFS_DIR}/rootfs/etc/dnf/vars
	mkdir -p ${MNT_ROOTFS_DIR}/rootfs/etc/rpm
	mkdir -p ${YUM_REPO_DIR}
	mkdir -p ${IMAGE_DIR}

	# rpm configuration
	echo "intel_x86_64-pc-linux" > ${MNT_ROOTFS_DIR}/rootfs/etc/rpm/platform
	echo "%_transaction_color 7" > ${MNT_ROOTFS_DIR}/rootfs/etc/rpm/macros
	echo "%_prefer_color 7" >> ${MNT_ROOTFS_DIR}/rootfs/etc/rpm/macros
	echo "arch_compat: intel_x86_64: all any noarch x86 i586 i686" \
	     "core2_32 corei7_32 intel_x86_64 x86_64 core2_64 corei7_64" > \
	     ${MNT_ROOTFS_DIR}/rootfs/etc/rpmrc
	echo "buildarch_compat: intel_x86_64: noarch" >> ${MNT_ROOTFS_DIR}/rootfs/etc/rpmrc

	# dnf configuration
	echo -n "corei7_64:core2_64:x86_64:intel_x86_64:corei7_32:core2_32:i686:i586:x86" > \
	        ${MNT_ROOTFS_DIR}/rootfs/etc/dnf/vars/arch
	touch ${MNT_ROOTFS_DIR}/rootfs/etc/dnf/dnf.conf
	touch ${MNT_ROOTFS_DIR}/rootfs/etc/dnf/vars/releasever

	generate_repo_conf

	cp ${MNT_ROOTFS_DIR} ${RAM_ROOTFS_DIR} -rf
}

# arg1 is type of rootfs: mounted rootfs or ram rootfs
create_rootfs(){
	fs_dir=$1;shift
	export_variant $fs_dir

	# dnf step 1
	echo "dnf step 1"
	dnf_cmd $fs_dir makecache --refresh || check_return "Error: run dnf error"

	# dnf step 2
	echo "dnf step 2"
	dnf_cmd $fs_dir repoquery --installed --queryformat Package: %{name} %{arch} %{version} %{name}-%{version}-%{release}.%{arch}.rpm || check_return "Error: run dnf error"

	# dnf step 3
	echo "dnf step 3"
	dnf_cmd $fs_dir --releasever=100 --skip-broken install $@ || check_return "Error: run dnf error"

	# dnf step 4
	echo "dnf step 4"
	dnf_cmd $fs_dir --skip-broken clean all || check_return "Error: run dnf error"

}

install_error_check(){
	echo "INFO: check post install error"

	FAIL_LIST=`grep -r -w "ERROR" ${LOG_DIR}/dnf.rpm.log |grep -v "kernel" |gawk -F" " '{print $NF}'`
	if [ -n "$FAIL_LIST" ];then
		mkdir -p ${MNT_ROOTFS_DIR}/rootfs/etc/rpm-postinsts
	else
		return
	fi

	i=0
	for pk in ${FAIL_LIST};
	do
		rpm -q --root=${MNT_ROOTFS_DIR}/rootfs --queryformat %{postin} $pk > \
			${MNT_ROOTFS_DIR}/rootfs/etc/rpm-postinsts/$i-$pk
		chmod 755 ${MNT_ROOTFS_DIR}/rootfs/etc/rpm-postinsts/$i-$pk
		((i++))
	done
}

# $1 is mnt or ram rootfs dir
generate_module_depency(){
	if [ -e "$1/usr/lib/modules" ];then
		K_IMAGE=`ls $1/usr/lib/modules`
		depmod -a -b $1/usr ${K_IMAGE}
	elif [ -e "$1/lib/modules" ];then
		K_IMAGE=`ls $1/lib/modules/`
		depmod -a -b $1 ${K_IMAGE}
	fi
}

create_mount_rootfs(){
	echo "INFO: create mounted rootfs"
	if [ -e "${APPEND_PKG_LIST}" ];then
		MNT_ROOTFS_LIST="${MNT_ROOTFS_LIST} `cat ${APPEND_PKG_LIST}`"
	fi

	create_rootfs ${MNT_ROOTFS_DIR} ${MNT_ROOTFS_LIST}
	install_error_check
	generate_module_depency ${MNT_ROOTFS_DIR}/rootfs
}

create_ram_rootfs(){
	echo "INFO: create RAM rootfs"
	create_rootfs ${RAM_ROOTFS_DIR} ${RAM_ROOTFS_LIST}
	generate_module_depency ${RAM_ROOTFS_DIR}/rootfs
}

create_initrd(){
	echo "INFO: create initrd"
	cd ${RAM_ROOTFS_DIR}/rootfs
	find . | sort | cpio --reproducible -o -H newc > ../wrlinux-image-initramfs.rootfs.cpio
	cd ..
	gzip -f -9 -n -c --rsyncable wrlinux-image-initramfs.rootfs.cpio > \
		wrlinux-image-initramfs.rootfs.cpio.gz
	rm wrlinux-image-initramfs.rootfs.cpio

}

create_std_image(){
	echo "INFO: create standard wic image"
	echo "INFO: create ${IMAGE_TYPE}.wks file"
	echo "part /boot --source bootimg-efi --sourceparams=\"loader=grub-efi\"" \
		"--ondisk sda --label msdos --active --align 1024 --use-uuid" > ${MNT_ROOTFS_DIR}/${WKS_FILE}
	echo "part / --source rootfs --ondisk sda --fstype=ext4 --label platform --align 1024 --use-uuid" >> ${MNT_ROOTFS_DIR}/${WKS_FILE}
	echo "bootloader --ptable gpt --timeout=5 --append=\"rootfstype=ext4 rw console=ttyS0,115200 console=tty0\"" >> ${MNT_ROOTFS_DIR}/${WKS_FILE}

	printf 'fs0:EFI\BOOT\\bootx64.efi\n' >${MNT_ROOTFS_DIR}/rootfs/boot/startup.nsh

	wic create -r ${MNT_ROOTFS_DIR}/rootfs -k ${MNT_ROOTFS_DIR}/rootfs/boot -m -s ${MNT_ROOTFS_DIR}/${WKS_FILE} -o ${IMAGE_DIR}
}

create_wic_image(){
	if [ $IMAGE_TYPE == "small" ]; then
		create_std_image
	fi
}

