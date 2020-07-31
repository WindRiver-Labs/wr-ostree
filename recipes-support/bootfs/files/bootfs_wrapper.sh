#!/bin/bash
#  This script will build a mini bootstrap image for a target system.
#
#* Copyright (c) 2019 Jason Wessel - Wind River Systems, Inc.
#* 
#* This program is free software; you can redistribute it and/or modify
#* it under the terms of the GNU General Public License version 2 as
#* published by the Free Software Foundation.
#* 
#* This program is distributed in the hope that it will be useful,
#* but WITHOUT ANY WARRANTY; without even the implied warranty of
#* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#* See the GNU General Public License for more details.
#* 
#* You should have received a copy of the GNU General Public License
#* along with this program; if not, write to the Free Software
#* Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
while getopts "e:hL" opt; do
    case ${opt} in
        e)
            ENVFILE=$OPTARG
            ;;
        h)
            $OECORE_NATIVE_SYSROOT/usr/share/bootfs/scripts/bootfs.sh --help
            exit 0
    esac
done

export IMAGE_ROOTFS="$PWD/bootfs"
export DEPLOY_DIR_IMAGE
eval `cat $ENVFILE`

$OECORE_NATIVE_SYSROOT/usr/share/bootfs/scripts/bootfs.sh $@
