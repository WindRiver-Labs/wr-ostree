#!/bin/sh
# Set Wind River NTP
if [ -e /etc/systemd/timesyncd.conf ]; then
  echo "NTP=147.11.1.11 147.11.100.50" >> /etc/systemd/timesyncd.conf
  systemctl restart systemd-timesyncd
fi
