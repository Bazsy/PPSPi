# PPSPi hardware test report: v0.2.6

Status: **v0.2.5 CHECK REJECTED SAFELY; v0.2.6 APPLY PENDING**

This compatibility patch is driven by live evidence from the supported Raspberry
Pi 4 Model B Rev 1.5 and Uputronics GPS/RTC Expansion Board Rev 6.4 appliance.

## Public v0.2.5 asset verification

All seven public v0.2.5 assets were independently downloaded and verified. The
compressed image was 728,159,412 bytes with SHA-256
`f5a6e292ae41f245d20f7bc81325c78869ebac305893835ae79cd70a8250e70a`.
The streamed decompressed image was 3,623,878,656 bytes with SHA-256
`1444a033b50328edea2d4734fe5d2acd355419bbdb509ef3770bc42591d9eb40`.
The 80,917-byte application archive had SHA-256
`5062db9d07724119c8475b1fe30a1ddbe4f8ae0039d0abf8376d2752f41943ad`
and verified with production minisign key ID `8D0124C5DC5CE411`.

## Physical v0.2.5 check

On the v0.2.3 appliance:

```console
sudo ppstime-update check --version 0.2.5
```

failed closed with:

```text
ppstime-update: payload path is outside the PPSPi application boundary: usr/lib/tmpfiles.d/ppstime.conf
```

Manifest validation occurs before archive download/extraction, transaction
creation, file replacement, or service reconciliation. No application, timing,
configuration, or dashboard state changed; the appliance remains on v0.2.3.

## v0.2.6 correction

v0.2.6 removes the incompatible tmpfiles member and adds the equivalent
`ppstime-dashboard-lock.service`, whose path is already accepted by v0.2.3. The
service prepares the same root-only lock as a required dashboard dependency after
boot. During an update it opens the existing inode without truncation, so the
old updater's exclusive `flock` remains authoritative while the candidate
Dashboard waits through systemd's inherited descriptor.

A generated 40-member candidate manifest and archive were parsed, validated, and
fully extracted by the exact v0.2.3 `ppstime_update.py`. Automated tests also
cover lexical service reconciliation, ownership/mode validation, symlink
rejection, lock preservation, installation, activation, and rollback.

## Feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| Public v0.2.5 seven-asset verification | PASS | Image, metadata, archive, signature |
| Signed v0.2.5 update check | SAFE FAILURE | Rejected before mutation |
| Appliance installed state | PRESERVED | Remains v0.2.3 |
| Exact v0.2.3 manifest parsing | PASS | Corrected 40-member inventory accepted |
| Exact v0.2.3 archive validation | PASS | All 40 members extracted |
| Lock inode and exclusive flock | AUTOMATED PASS | No replacement or truncation |
| Cold-boot lock dependency | AUTOMATED PASS | Required before dashboard start |
| Rollback compatibility | AUTOMATED PASS | New service is transaction-managed |
| Production v0.2.3-to-v0.2.6 apply | PENDING | Requires published signed assets |
| Rollback/reapply and routed denial | PENDING | Continue issue #95 evidence |
| Public-image shortened smoke | PENDING | Post-publication |

GPSD configuration, PPS, Chrony policy, RTC, boot overlays, hardware profiles,
and the supported target are unchanged from the v0.2.0 physical timing baseline.

## Decision

Publish signed v0.2.6 assets after protected checks pass, independently verify
all seven assets including the old-updater boundary, and then perform physical
check/apply acceptance. Remaining physical checks stay **PENDING** until recorded
in [issue #95](https://github.com/Bazsy/PPSPi/issues/95).
