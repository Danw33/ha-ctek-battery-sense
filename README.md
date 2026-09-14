# CTEK Battery Sense Custom Component for Home Assistant

An **unofficial** Home Assistant integration for the CTEK Battery Sense 40-149
Bluetooth battery monitor. It connects locally through Home Assistant's
Bluetooth stack and does not require the CTEK app or a cloud service during
normal operation.

The integration provides live battery voltage and temperature, calculates the
same State of Charge and battery-status categories used by the CTEK app, and
supports multiple monitors as separate Home Assistant devices.

> [!IMPORTANT]
> This project is independent and is not affiliated with, endorsed by, or
> supported by CTEK Sweden AB. It is intended for informational monitoring and
> must not be relied upon as a safety system or as the sole indication that a
> battery or vehicle is safe to use.

## Supported devices

- CTEK Battery Sense 40-149, hardware model CTEK1088

Only the 12 V Battery Sense model above has been tested. Other CTEK products
that advertise different Bluetooth services are not currently supported.

## Requirements

- Home Assistant 2026.9.0 or newer
- A connectable Home Assistant Bluetooth adapter or ESPHome Bluetooth proxy
- The 11-character Sender ID printed on the monitor or its packaging
- The battery capacity in ampere-hours

Advertisement-only proxies can discover a monitor but cannot establish the
encrypted GATT connection needed to read it. In Home Assistant's Bluetooth
advertisement monitor, the selected source must report `connectable: true`.

For ESPHome, active Bluetooth proxy connections must be enabled:

```yaml
bluetooth_proxy:
  active: true
```

The CTEK app should be closed while Home Assistant connects. The sender
supports only one active BLE connection at a time.

## Installation

### HACS custom repository

1. Open HACS in Home Assistant.
2. Add `https://github.com/Danw33/ha-ctek-battery-sense` as a custom integration
   repository.
3. Install **CTEK Battery Sense**.
4. Restart Home Assistant.

### Manual installation

1. Copy `custom_components/ctek_battery_sense` into the `custom_components`
   directory in the Home Assistant configuration directory.
2. Restart Home Assistant.

## Configuration

When a connectable monitor is nearby, Home Assistant discovers it automatically:

1. Open **Settings > Devices & services**.
2. Select the discovered **CTEK Battery Sense** integration.
3. Enter the Sender ID printed on the monitor or box.
4. Enter the battery's rated capacity in ampere-hours.

Repeat the process for each monitor. The Sender ID is not included in the BLE
advertisement, so it cannot be filled automatically.

### Options

Open the configured integration and select **Configure** to change:

- **Battery capacity**: 5–200 Ah. Changing this recalculates State of Charge
  from the monitor's stored voltage history.
- **Update interval**: 5–1,440 minutes. The default is five minutes.

Five minutes matches the monitor's internal history sample interval. Longer
intervals reduce BLE connection activity because missed history samples are
downloaded during the next successful sync.

## Entities

The following entities are enabled by default:

| Entity | Description |
| --- | --- |
| Voltage | Live battery-terminal voltage |
| Temperature | Live temperature measured by the sender |
| State of charge | Calculated battery State of Charge |
| Battery status | Battery OK, Charge soon, or Charge now |

The following diagnostic entities are disabled by default:

| Entity | Description |
| --- | --- |
| Signal strength | RSSI of the most recent connectable advertisement |
| Uptime | Time since the monitor last restarted |
| Cached history records | Number of voltage samples held for calculation |
| Device sample interval | Monitor's internal history interval |
| Last successful sync | Time of the last complete data update |

The last-successful-sync entity remains available when the monitor is out of
range so dashboards can distinguish an old reading from a current one.

## Data updates and availability

Home Assistant connects to each monitor every five minutes by default. A normal
update reads live values and downloads only the history accumulated since the
previous update. When an unavailable monitor's advertisement reappears, it
requests an immediate refresh instead of waiting for the next scheduled poll.
Recovery attempts are rate-limited to avoid repeatedly connecting to a monitor
that is visible but temporarily unable to complete a read.

