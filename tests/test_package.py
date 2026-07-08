import unittest

from resolve_time_tracker import __version__


class PackageTest(unittest.TestCase):
    def test_version_exists(self):
        self.assertTrue(__version__)
