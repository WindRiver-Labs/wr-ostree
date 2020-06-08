#!/bin/bash

source $OECORE_NATIVE_SYSROOT/usr/bin/_create_full_image_h.sh

while getopts "r:l:t:h" opt; do
        case ${opt} in
                r)
                        RPM_REPO=$OPTARG
			;;
                l)
                        APPEND_PKG_LIST=$OPTARG
			if ! test -e ${APPEND_PKG_LIST};then echo "Error: ${RPM_REPO} does not exist"; usage; fi
                        ;;
                t)
                        IMAGE_TYPE=$OPTARG
			WKS_FILE="${IMAGE_TYPE}.wks"
                        ;;
                h)
                        usage
			;;
		*)
			usage
			;;
	esac
done

main_process(){
	pseudo
	#file_check
	do_clean
	prepare_work
	create_mount_rootfs
	create_ram_rootfs
	create_initrd
	create_wic_image
}

main_process $@
