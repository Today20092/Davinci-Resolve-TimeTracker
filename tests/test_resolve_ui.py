import unittest

from resolve_time_tracker.resolve_ui import _fusion_app


class ResolveUiTest(unittest.TestCase):
    def test_uses_bmd_fusion_app_when_resolve_fusion_has_no_ui_manager(self):
        class Resolve:
            def Fusion(self):
                return type("ResolveFusion", (), {"UIManager": None})()

        usable_fusion = type("Fusion", (), {"UIManager": object()})()

        class Bmd:
            def scriptapp(self, name):
                self.requested = name
                return usable_fusion

        bmd = Bmd()

        self.assertIs(usable_fusion, _fusion_app(Resolve(), bmd, None))
        self.assertEqual("Fusion", bmd.requested)


if __name__ == "__main__":
    unittest.main()
