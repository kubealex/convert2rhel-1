import os
import platform

from envparse import env


def test_backup_os_release_no_envar(shell, convert2rhel):
    """
    In this scenario there is no variable `CONVERT2RHEL_UNSUPPORTED_INCOMPLETE_ROLLBACK` set.
    This means the conversion is inhibited in early stage.
    This test case removes all the repos on the system which prevents the backup of some files.
    Satellite is being used in all of test cases.
    """

    # OL distros may not have wget installed
    assert shell("yum install wget -y").returncode == 0

    # Install katello package for satellite
    pkg_url = "https://dogfood.sat.engineering.redhat.com/pub/katello-ca-consumer-latest.noarch.rpm"
    pkg_dst = "/usr/share/convert2rhel/subscription-manager/katello-ca-consumer-latest.noarch.rpm"
    assert shell("wget --no-check-certificate --output-document {} {}".format(pkg_dst, pkg_url)).returncode == 0
    assert shell("rpm -i {}".format(pkg_dst)).returncode == 0

    # Move all repos to other location so it is not used
    assert shell("mkdir /tmp/s_backup && mv /etc/yum.repos.d/* /tmp/s_backup/").returncode == 0

    assert shell("find /etc/os-release").returncode == 0
    with convert2rhel(
        ("-y --no-rpm-va -k {} -o {} --debug --keep-rhsm").format(
            env.str("SATELLITE_KEY"),
            env.str("SATELLITE_ORG"),
        )
    ) as c2r:
        c2r.expect("set the environment variable 'CONVERT2RHEL_UNSUPPORTED_INCOMPLETE_ROLLBACK.")
        assert c2r.exitstatus != 0

    assert shell("find /etc/os-release").returncode == 0


def test_backup_os_release_with_envar(shell, convert2rhel):
    """
    In this scenario the variable `CONVERT2RHEL_UNSUPPORTED_INCOMPLETE_ROLLBACK` is set.
    This test case removes all the repos on the system and validates that
    the /etc/os-release package is being backed up and restored during rollback.
    Ref ticket: OAMG-5457. Note that after the test, the $releaserver
    variable is unset.
    """

    assert shell("find /etc/os-release").returncode == 0

    os.environ["CONVERT2RHEL_UNSUPPORTED_INCOMPLETE_ROLLBACK"] = "1"

    with convert2rhel(
        ("--no-rpm-va -k {} -o {} --debug --keep-rhsm").format(
            env.str("SATELLITE_KEY"),
            env.str("SATELLITE_ORG"),
        ),
    ) as c2r:
        c2r.expect("Continue with the system conversion?")
        c2r.sendline("y")
        c2r.expect("Continue with the system conversion?")
        c2r.sendline("y")
        # On OracleLinux8 there is one question less than on other distros
        if "oracle-8" not in platform.platform():
            c2r.expect("Continue with the system conversion?")
            c2r.sendline("y")
        c2r.expect("The tool allows rollback of any action until this point.")
        c2r.sendline("n")

    assert shell("find /etc/os-release").returncode == 0

    # Restore repos
    assert shell("mv /tmp/s_backup/* /etc/yum.repos.d/").returncode == 0


def test_missing_system_release(shell, convert2rhel):
    """
    It is required to have /etc/system-release file present on the system.
    If the file is missing inhibit the conversion.
    """

    # Make backup copy of the file
    assert shell("mv /etc/system-release /tmp/s_backup/").returncode == 0

    with convert2rhel(
        ("-y --no-rpm-va -k {} -o {} --debug").format(
            env.str("SATELLITE_KEY"),
            env.str("SATELLITE_ORG"),
        )
    ) as c2r:
        c2r.expect("Unable to find the /etc/system-release file containing the OS name and version")

    assert c2r.exitstatus != 0

    # Restore the system
    assert shell("mv /tmp/s_backup/system-release /etc/").returncode == 0
