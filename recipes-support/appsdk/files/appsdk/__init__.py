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

logger = logging.getLogger('appsdk')
set_logger(logger)

def main():
    parser = argparse.ArgumentParser(
        description='AppSDK for CBAS',
        epilog='Use %(prog)s <subcommand> --help to get help')
    parser.add_argument('-d', '--debug',
                        help = "Enable debug output",
                        action='store_const', const=logging.DEBUG, dest='loglevel', default=logging.INFO)
    parser.add_argument('-q', '--quiet',
                        help = 'Hide all output except error messages',
                        action='store_const', const=logging.ERROR, dest='loglevel', default=logging.INFO)

    subparsers = parser.add_subparsers(help='Subcommands. "appsdk <subcommand> --help" to get more info')

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
    
    if len(sys.argv) == 1:
        parser.print_help()
        exit(1)

    args = parser.parse_args()
    logger.setLevel(args.loglevel)
    args.func(args)


def gensdk(args):
    appsdk = AppSDK()
    appsdk.generate_sdk(args.file, args.output)

def checksdk(args):
    appsdk = AppSDK()
    appsdk.check_sdk()
    
if __name__ == "__main__":
    try:
        ret = main()
    except Exception:
        ret = 1
        import traceback
        traceback.print_exc()
    sys.exit(ret)
