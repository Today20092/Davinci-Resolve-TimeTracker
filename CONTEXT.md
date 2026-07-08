# Resolve Time Tracker

Resolve Time Tracker tracks billable editing time for DaVinci Resolve Free projects while preserving privacy and avoiding unattended-time false positives.

## Language

**Resolve Project**:
A project currently open in DaVinci Resolve and used as the billing boundary for tracked time.
_Avoid_: File, job

**Page**:
The Resolve workspace where activity occurs: Media, Cut, Edit, Fusion, Color, Fairlight, Deliver, Render/Export, or Unknown.
_Avoid_: Tab, view

**Active Work**:
Time that should count toward billing because the user is interacting with Resolve, reviewing playback, or rendering/exporting.
_Avoid_: Usage, presence

**Idle**:
A state where the user's inactivity has exceeded the configured idle timeout and time should stop accruing unless Resolve is rendering/exporting.
_Avoid_: Away, inactive

**Session**:
A contiguous billable time span attributed to one Resolve Project, Page, and activity category.
_Avoid_: Entry, log row

**Heartbeat**:
A periodic timestamp showing a session was still alive, used to recover unfinished sessions after shutdown or crash.
_Avoid_: Ping, pulse
