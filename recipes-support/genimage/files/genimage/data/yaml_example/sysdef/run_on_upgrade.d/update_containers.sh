#!/bin/sh
# Update containers listed in /etc/sysdef/run_on_upgrade.d/XXXX/containers.dat
# If container has already existed, rename it, pull a new one and run it.
dirname=`dirname ${BASH_SOURCE[0]}`
dat=`cat ${dirname}/containers.dat`
for container_name in ${dat}; do
    docker pull ${container_name}
    # Rename old if it is available
    container_id=`docker ps -a --filter=name=^${container_name}$ --format {{.ID}}`
    if [ -n "$container_id" ]; then
        curtime=`date +%Y%m%d%H%M`
        docker rename ${container_name} ${container_name}_$curtime
    fi
    docker run -it -d --name ${container_name} ${container_name}
done
