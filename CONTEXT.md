# Resolve Time Tracker

Resolve Time Tracker tracks billable editing time for DaVinci Resolve Studio projects while preserving privacy and avoiding unattended-time false positives.

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

**Tracking Observation**:
A periodic reading of the open Resolve Project, Page, rendering state, and user activity used to decide whether Active Work continues. A Tracking Observation may update live state without persisting a Heartbeat.
_Avoid_: Poll, sample

**Tracked Launch**:
A user-initiated start of DaVinci Resolve that also starts time tracking for that Resolve session.
_Avoid_: Automatic startup, background watcher