The first update can take around two minutes when all 30,000 history positions
must be downloaded. Later incremental updates are much shorter.

Voltage, temperature, State of Charge and battery status become unavailable
when Home Assistant cannot reach the monitor. This deliberately prevents stale
measurements from being presented to automations as current data. The monitor
continues recording locally, and missed samples are retrieved the next time it
is reached. Home Assistant Recorder states are not backfilled for the period in
which the entities were unavailable.

The circular history holds approximately 104 days at the normal five-minute
sample interval. Data older than that cannot be recovered if the monitor has
not synchronised in the meantime.

## Example uses

- Add voltage, State of Charge and temperature to a vehicle dashboard card.
- Alert when State of Charge falls below a chosen threshold while the reading
  is available.
- Use **Last successful sync** to distinguish a parked vehicle that is away
  from home from a monitor that has stopped reporting unexpectedly.

For example, this automation sends a persistent notification when a battery
drops below 35%. Replace the entity ID with the State of Charge entity created
for your monitor:

```yaml
alias: Vehicle battery needs charging
triggers:
  - trigger: numeric_state
    entity_id: sensor.ctek_state_of_charge
    below: 35
actions:
  - action: persistent_notification.create
    data:
      title: Vehicle battery
      message: The starter battery State of Charge is below 35%.
```

## Troubleshooting

### The monitor is discovered but cannot be configured

- Confirm its advertisement has `connectable: true`.
- Confirm the ESPHome proxy has `bluetooth_proxy.active` enabled.
- Move the proxy closer and retry; reliable GATT operation needs more signal
  margin than passive advertisement reception.
- Force-close the CTEK app and temporarily disable Bluetooth on nearby phones
  previously paired with the monitor.

### Pairing fails

Use a current ESPHome release and configure the proxy for bonding:

```yaml
esp32_ble:
  auth_req_mode: bond
```

If pairing still fails, turn off Bluetooth on previously paired phones,
disconnect the Battery Sense sender from the battery for at least 30 seconds,
reconnect it, and retry while the phones remain disconnected.

### Entities become unavailable

Check the disabled signal-strength and last-successful-sync entities. An RSSI
near the receiver sensitivity limit can disappear because of ordinary RF
variation even when neither vehicle nor proxy has moved. Repositioning a proxy
by a small distance can materially change reception around metal bodywork.

### Initial synchronisation times out

Keep the monitor and proxy close together for the first synchronisation. The
integration deliberately downloads history in small requests to avoid filling
the ESPHome-to-Home Assistant transport buffers.

## Diagnostics

Download diagnostics from the integration entry's menu when reporting a
problem. Sender IDs, Bluetooth addresses and Bluetooth-source addresses are
redacted. Raw packet captures and Home Assistant logs may still contain device
identifiers, so review them before publishing.

## Removal

1. Open **Settings > Devices & services**.
2. Open **CTEK Battery Sense**.
3. Delete the relevant integration entry.
4. Remove the custom integration through HACS, or delete
   `custom_components/ctek_battery_sense` for a manual installation.
5. Restart Home Assistant after removing the integration files.

Removing an entry also removes its Home Assistant entities and the locally
cached history used for State of Charge calculation. It does not change or
erase history stored on the physical monitor.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local checks and contribution
guidance. Progress toward Home Assistant's Integration Quality Scale is tracked
in `custom_components/ctek_battery_sense/quality_scale.yaml`.

Bluetooth communication, protocol decoding, history synchronisation, and State
of Charge calculation are provided by the independently released
[`ctek-battery-sense`](https://github.com/Danw33/py-ctek-battery-sense) Python
library. The integration pins its exact library release in `manifest.json`, as
required by Home Assistant.

## Licence

Copyright © 2026 Daniel Wilson ([@Danw33](https://github.com/Danw33))

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

CTEK and Battery Sense are trademarks of their respective owners.
