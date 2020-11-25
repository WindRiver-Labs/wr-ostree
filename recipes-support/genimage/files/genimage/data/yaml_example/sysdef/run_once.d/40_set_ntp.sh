#!/bin/sh
# Set Wind River NTP
if [ -e /etc/ntp.conf ]; then
  echo "pool ntp-1.wrs.com" >> /etc/ntp.conf
  echo "pool ntp-2.wrs.com" >> /etc/ntp.conf
fi
