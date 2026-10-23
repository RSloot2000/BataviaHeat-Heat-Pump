# BataviaHeat R290 — Release 0.5.6

**Newntide cascade: second outdoor unit now fully supported.**

If you run a two-unit Newntide cascade (two outdoor units on one bus), this
release adds monitoring for the second unit and makes your energy / COP / EER
figures account for **both** units.

## What's new

### Module 1# (second unit) cloud sensors
Seven new cloud sensors for the second outdoor unit, so a cascade reports both
units instead of just the first:

- Water inlet temperature
- Water outlet temperature
- Pump target speed
- Pump flow rate
- Pump control signal
- Pump feedback signal
- Pump fault information

These sit alongside your existing module 0# sensors — no existing entity IDs,
dashboard cards or history are affected.

## Improvements

### Total cascade power, energy and COP/EER
Previously, thermal power (and the energy / COP / EER sensors built on it) was
computed from a single unit. It now sums **both** cascade units, so a two-unit
system reports its true total heating/cooling power, cumulative energy, and COP/EER.

- A healthy multi-unit system at high load is no longer dropped to *unavailable*.
- A single implausible reading still falls back gracefully (reported on its own).
- Cloud-only setups keep working exactly as before.

## For developers

- Added unit tests for the thermal-power derivation (module 0# Modbus/cloud and
  module 1# cloud paths, plus the cascade summing and sanity caps).

---

Thanks to @tcjw3 for the cascade sensor work (issue #3) and the review that
shaped it. As always, report any oddity in issues — cascade setups are rarer,
so your feedback helps make this solid for everyone.
