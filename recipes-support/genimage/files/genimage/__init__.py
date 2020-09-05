#!/usr/bin/env python3
#
# Copyright (C) 2020 Wind River Systems, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

from genimage.genimage import set_subparser
from genimage.genyaml import set_subparser_genyaml
from genimage.exampleyamls import set_subparser_exampleyamls
from genimage.genimage import main
from genimage.genyaml import main_genyaml
from genimage.exampleyamls import main_exampleyamls

__all__ = [
    "set_subparser",
    "set_subparser_exampleyamls",
    "set_subparser_genyaml",
    "set_subparser_geninitramfs",
    "main",
    "main_exampleyamls",
    "main_genyaml",
    "main_geninitramfs",
]


