# -*- coding: utf-8 -*-
#
# Copyright(C) 2021 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os

from convert2rhel.grub import is_efi
from convert2rhel.systeminfo import system_info
from convert2rhel.utils import RestorableFile, mkdir_p


OPENJDK_RPM_STATE_DIR = "/var/lib/rpm-state/"
_SHIM_X64_PKG_PROTECTION_FILE_PATH = "/etc/yum/protected.d/shim-x64.conf"

logger = logging.getLogger(__name__)
shim_x64_pkg_protection_file = RestorableFile(_SHIM_X64_PKG_PROTECTION_FILE_PATH)  # pylint: disable=C0103


def check_and_resolve():
    perform_java_openjdk_workaround()
    unprotect_shim_x64()


def perform_java_openjdk_workaround():
    """Resolve a yum transaction failure on CentOS/OL 6 related to the java-1.7.0-openjdk package.

    The java-1.7.0-openjdk package expects that the /var/lib/rpm-state/ directory is present. Yet, it may be missing.
    This directory is supposed to be created by the copy-jdk-configs package during the system installation, but it does
    not do that: https://bugzilla.redhat.com/show_bug.cgi?id=1620053#c14.

    If the original system has an older version of copy-jdk-configs installed than the one available in RHEL repos, the
    issue does not occur because the copy-jdk-configs is updated together with the java-1.7.0-openjdk package and a
    pretrans script of the copy-jdk-configs creates the dir.

    In case there's no newer version of copy-jdk-configs available in RHEL but a newer version of java-1.7.0-openjdk is
    available, we need to create the /var/lib/rpm-state/ directory as suggested in
    https://access.redhat.com/solutions/3573891.
    """

    logger.info("Checking if java-1.7.0-openjdk is installed.")
    if system_info.is_rpm_installed(name="java-1.7.0-openjdk"):
        logger.info(
            "Package java-1.7.0-openjdk found. Applying workaround in"
            "accordance with https://access.redhat.com/solutions/3573891."
        )
        try:
            mkdir_p(OPENJDK_RPM_STATE_DIR)
        except OSError:
            logger.warning("Unable to create the %s directory." % OPENJDK_RPM_STATE_DIR)
        else:
            logger.info("openjdk workaround applied successfully.")
    else:
        logger.info("java-1.7.0-openjdk not installed.")


def unprotect_shim_x64():
    """Remove the shim-x64 package yum protection on UEFI-based Oracle Linux 7 systems as it causes a yum traceback.

    The package is protected through the /etc/yum/protected.d/shim-x64.conf file. It is installed with the
    Oracle Linux 7 shim-x64 package. The same package on RHEL 7 does not install this file - it's OL specific - no
    need to add it back after a successful conversion to RHEL.

    Related: https://bugzilla.redhat.com/show_bug.cgi?id=2009368
    """
    logger.info("Removing shim-x64 package yum protection.")
    if system_info.id == "oracle" and system_info.version.major == 7:
        if not is_efi():
            logger.info("Relevant to UEFI firmware only. Skipping.")
            return
        shim_x64_pkg_protection_file.backup()
        try:
            os.remove(shim_x64_pkg_protection_file.filepath)
            logger.info(
                "'%s' removed in accordance with https://bugzilla.redhat.com/show_bug.cgi?id=2009368."
                % shim_x64_pkg_protection_file.filepath
            )
        except OSError as err:
            # For permissions reasons (unlikely as we run as root) or because it does not exist
            logger.error("Unable to remove '%s': %s" % (shim_x64_pkg_protection_file.filepath, err.strerror))
    else:
        logger.info("Relevant to Oracle Linux 7 only. Skipping.")
