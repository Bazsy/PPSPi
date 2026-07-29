# PPSPi hardware test report: v0.2.1

Status: **INHERITED TIMING BASELINE; PATCH-SPECIFIC HARDWARE CHECK PENDING**

PPSPi v0.2.1 changes dashboard startup, IPv4 listen defaults, and exact legacy
configuration migration. It does not change GPSD, PPS, Chrony, RTC, boot
overlays, hardware profiles, or the supported physical target. This report does
not invent a new pre-publication hardware run: production-signed v0.2.1 assets
exist only after explicit release publication.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.1` |
| Source commit | Pending merge of the stable release PR |
| Image filename | `ppspi-0.2.1-raspios-trixie-arm64.img.xz` |
| Compressed SHA-256 | Pending release workflow |
| Extracted SHA-256 | Pending release workflow |
| Imager manifest | `ppspi-0.2.1-raspios-trixie-arm64.rpi-imager-manifest` |
| Application archive | `ppspi-0.2.1-application.tar.gz` |
| Release workflow | Pending publication |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |

## Physical target

The supported target is unchanged:

- Raspberry Pi 4 Model B Rev 1.5;
- Uputronics GPS/RTC Expansion Board Rev 6.4;
- RV-3028-C7 RTC at I2C address `0x52`;
- active external GNSS antenna with broad sky view;
- trusted private LAN.

## Inherited evidence

The [v0.2.0 hardware report](hardware-test-report-v0.2.0.md) records physical
acceptance for first boot, Imager customization, account/network/SSH policy,
GPS at 115200 baud, 3D fix, active PPS, RV-3028 RTC, synchronized Stratum 1,
deep tests, host health, reboot persistence, loopback dashboard operation,
bounded storage, and diagnostics privacy. The v0.2.0 public seven-asset and
production-signature verification was subsequently completed in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95).

Automated patch coverage validates the new defaults, exact legacy migration,
custom-setting preservation, generated-config rollback coverage, image defaults,
unit enablement, CIDR admission, and dashboard behavior. This supports release
publication but does not replace the patch-specific direct-LAN measurement.

## Feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| GPS/PPS/RTC and Stratum 1 | INHERITED PASS | Runtime and configuration unchanged from v0.2.0 |
| Reboot persistence | INHERITED PASS | Timing/boot path unchanged |
| Dashboard sanitized API/UI | INHERITED PASS | Existing loopback behavior plus automated regression coverage |
| Default dashboard enable/bind | AUTOMATED PASS | Installer, image, config, server, and unit tests |
| Exact v0.2.0 default migration | AUTOMATED PASS | Real regeneration path and transactional coverage |
| Production v0.2.0-to-v0.2.1 apply | PENDING | Requires published signed v0.2.1 assets |
| Direct-LAN allow/deny boundary | PENDING | Must be measured on the appliance |
| Production rollback and reapply | PENDING | Must be exercised after publication |
| Exact public-image shortened smoke | PENDING | Public image does not exist before publication |
| Genuine reboot-required OS update | DEFERRED | Unrelated issue #95 scope |

## Post-publication procedure

After independently verifying all seven public assets:

1. record preservation sentinels and current service/configuration state;
2. use the installed v0.2.0 updater to check and apply exact version `0.2.1`;
3. verify timing health and preservation of accounts, SSH, network, cloud-init,
   PPSPi timing settings, and unrelated files;
4. verify the migrated default, automatic boot service/timer state, one allowed
   private client, and one routed out-of-CIDR denial;
5. inspect bounded sampling, no access logging, and no external browser requests;
6. perform local rollback and exact restoration checks, then reapply if desired;
7. attach sanitized evidence and final disposition to issue #95.

## Decision

The unchanged timing/hardware baseline and protected automated patch coverage are
sufficient to publish the assets needed for production update testing. The
patch-specific physical checks remain **PENDING**, not PASS, until recorded in
issue #95. PPSPi remains early-stage software and must not be the sole
production time source.
