import subprocess
import sys

from dls_pmac_lib import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "dls_pmac_lib", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
