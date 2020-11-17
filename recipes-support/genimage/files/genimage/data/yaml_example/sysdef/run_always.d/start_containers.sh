#!/bin/sh
# Start containers listed in /etc/sysdef/run_on_upgrade.d/XXXX/containers.dat
latest=`ls /etc/sysdef/run_on_upgrade.d/ -1 -v -r | head -n 1`
dirname="/etc/sysdef/run_on_upgrade.d/${latest}"
dat=`cat ${dirname}/containers.dat`
for container_name in ${dat}; do
    docker start ${container_name}
done
