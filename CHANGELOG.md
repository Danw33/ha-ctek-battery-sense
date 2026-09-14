# Changelog

All notable changes to this project are documented in this file.

## 0.2.0

- Moved Bluetooth communication, protocol codecs, history synchronisation, and
  State of Charge calculation into the independently released and typed
  `ctek-battery-sense` Python package.
- Pinned the external runtime dependency to version 0.1.0 in the integration
  manifest, following Home Assistant dependency requirements.
- Renamed the public repository to `ha-ctek-battery-sense` and updated project
  links and development documentation.
- Added strict type checking, hassfest validation, HACS validation, and
  automated dependency-update configuration.
- Updated the development and CI environment to Home Assistant 2026.9.2 and
  the current compatible validation-tool releases.
- Redacted persisted Bluetooth discovery keys from diagnostics and expanded
  configuration, diagnostics, and unload test coverage.
- Added local standard- and high-resolution integration icons for Home
  Assistant and HACS.

## 0.1.7

- Added a configurable per-device update interval from 5 minutes to 24 hours.
- Added disabled diagnostic sensors for the device sample interval and last
  successful synchronisation.
- Kept the last-successful-sync timestamp available while a monitor is away.
- Requested an immediate refresh when an unavailable monitor advertises again.
- Rate-limited advertisement-triggered recovery attempts to five minutes.
- Removed cached history when its integration entry is deleted.
- Hardened diagnostic redaction for Sender IDs and Bluetooth addresses.
- Removed the redundant English status-label attribute in favour of translated
  enum states.
- Added project metadata, quality-scale tracking, CI and expanded tests.
- Added focused BLE client, coordinator, entity, diagnostics and State of Charge
  tests with an enforced minimum of 95% overall coverage.
- Reworked the README for beta users and removed obsolete development notes.

## 0.1.6

- Updated the signal-strength unit for Home Assistant 2026.9 compatibility.

## 0.1.5

- Split history retrieval into bounded requests to prevent ESPHome proxy
  transport backpressure from dropping BLE notifications.

## 0.1.4

- Applied the application unlock before requesting BLE pairing.

## 0.1.0

- Added Bluetooth discovery, live readings, history synchronisation and State
  of Charge calculation.
