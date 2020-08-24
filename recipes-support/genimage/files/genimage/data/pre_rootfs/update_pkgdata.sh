#!/bin/bash

set -x

install_pkgdata() {
    pkgdatadir=$1
    if [ ! -d $pkgdatadir ]; then
        mkdir -p $pkgdatadir
        tar xf pkgdata.tar.bz2 -C $pkgdatadir
    fi
}

update_pkgdata() {
    REMOTE_PKGDATADIR=$1
    pkgdatadir=$OECORE_NATIVE_SYSROOT/../pkgdata

    cd "$OECORE_NATIVE_SYSROOT/usr/share/pkgdata"

    wget $REMOTE_PKGDATADIR/.pkgdata.tar.bz2.sha256sum -O .pkgdata.tar.bz2.sha256sum
    if [ $? -ne 0 ]; then
        echo "Download pkgdata.tar.bz2.sha256sum failed, use default pkgdata"
        install_pkgdata $pkgdatadir
        exit 0
    fi

    cat .pkgdata.tar.bz2.sha256sum | sha256sum -c
    if [ $? -eq 0 ]; then
        rm .pkgdata.tar.bz2.sha256sum
        install_pkgdata $pkgdatadir
        exit 0
    fi

    echo "The pkgdata is obsoleted, update it from rpm repo"
    wget $REMOTE_PKGDATADIR/.pkgdata.tar.bz2 -O .pkgdata.tar.bz2
    if [ $? -ne 0 ]; then
        echo "Update pkgdata from rpm repo failed, use default"
        rm -f .pkgdata.tar.bz2*
        install_pkgdata $pkgdatadir
        exit 0
    fi

    mv .pkgdata.tar.bz2.sha256sum pkgdata.tar.bz2.sha256sum
    mv .pkgdata.tar.bz2 pkgdata.tar.bz2

    rm $pkgdatadir -rf
    install_pkgdata $pkgdatadir

}

update_pkgdata $1

# cleanup
ret=$?
exit $ret
