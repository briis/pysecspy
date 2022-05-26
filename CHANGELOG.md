# Change Log

This document will contain a list of all major changes.

## [1.3.4] - Unreleased

### Fixed

- If no Object detected return None instead of an empty array.
- Reset Event Objects when Motion ends.


## [1.3.3] - 2022-04-18

### Added

- Replaced the `event_score` attribute with two new attributes: `event_score_human` and `event_score_vehicle`. The `event_object` will still hold the object that has the highest score of the two, but if you only want to look for a person moving, you can check on the `event_score_human` value.

## [1.3.2] - 2022-04-17

### Fixed

- False object detections could occur, if neither Vehicle or Human. Now corrected.

## [1.3.1] - 2022-04-17

### Fixed

- Initial event_score value is needed when starting the loop.

## [1.3.0] - 2022-04-17

### Added

- Added percentage threshold for Object Detection on Motion events

## [1.2.1] - 2021-12-21

### Fixed

- Enure that the stream is properly closed, when exiting program.

### Added

- Adding Camera Online/Offline event detection, to ensure timely updates.


## [1.2.0] - 2021-12-20

### Added

- New function to activate a PTZ Preset. `set_ptz_preset`.
- List of defined PTZ presets per camera, now returned as `ptz_presets`
- PTZ capabilities now returned as `ptz_capabilities`. Value is 0 if no capabilities, else a binary integer.

### Changed

- Rewritten the setup function.
