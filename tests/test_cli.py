import subprocess
import sys

from dls_pmaclib import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "dls_pmaclib", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
