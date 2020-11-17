#!/bin/sh
# Set hostname based on MAC address or current time
if [ -e /etc/hostname ]; then
  old=`cat /etc/hostname`
fi
interface=`ls /sys/class/net/e*/address | head -1`
if [ -n $interface ] && [ -e $interface ]; then
    mac=`cat $interface`
    new=`echo $mac | sed s/:/-/g`
else
    new=`date +%s`
fi
hostnamectl set-hostname $new
if [ -n "$old" ]; then
    sed -i "s/ $old$/ $new/g" /etc/hosts
fi
