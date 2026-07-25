# PPSPi hardware test report: v0.2.0

Status: **AVAILABLE HARDWARE SCOPE PASSED; PRODUCTION-ONLY FOLLOW-UP DEFERRED**

This report records the physical v0.2.0 acceptance completed before publication.
The exact public image is rebuilt only after explicit release publication, so
its shortened smoke and public-asset verification remain tracked in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95) under the v0.3 milestone.
They are not represented as v0.2.0 passes.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.0` |
| Source commit | Pending merge of the stable release PR |
| Image filename | `ppspi-0.2.0-raspios-trixie-arm64.img.xz` |
| Compressed SHA-256 | Pending release workflow |
| Extracted SHA-256 | Pending release workflow |
| Imager manifest | `ppspi-0.2.0-raspios-trixie-arm64.rpi-imager-manifest` |
| Release workflow | Pending publication |
| Build date UTC | Pending release workflow |
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

## Combined-candidate evidence

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

Hardware findings were fixed in PRs #89 through #93. The fixes were individually
rechecked on the appliance where applicable and are covered by the protected
automated suite. The combined development artifact predates some final commits,
so it is evidence for the exercised hardware scope rather than an exact public
v0.2.0-image smoke.

## Feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| GPS/PPS/RTC, Stratum 1, reboot persistence | PASS | Combined development candidate |
| Passive timing and host monitoring | PASS | PR #89 fixed sandbox mount interpretation |
| Configuration backup/restore | PASS | Automated apply/rollback coverage; export exercised |
| Loopback dashboard | PASS | Default-disabled and browser behavior checked |
| Direct-LAN dashboard allow/deny | DEFERRED | Issue #95; not part of accepted loopback deployment |
| Diagnostics privacy | PASS | Regenerated archive inspected after PR #92 |
| Application updater safe baseline | PASS | Automated signed/update/recovery coverage |
| Production v0.2.0 apply/rollback | DEFERRED | Requires assets created by publication; issue #95 |
| OS maintenance no-reboot path | PASS | Automated and available appliance checks |
| Genuine reboot-required update path | DEFERRED | Requires a real signed update; issue #95 |
| Exact public-image shortened smoke | DEFERRED | Public image does not exist before publication; issue #95 |

## Security review

- [x] No project default password, SSH key, or Wi-Fi credential is included.
- [x] Production application public key is committed; private key is restricted
  to the release environment.
- [x] Diagnostics privacy regression was fixed and physically rechecked.
- [x] Dashboard loopback deployment and disabled default were physically checked.
- [x] Netplan renderer mode and persistent statoverride are validated during
  installation and mounted-image checks.
- [ ] Exact public v0.2.0 image and seven public assets await the release workflow.

## Decision

The available supported-hardware acceptance scope is **PASS**. The maintainer
explicitly approved publication on 2026-07-25 so the appliance can be flashed
before relocation. The production-only and post-publication checks above remain
open in issue #95; this report does not convert them to passes or claim that the
exact public image was already flashed.
