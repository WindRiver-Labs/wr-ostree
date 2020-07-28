#!/usr/bin/env python3

import sys
import os
import argparse
import glob
import re
import logging
from appsdk.appsdk import AppSDK
from create_full_image.utils import set_logger
import create_full_image.utils as utils
import create_full_image

logger = logging.getLogger('appsdk')

def set_subparser(subparsers=None):
    if subparsers is None:
        sys.exit(1)

    parser_gensdk = subparsers.add_parser('gensdk', help='Generate a new SDK')
    parser_gensdk.add_argument('-f', '--file',
                               help='An input yaml file specifying image information. Default to image.yaml in current directory',
                               default='image.yaml')
    parser_gensdk.add_argument('-o', '--output',
                               help='The path of the generated SDK. Default to deploy/AppSDK.sh in current directory',
                               default='deploy/AppSDK.sh')
    parser_gensdk.set_defaults(func=gensdk)
    
    parser_checksdk = subparsers.add_parser('checksdk', help='Sanity check for SDK')
    parser_checksdk.set_defaults(func=checksdk)

    parser_buildrpm = subparsers.add_parser('genrpm', help='Build RPM package')
    parser_buildrpm.add_argument('-f', '--file', required=True,
                                 help='A yaml or spec file specifying package information')
    parser_buildrpm.add_argument('-i', '--installdir', required=True,
                                 help='An installdir serving as input to generate RPM package')
    parser_buildrpm.add_argument('-o', '--outputdir',
                                 help='Output directory to hold the generated RPM package',
                                 default='deploy/rpms')
    parser_buildrpm.add_argument('--pkgarch',
                                 help='package arch about the generated RPM package', default=None)
    parser_buildrpm.set_defaults(func=buildrpm)

    parser_publishrpm = subparsers.add_parser('publishrpm', help='Publish RPM package')
    parser_publishrpm.add_argument('-r', '--repo', required=True,
                                   help='RPM repo path')
    parser_publishrpm.add_argument('rpms', help='RPM package paths',
                                   nargs='*')
    parser_publishrpm.set_defaults(func=publishrpm)

def main():
    if os.getuid() == 0:
        raise Exception("Do not use appsdk as root.")

    parser = argparse.ArgumentParser(
        description='Application SDK Management Tool for CBAS',
        epilog='Use %(prog)s <subcommand> --help to get help')
    parser.add_argument('-d', '--debug',
                        help = "Enable debug output",
                        action='store_const', const=logging.DEBUG, dest='loglevel', default=logging.INFO)
    parser.add_argument('-q', '--quiet',
                        help = 'Hide all output except error messages',
                        action='store_const', const=logging.ERROR, dest='loglevel', default=logging.INFO)

    subparsers = parser.add_subparsers(help='Subcommands. "%(prog)s <subcommand> --help" to get more info')

    set_subparser(subparsers)

    # Add genimage to appsdk
    create_full_image.set_subparser(subparsers)

    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit(1)

    args = parser.parse_args()
    set_logger(logger)
    logger.setLevel(args.loglevel)
    args.func(args)

def gensdk(args):
    appsdk = AppSDK()
    appsdk.generate_sdk(args.file, args.output)

def checksdk(args):
    appsdk = AppSDK()
    appsdk.check_sdk()

def buildrpm(args):
    appsdk = AppSDK()
    appsdk.buildrpm(args.file, args.installdir, rpmdir=args.outputdir, pkgarch=args.pkgarch)

def publishrpm(args):
    appsdk = AppSDK()
    appsdk.publishrpm(args.repo, args.rpms)
    
if __name__ == "__main__":
    try:
        ret = main()
    except Exception:
        ret = 1
        import traceback
        traceback.print_exc()
    sys.exit(ret)
