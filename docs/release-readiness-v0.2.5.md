# PPSPi v0.2.5 release readiness

Status: **APPROVED CORRECTIVE PATCH FOR PUBLICATION**

v0.2.5 addresses direct appliance evidence from the signed v0.2.4 application
update. The transaction reached health validation but rolled back because the
dashboard could not immediately rebind after the previous process had served an
HTTP connection.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.5` |
| Release commit | Pending merge of this release PR |
| Corrective merge | `ebee788f85614d03d67367ee10733d527bdc7517` |
| Installed source | v0.2.3 application at `e8eaf385a47890414d325d0e349491e4d60bee0f` |
| Failed and rolled-back target | v0.2.4 at `d5267cc009c6501fbf6bf65e0f452ebff4cb56f2` |
| Rolled-back transaction | `20260729T133031Z-582d1b16-0.2.4` |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Compatibility series | `0.2` |

## Root cause and compatibility design

- the v0.2.3 dashboard did not set `SO_REUSEADDR` and had served an HTTP client;
- stopping its listener left TCP state that made immediate bind fail with
  `EADDRINUSE` despite the address no longer appearing as a listening socket;
- adding reuse only to the new server cannot bridge old-nonreuse to new-reuse;
- allowing candidate traffic before transaction commit can create the reverse
  incompatibility during rollback to an old non-reuse server;
- v0.2.5 sets reuse in both preflight and the actual future server and allows a
  bounded first-generation bind-settling interval;
- the updater's existing root-owned kernel `flock` is securely passed to the
  `DynamicUser` server with systemd `OpenFile=`;
- the candidate may bind but accepts no HTTP while the updater holds its
  exclusive lock;
- atomic executable/configuration replacement makes the candidate exit during
  rollback before it can serve, allowing the restored old generation to bind;
- strict direct-parent detection and proof of the updater-owned exclusive lock
  prevent unrelated callers from preparing the handoff;
- lock permissions remain `0600`; the design needs no detached process, PID
  reuse assumptions, or sandbox-weakening `/proc` access.

## Physical evidence captured

- all seven public v0.2.4 assets independently passed cryptographic and metadata
  verification before appliance use;
- the v0.2.4 signed apply reached post-update validation and failed safely;
- journal evidence repeatedly recorded dashboard `EADDRINUSE`;
- Chrony selected network after six seconds and PPS after nine seconds;
- automatic rollback restored the v0.2.3 application and configuration;
- all 16 essential deep checks passed after rollback;
- local real-request reproduction confirmed the TCP-state root cause.

## Validation gates

- 194 complete local unit/integration tests pass, including real socket restart,
  lock wait/release, symlink rejection, exact descriptor parsing, installer
  permissions, signed inventory, activation, rollback, and persistence failure;
- Ruff, ShellCheck, shfmt, yamllint, actionlint, markdownlint-cli2, and whitespace
  checks pass;
- corrective PR #102 passed all 15 protected checks before merge;
- this release PR must pass the protected Python, model-policy, static, required,
  and CodeQL checks before merge;
- publication must rebuild, inspect, sign, and upload exactly seven immutable
  assets;
- independent public-asset verification must pass before appliance apply.

## Post-publication acceptance

- apply signed v0.2.5 from the physically running v0.2.3 appliance;
- confirm installed commit/version and all essential timing checks;
- confirm `0.0.0.0:8080`, loopback HTTP 200, and HTTP 200 on both current private
  IPv4 addresses without a manual configuration edit or service restart;
- confirm one-decimal root, boot, and CPU-temperature card rendering;
- exercise local rollback/reapply and routed out-of-CIDR denial separately;
- retain shortened public-image smoke and genuine reboot-required OS maintenance
  as separately tracked issue #95 work.

## Decision

The safely rolled-back physical failure, exact local reproduction, bounded and
rollback-compatible correction, complete automated suite, and protected checks
support publication. Production v0.2.5 application-update acceptance remains
pending rather than pre-claimed as pass. PPSPi must not be the sole production
time source.
