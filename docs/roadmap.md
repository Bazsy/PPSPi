# Roadmap

PPSPi has one release-tested hardware combination today and a deliberately open
path toward easier operation and broader hardware support. This roadmap is a
direction, not a promise of dates or compatibility before testing.

Roadmap milestones do not publish releases automatically. GitHub Release
publication remains a separate, explicit maintainer action after the documented
release gates pass.

## Available now

Version 0.1.0 is release-tested on:

- Raspberry Pi 4 Model B Rev 1.5;
- Uputronics GPS/RTC Expansion Board Rev 6.4 (V6.0+ profile);
- Raspberry Pi OS Lite 64-bit Trixie;
- an outdoor active GNSS antenna and wired Ethernet.

The release includes a Raspberry Pi Imager manifest, strict installer,
GPSD/Chrony/PPS integration, RTC support, diagnostics, controlled fallback, and
explicit release gates. See the
[v0.1.0 hardware report](hardware-test-report-v0.1.0.md).

## v0.2.x: unattended operation and easier setup

The next milestone makes the existing appliance easier to install, understand,
and leave running:

- public v0.1.0 7–14 day operational soak:
   [issue #60](https://github.com/Bazsy/PPSPi/issues/60);
- beginner-facing roadmap and quick start:
   [issue #63](https://github.com/Bazsy/PPSPi/issues/63) and
   [issue #65](https://github.com/Bazsy/PPSPi/issues/65);
- documented Experimental, Community-validated, and Release-tested support
   levels: [issue #64](https://github.com/Bazsy/PPSPi/issues/64);
- one-file published installation through the Imager manifest:
   [issue #66](https://github.com/Bazsy/PPSPi/issues/66);
- unattended signed OS security updates and a bounded weekly reboot window:
   [issue #67](https://github.com/Bazsy/PPSPi/issues/67);
- verified PPSPi application update and rollback:
   [issue #68](https://github.com/Bazsy/PPSPi/issues/68);
- configuration export and disaster recovery (implemented in `0.2.0-dev`):
   [issue #69](https://github.com/Bazsy/PPSPi/issues/69);
- host storage, temperature, throttling, and update health:
   [issue #77](https://github.com/Bazsy/PPSPi/issues/77);
- optional read-only LAN dashboard with short history graphs:
   [issue #78](https://github.com/Bazsy/PPSPi/issues/78).

These items are not a strict serial queue. The unchanged public-v0.1.0 soak in
issue #60 can run in parallel with documentation, design, and prototype work.
Configuration export/recovery in issue #69 should be established before relying
on application-update rollback, and issue #68 must integrate with the
maintenance-window behavior designed in issue #67.

Issue #60 intentionally remains on the unmodified public v0.1.0 image and must
not install or rely on the `0.2.0-dev` stateful health monitor. That monitor was
delivered in [issue #58](https://github.com/Bazsy/PPSPi/issues/58); it remains
notification-only and never restarts or reconfigures the timing chain.

## v0.3.x: contributor-led hardware expansion

Hardware work is split so one contributor can validate one setup. The first goal
is **experimental**, not release-tested, support. Experimental contributions use
a short evidence checklist and do not require a 24-hour run.

Raspberry Pi validation:

- Raspberry Pi 3 Model B/B+:
   [issue #71](https://github.com/Bazsy/PPSPi/issues/71);
- Compute Module 4 on the official IO Board:
   [issue #72](https://github.com/Bazsy/PPSPi/issues/72);
- Raspberry Pi 5 Model B:
   [issue #73](https://github.com/Bazsy/PPSPi/issues/73).

Specific GNSS/PPS products:

- Adafruit Ultimate GPS HAT (exact tested MTK3339/PA6H revision):
   [issue #74](https://github.com/Bazsy/PPSPi/issues/74);
- Waveshare MAX-M8Q GNSS HAT:
   [issue #75](https://github.com/Bazsy/PPSPi/issues/75);
- SparkFun GPS-RTK2 with ZED-F9P:
   [issue #76](https://github.com/Bazsy/PPSPi/issues/76).

A Raspberry Pi result applies only to the receiver, carrier, wiring, and profile
named in that report. A receiver result likewise applies only to the named Pi
setup. Passing two separate issues does not automatically validate their
cross-product combination.

Advanced or hardware-dependent work:

- generic operator-wired UART/PPS modules:
   [issue #18](https://github.com/Bazsy/PPSPi/issues/18);
- identified pre-V6.0 Uputronics revisions:
   [issue #22](https://github.com/Bazsy/PPSPi/issues/22).

Each issue names what must be measured. Similar-looking products, carrier boards,
or revisions are never included automatically. See
[hardware support levels](hardware-support-tiers.md).

## v1.0: stable appliance contract

[Issue #20](https://github.com/Bazsy/PPSPi/issues/20) owns the stable-release
criteria. Expected work includes:

- documented support and maintenance periods;
- upgrade and rollback guarantees;
- reproducibility and security expectations;
- release-tested hardware with no unresolved assumptions;
- authenticated NTS fallback as an option:
   [issue #70](https://github.com/Bazsy/PPSPi/issues/70);
- evidence from unattended operation and recovery testing.

PPSPi will not claim independently traceable timing accuracy without a traceable
reference and documented measurement method.

## Dashboard direction

There is no maintained plug-and-play package that understands the complete
GPSD, kernel PPS, Chrony, RTC, and PPSPi health chain.

[Issue #78](https://github.com/Bazsy/PPSPi/issues/78) will compare before
building:

1. **Netdata**, the closest all-in-one local dashboard with automatic Raspberry
   Pi system graphs and history, using a small PPSPi collector;
2. **node_exporter plus Prometheus/Grafana**, the mature advanced route that can
   consume the `ppstime-health --prometheus` output available in `0.2.0-dev`,
   preferably with Prometheus/Grafana on another host;
3. a small PPSPi read-only dashboard if existing options prove too heavy or too
   difficult to secure.

Any PPSPi dashboard stays optional and read-only. Configuration, service
restarts, updates, clock changes, and source selection remain outside its scope.

## How to help

You do not need to implement an entire milestone.

- Own one exact Pi or GNSS issue and post the requested sanitized evidence.
- Improve beginner wording or screenshots in
   [issue #65](https://github.com/Bazsy/PPSPi/issues/65).
- Test the one-file manifest path on another desktop OS for
   [issue #66](https://github.com/Bazsy/PPSPi/issues/66).
- Review update/rollback safety in
   [issues #67–#69](https://github.com/Bazsy/PPSPi/milestone/1).
- Prototype Netdata or Prometheus integration for
   [issue #78](https://github.com/Bazsy/PPSPi/issues/78).

Start with [CONTRIBUTING.md](../CONTRIBUTING.md). Hardware contributors should
also read [hardware support levels](hardware-support-tiers.md). Ask questions on
the issue before buying hardware or changing wiring; early evidence is useful
even when it finds incompatibility.
