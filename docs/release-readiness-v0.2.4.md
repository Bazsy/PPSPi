# PPSPi v0.2.4 release readiness

Status: **APPROVED CORRECTIVE PATCH FOR PUBLICATION**

v0.2.4 addresses direct appliance evidence collected after the signed v0.2.3
application update committed successfully. Timing validation and update identity
passed, but the dashboard process retained its pre-regeneration socket address.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.4` |
| Release commit | Pending merge of this release PR |
| Installed source | v0.2.3 application at `e8eaf385a47890414d325d0e349491e4d60bee0f` |
| Successful source transaction | `20260729T094909Z-ef4be723-0.2.3` |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Compatibility series | `0.2` |

## Root cause and compatibility design

- configuration regeneration uses atomic replacement, so an existing Python
  HTTP process continues using values loaded at its original start;
- prior updater activation restarted GPSD and Chrony but not an already-active
  dashboard;
- `systemctl enable --now` does not restart an active service;
- preflighting the new wildcard bind before stopping an old literal listener can
  fail with `EADDRINUSE`, even though a controlled restart is valid;
- current updater activation now includes the dashboard;
- because an updater cannot reload its own replaced Python module mid-process,
  the newly installed `ppstime-test` also restarts and verifies the dashboard
  when its exact parent is `ppstime-update`;
- the dashboard watches its atomically replaced executable and configuration
  identities, so stale in-memory code exits and systemd starts the installed or
  restored version after a forward update or rollback;
- the systemd unit owns bind preflight in `ExecStartPre`, after the old process
  has stopped and before the server starts;
- `ppstime-config apply` re-reads post-generation configuration and uses explicit
  enable, restart, and timer-start operations.

## Physical acceptance captured

Before correction, the appliance had both `10.0.10.110` and `10.0.10.173` but
listened only on the stale `10.0.10.173:8080`. The service and timer were enabled
and active and the sampler completed repeatedly. HTTP returned 200 on `.173`
and connection refusal on `.110` and loopback.

After validated wildcard configuration and a dashboard-only restart:

- listener: `0.0.0.0:8080`;
- loopback: HTTP 200;
- `10.0.10.110`: HTTP 200;
- `10.0.10.173`: HTTP 200.

No GPSD, Chrony, RTC, PPS, or NTP service was changed by this live correction.

## Validation gates

- 77 focused updater/config/dashboard/status tests pass, including serving-loop
  exit on atomic replacement and post-activation persistence-failure rollback;
- 188 complete local unit/integration tests pass;
- Ruff, ShellCheck, shfmt, yamllint, actionlint, and markdownlint-cli2 pass;
- protected Python 3.10/3.11/3.13, model matrix, required gate, static checks,
  and CodeQL must pass before merge;
- publication must rebuild, mount/validate, sign, and upload exactly seven
  immutable assets;
- independent public-asset verification must pass before appliance apply.

## Post-publication acceptance

- apply signed v0.2.4 from the physically running v0.2.3 appliance;
- confirm installed commit/version and all essential timing checks;
- confirm `0.0.0.0:8080`, loopback HTTP 200, and HTTP 200 on both current private
  IPv4 addresses without a manual service restart;
- confirm one-decimal root, boot, and CPU-temperature card rendering;
- exercise local rollback/reapply and routed out-of-CIDR denial;
- retain shortened public-image smoke and genuine reboot-required OS maintenance
  as separately tracked issue #95 work.

## Decision

The committed v0.2.3 transaction, isolated dashboard root cause, successful live
wildcard correction, and complete automated regressions support publication.
Production v0.2.4 application-update acceptance remains pending rather than
pre-claimed as pass. PPSPi must not be the sole production time source.
