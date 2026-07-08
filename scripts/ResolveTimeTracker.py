"""Entry point intended for DaVinci Resolve's Scripts menu.

Implementation starts after Phase 0 confirms the Resolve API surface.
"""

from resolve_time_tracker import __version__


def main() -> None:
    print(f"Resolve Time Tracker {__version__}")


if __name__ == "__main__":
    main()
