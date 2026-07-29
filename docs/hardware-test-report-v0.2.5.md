# PPSPi hardware test report: v0.2.5

Status: **v0.2.4 APPLY ROLLED BACK SAFELY; v0.2.5 APPLY PENDING**

This corrective patch is driven by live evidence from the supported Raspberry
Pi 4 Model B Rev 1.5 and Uputronics GPS/RTC Expansion Board Rev 6.4 appliance.

## Public v0.2.4 asset verification

All seven public v0.2.4 assets were independently downloaded. The release
inventory, GitHub digests, compressed image checksum, streamed decompressed image
hash, build metadata, Raspberry Pi Imager manifest, application archive, exact
managed inventory, and production minisign signature all passed verification.
The signing key ID was `8D0124C5DC5CE411`.

## Physical v0.2.4 update attempt

The appliance attempted transaction `20260729T133031Z-582d1b16-0.2.4`:

- source: v0.2.3 commit `e8eaf385a47890414d325d0e349491e4d60bee0f`;
- target: v0.2.4 commit `d5267cc009c6501fbf6bf65e0f452ebff4cb56f2`;
- result: `ROLLED_BACK`;
- failed validation: dashboard activation plus Chrony synchronization/source
  checks that had not yet settled at the instant activation failed.

The journal repeatedly recorded `[Errno 98] Address already in use` during
preflight and actual dashboard bind. Chrony selected a network source six seconds
later and PPS nine seconds later. After automatic rollback, all 16 essential
`ppstime-test --json` checks passed. This demonstrates transaction safety and
isolates the release blocker to immediate dashboard socket replacement rather
than PPS/GPS/Chrony health.

## Root cause reproduction

A local real HTTP request against an old non-`SO_REUSEADDR` server reproduced
immediate restart failure. Testing also proved that setting reuse only on the new
server does not fix old-nonreuse-to-new-reuse, and candidate traffic can prevent
new-reuse-to-old-nonreuse rollback. Therefore a timeout alone or reuse alone is
insufficient.

v0.2.5 combines consistent future reuse, bounded old-listener settling, and the
updater's root-only kernel lock passed through systemd. The candidate can bind
but cannot accept HTTP before transaction completion. If rollback replaces its
files, identity watching makes it exit before serving, so the restored old
server does not inherit candidate-created TCP `TIME_WAIT` state.

## Feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| Public v0.2.4 seven-asset verification | PASS | Image, metadata, archive, signature |
| Signed v0.2.4 application apply | SAFE FAILURE | Transaction rolled back |
| Automatic restoration | PASS | v0.2.3 identity/configuration restored |
| Post-rollback essential timing checks | PASS | All 16 checks passed |
| Immediate-restart root cause | PASS | Reproduced with a real HTTP request |
| Future reuse behavior | AUTOMATED PASS | Preflight and real server consistent |
| Exclusive/shared lock handoff | AUTOMATED PASS | Real kernel `flock` exercised |
| Rollback socket compatibility | AUTOMATED PASS | Candidate cannot serve before commit |
| Signed tmpfiles inventory | AUTOMATED PASS | Root-only runtime lock is managed |
| Production v0.2.3-to-v0.2.5 apply | PENDING | Requires published signed assets |
| Rollback/reapply and routed denial | PENDING | Continue issue #95 evidence |
| Public-image shortened smoke | PENDING | Post-publication |

GPSD configuration, PPS, Chrony policy, RTC, boot overlays, hardware profiles,
and the supported target are unchanged from the v0.2.0 physical timing
baseline.

## Decision

Publish signed v0.2.5 assets after protected checks pass, independently verify
all seven assets, and then repeat dashboard acceptance without manual
configuration or service action. Remaining physical checks stay **PENDING**
until recorded in [issue #95](https://github.com/Bazsy/PPSPi/issues/95).
