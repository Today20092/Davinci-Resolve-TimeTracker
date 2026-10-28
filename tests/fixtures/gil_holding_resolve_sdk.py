"""Disposable SDK boundary that holds its interpreter's GIL on request."""

import ctypes
import os
from pathlib import Path


ROOT = Path(__file__).parent


class Project:
    def GetName(self):
        return "Test project"

    def IsRenderingInProgress(self):
        return False

    def GetCurrentTimeline(self):
        return None


class Manager:
    def GetCurrentProject(self):
        return Project()


class Resolve:
    def GetProductName(self):
        return "Test Studio"

    def GetVersionString(self):
        return "test"

    def GetProjectManager(self):
        if (ROOT / "block").exists():
            milliseconds = int((ROOT / "block").read_text() or "3000")
            (ROOT / "entered").touch()
            if os.name == "nt":
                ctypes.PyDLL("kernel32").Sleep(milliseconds)
            else:
                ctypes.PyDLL(None).usleep(milliseconds * 1000)
        return Manager()

    def GetCurrentPage(self):
        return "edit"


def scriptapp(name):
    assert name == "Resolve"
    return Resolve()
