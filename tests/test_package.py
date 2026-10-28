import unittest
from importlib.metadata import version

from resolve_time_tracker import __version__


class PackageTest(unittest.TestCase):
    def test_version_matches_installed_package(self):
        self.assertEqual(__version__, version("resolve-time-tracker"))
