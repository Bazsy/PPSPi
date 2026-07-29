# PPSPi hardware test report: v0.2.3

Status: **ROLLBACK SAFETY PASSED; CORRECTED APPLY PENDING**

This patch is driven by real production-update evidence on the supported
Raspberry Pi 4 and Uputronics Rev 6.4 appliance.

## Observed v0.2.2 attempt

- source identity before apply: v0.2.0 image commit
  `a07d436dac2cea78e738a49ad193fa9cdb58cbb9`;
- target: production-signed v0.2.2;
- transaction: `20260729T085406Z-2e075ae6-0.2.2`;
- apply reached post-update deep validation;
- validation failed before GPSD/Chrony had settled;
- automatic transaction rollback completed;
- origin/state returned to v0.2.0 with `last_action=failed_rolled_back`;
- the restored appliance then passed every essential `ppstime-test --json`
  check: boot/configuration, serial/baud/GPSD/message flow, PPS device/pulses,
  RTC, Chrony synchronization/PPS selection, syntax, UDP/123, local NTP, and
  unit health.

This is positive rollback evidence and negative v0.2.2 apply evidence. It is not
a successful update claim.

## v0.2.3 correction

v0.2.3 places the settle bridge in the newly installed test executable because
that is what the already-running v0.2.0 updater invokes. It retries only under
that exact parent, for at most 90 seconds. The sample timer also pulls in the
HTTP dashboard service so old-updater reconciliation starts both immediately.

## Feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| v0.2.2 signature/staging | PASS | Apply reached activation |
| v0.2.2 failed-apply rollback | PASS | Exact v0.2.0 identity restored |
| Restored timing hardware | PASS | All essential deep checks pass |
| v0.2.3 bounded settle bridge | AUTOMATED PASS | Exact parent, retry, deadline coverage |
| v0.2.3 immediate dashboard start | AUTOMATED PASS | Old/new updater paths covered |
| Unprivileged update status | AUTOMATED PASS | No lock for atomic read-only state |
| Production v0.2.0-to-v0.2.3 apply | PENDING | Requires published signed assets |
| Preservation and rollback/reapply | PENDING | Continue issue #95 evidence |
| Direct-LAN allow/deny | PENDING | Requires routed client measurement |
| Public-image shortened smoke | PENDING | Post-publication |

GPSD configuration, PPS, Chrony policy, RTC, boot overlays, hardware profiles,
and the supported target are unchanged from the v0.2.0 physical baseline.

## Decision

Publish the signed v0.2.3 assets needed to retest the corrected path. Do not retry
v0.2.2 on the appliance. Remaining physical checks stay **PENDING** until
recorded in [issue #95](https://github.com/Bazsy/PPSPi/issues/95).
