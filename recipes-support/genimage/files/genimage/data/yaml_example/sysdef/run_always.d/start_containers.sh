#!/bin/sh
# Start containers listed in /etc/sysdef/run_on_upgrade.d/XXXX/containers.dat
latest=`ls /etc/sysdef/run_on_upgrade.d/ -1 -v -r | head -n 1`
dirname="/etc/sysdef/run_on_upgrade.d/${latest}"
dat="${dirname}/containers.dat"
while read -r line; do
    [ "${line}" != "${line#\#}" ] && continue
    container_name=${line%% *}
    [ -z "${container_name}" ] && continue
    echo "systemctl start start-container@${container_name}.service"
    systemctl start start-container@${container_name}.service
done < ${dat}
