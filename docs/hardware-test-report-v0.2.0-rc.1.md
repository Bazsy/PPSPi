# PPSPi hardware test report: v0.2.0-rc.1

Status: **PREPARING — EXACT RC1 IMAGE NOT YET BUILT**

This report carries forward the release-tested physical timing target from
v0.1.0 and records focused v0.2 operational acceptance. It does not approve
stable v0.2.0 while issue #67 remains blocked.

## RC1 artifact identity

| Field | Value |
| --- | --- |
| Version | `0.2.0-rc.1` |
| Source commit | Pending |
| Image filename | `ppspi-0.2.0-rc.1-raspios-trixie-arm64.img.xz` |
| Compressed SHA-256 | Pending |
| Extracted SHA-256 | Pending |
| Imager manifest | `ppspi-0.2.0-rc.1-raspios-trixie-arm64.rpi-imager-manifest` |
| Manual workflow | Pending |
| Artifact ID/digest | Pending |
| Build date UTC | Pending |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |

## Physical target

- Raspberry Pi 4 Model B Rev 1.5;
- Uputronics GPS/RTC Expansion Board Rev 6.4;
- RV-3028-C7 RTC at I2C address `0x52`;
- active external GNSS antenna with broad sky view;
- wired trusted private LAN;
- known-good SD retained; separate SD used for candidate testing.

Precise location, addresses, MACs, serial numbers, credentials, and public NTP
source identities are excluded.

## Development-candidate evidence

The combined `0.2.0-dev` image from workflow
[30154360761](https://github.com/Bazsy/PPSPi/actions/runs/30154360761), commit
`5a71900758c6e152016a612f58d249af27f5d0a7`, compressed SHA-256
`e3ab8cb13d0df8438db892182879711375bd8d47bfd6f8e95b7c0e5b8be14db4`,
passed:

- Imager `cloudinit-rpi` customization and first boot;
- intended operator, hostname, locale, timezone, SSH, and wired network policy;
- image-origin updater state with no incomplete transaction;
- GPSD active at 115200 baud, 3D fix with 13 satellites at the recorded sample,
  active PPS, healthy RV-3028 RTC, synchronized PPS selection, and Stratum 1;
- every `ppstime-test` essential check;
- direct and confirmed timing/host health with no throttling or filesystem errors;
- reboot persistence;
- dashboard disabled/no listener by default, loopback enable/apply, exact routes,
  invalid-route/method rejection, bounded SQLite sample, browser rendering,
  labeled graph scales, and no failed units;
- regenerated diagnostics archive SHA-256
  `449bcacf7058c9d4e108bc7f7b8489788c9d0ec4b9bc93bf1ada2c27d9109a30`:
  exact 17-file set, 33,388 expanded bytes, eight identifying configuration
  fields redacted, seven selected-source identities reduced to
  `Selected source REDACTED`, and zero credentials, keys, tokens, coordinates,
  dashboard rows, or raw IPv4/IPv6 literals.

Hardware findings were fixed in PRs #89 through #93. Because those fixes were
hot-applied or found after flashing, the development artifact is evidence for
the fixes but is not the exact RC1 image.

## Exact RC1 shortened smoke

| Check | Result | Evidence |
| --- | --- | --- |
| Artifact integrity and build identity | NOT RUN | Pending candidate workflow |
| Fresh boot and cloud-init | NOT RUN | Pending flash |
| Operator/network/SSH preservation | NOT RUN | Pending flash |
| Netplan mode and persistent statoverride | NOT RUN | Must be `root:root 600` and recorded in dpkg statoverride |
| Updater image origin and clean transaction state | NOT RUN | Pending flash |
| GPS/PPS/RTC and Stratum 1 | NOT RUN | Pending flash |
| Deep PPSPi test | NOT RUN | Pending flash |
| Timing and host health | NOT RUN | Pending flash |
| Dashboard disabled/no listener default | NOT RUN | Pending flash |
| Zero failed units | NOT RUN | Pending flash |

## v0.2 feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| Passive timing/host monitoring | PASS on development candidate | PR #89 fixed sandbox mount interpretation; RC1 smoke pending |
| Configuration backup/restore | PASS in automated tests | Hardware restore not repeated for RC1 |
| Loopback dashboard | PASS on development candidate | Direct-LAN/out-of-CIDR mode not run and not claimed |
| Diagnostics privacy | PASS after PR #92 | RC1 smoke should regenerate a bounded archive |
| Application updater safe baseline | PASS | Production apply/rollback blocked until RC1 signed assets exist |
| OS maintenance no-reboot path | PASS in automated tests | Real reboot-required path remains BLOCKED by #67 |

## Security review

- [x] No project default password, SSH key, or Wi-Fi credential is included.
- [x] Production application public key is committed; private key is restricted
  to the release environment.
- [x] Diagnostics privacy regression was fixed and physically rechecked.
- [x] Dashboard loopback deployment and disabled default were physically checked.
- [ ] Exact RC1 image credential absence and first-boot behavior are pending.
- [ ] Exact RC1 public assets and signed application manifest are pending.

## Decision

RC1 candidate smoke: **NOT RUN**. Stable release gate: **NOT APPROVED**.

RC1 may be published only as a clearly marked prerelease after the exact-image
shortened smoke passes. Stable v0.2.0 remains blocked until issue #67's genuine
reboot-required update path passes on supported hardware.
