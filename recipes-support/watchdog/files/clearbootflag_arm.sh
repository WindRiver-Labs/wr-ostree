#!/bin/sh

#* Copyright (c) 2018 Wind River Systems, Inc.
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

partbase=`cat /proc/mounts |grep "sysroot " | awk '{print $1}' | awk -F 'p' '{print $1}'`
part=${partbase}'p1'
tdir=`mktemp -d`
if [ "$tdir" != "" ] ; then
	mount ${part} ${tdir}
	printf '0\0WR' > ${tdir}/boot_cnt
	umount ${tdir}
	rm -rf ${tdir}
fi

