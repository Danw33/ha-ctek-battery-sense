# Contributing

Bug reports and focused pull requests are welcome.

## Before reporting a Bluetooth problem

- Confirm the monitor is visible in Home Assistant's Bluetooth advertisement
  monitor.
- Record whether its advertisement is connectable, its RSSI, and the Bluetooth
  source that received it.
- Confirm the official CTEK app is closed.
- Download the integration diagnostics.

Review logs and packet captures before attaching them publicly. Sender IDs,
Bluetooth addresses and BLE link material may identify or provide access to a
physical monitor.

## Development environment

The integration targets Python 3.14 and Home Assistant 2026.9 or newer.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements_test.txt
```

To test unreleased changes to the companion library, install it in editable
mode after installing the test requirements:

```bash
python -m pip install --editable ../py-ctek-battery-sense
```

Run the same checks as continuous integration:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

Format locally with `ruff format .`. Contributions should include tests for
new behaviour and failure paths.

## Scope

This project implements interoperability with lawfully accessed CTEK Battery
Sense monitors. Do not submit proprietary application binaries, decompiled
source, private packet captures, real Sender IDs, or functionality intended to
access a monitor without its printed Sender ID.

## Licence

Unless explicitly stated otherwise, submitted contributions are licensed under
the Apache License, Version 2.0.
