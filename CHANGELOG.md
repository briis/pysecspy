# Change Log

This document will contain a list of all major changes.

## [1.2.0] - Unreleased

### Added

- New function to activate a PTZ Preset. `set_ptz_preset`.
- List of defined PTZ presets per camera, now returned as `ptz_presets`
- PTZ capabilities now returned as `ptz_capabilities`. Value is 0 if no capabilities, else a binary integer.

### Changed

- Rewritten the setup function.
