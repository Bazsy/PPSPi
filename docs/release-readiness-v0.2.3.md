# PPSPi v0.2.3 release readiness

Status: **APPROVED CORRECTIVE PATCH FOR PUBLICATION**

v0.2.3 addresses evidence from the first production-signed v0.2.2 apply on the
supported appliance. v0.2.2 verified and staged successfully, then its immediate
post-restart deep test failed and automatic rollback restored exact v0.2.0
release identity. A subsequent v0.2.0 deep test passed all essential checks.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.3` |
| Release commit | Pending merge of this release PR |
| Installed source | v0.2.0 image at `a07d436dac2cea78e738a49ad193fa9cdb58cbb9` |
| Failed target transaction | `20260729T085406Z-2e075ae6-0.2.2` |
| Failure disposition | Automatic rollback to v0.2.0 passed |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Compatibility series | `0.2` |

## Root cause and compatibility design

- updater activation intentionally restarts GPSD and Chrony;
- v0.2.2 immediately required GPS message flow, active PPS, synchronized Chrony,
  selected PPS, UDP/123, and a local NTP response;
- the rolled-back appliance subsequently passed every essential check, isolating
  the defect to the unbounded readiness race;
- the running v0.2.0 updater cannot reload its own newly installed Python code;
- it does launch the newly installed `ppstime-test`, so v0.2.3 detects that exact
  parent and performs bounded retries there;
- normal tests and fixture tests remain single-shot;
- the old updater starts the new sample timer, whose `Wants=` relationship now
  starts the dashboard HTTP service immediately;
- future updater failures expose validated failed-check names rather than a
  generic message.

## Validation requirements

- focused updater, status, dashboard, and deep-test regressions pass;
- complete local unit/integration and static suites must pass;
- protected Python 3.10/3.11/3.13, model matrix, required gate, static checks,
  and CodeQL must pass before merge;
- publication must rebuild, mount/validate, sign, and upload exactly seven
  immutable assets;
- independent public-asset verification must pass before appliance retry.

## Post-publication acceptance

- capture preservation sentinels and run exact v0.2.0-to-v0.2.3 check/apply;
- record whether settling retries were needed and final installed identity;
- verify unprivileged status, timing health, automatic dashboard service/timer,
  private Ethernet/Wi-Fi access, routed out-of-CIDR denial, bounded history, and
  no access logging/external requests;
- verify accounts, SSH, network, cloud-init, timing configuration, and unrelated
  files are preserved;
- exercise local rollback and exact restoration, then reapply v0.2.3;
- retain shortened public-image smoke and genuine reboot-required OS maintenance
  as separately tracked issue #95 work.

## Decision

The demonstrated rollback safety, healthy restored baseline, bounded compatibility
bridge, and regression coverage support publication. Production v0.2.3 apply is
still pending rather than pre-claimed as PASS. PPSPi must not be the sole
production time source.
