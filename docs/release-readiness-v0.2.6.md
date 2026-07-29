# PPSPi v0.2.6 release readiness

Status: **APPROVED COMPATIBILITY PATCH FOR PUBLICATION**

v0.2.6 addresses direct appliance evidence from an attempted signed v0.2.5
update check. The running v0.2.3 updater rejected a new tmpfiles payload path
before archive application, demonstrating that the closed application boundary
worked as designed but that v0.2.5 was not consumable from the deployed release.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.6` |
| Release commit | Pending merge of this release PR |
| Compatibility correction merge | `ce0c927df6e90a8fa59cfcbaad22fd55a4653d42` |
| Installed source | v0.2.3 at `e8eaf385a47890414d325d0e349491e4d60bee0f` |
| Rejected target | v0.2.5 at `88ed548adf86a3d2e44511f7fc4e6c9f59225396` |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Compatibility series | `0.2` |

## Root cause and compatibility design

- the v0.2.5 package added `usr/lib/tmpfiles.d/ppstime.conf` to the new updater's
  allowlist and signed inventory;
- the updater performing an upgrade remains the v0.2.3 process already loaded in
  memory, so candidate allowlist changes cannot affect manifest validation;
- v0.2.3 rejects the unfamiliar path before archive download/extraction and
  before creating an update transaction;
- v0.2.6 replaces the tmpfiles member with a PPSPi-named systemd service, a path
  already accepted by the immutable v0.2.3 boundary;
- the root oneshot invokes newly installed `ppstime-update prepare-lock` and is a
  required ordered dependency of the dashboard;
- opening with `O_NOFOLLOW` and without truncation preserves an updater-held
  inode and exclusive kernel lock while validating regular-file type, root
  ownership/group, and mode `0600`;
- lexical reconciliation handles the lock service before the dashboard; starting
  the dashboard then pulls in the static oneshot through `Requires=`;
- rollback restores the old dashboard unit and removes the newly introduced
  service through the existing signed transaction inventory.

## Appliance evidence captured

- `sudo ppstime-update check --version 0.2.5` returned:
  `payload path is outside the PPSPi application boundary:
  usr/lib/tmpfiles.d/ppstime.conf`;
- the command failed before application mutation or transaction creation;
- the appliance therefore remains on the previously healthy v0.2.3 installation;
- no timing-service or dashboard recovery action is required for this check
  failure;
- all seven public v0.2.5 assets had already passed independent cryptographic and
  metadata verification.

## Validation gates

- the exact immutable v0.2.3 parser accepted the corrected canonical v0.2.6
  manifest;
- the exact immutable v0.2.3 archive validator extracted all 40 candidate files;
- 198 complete unit/integration tests pass, including exact legacy-boundary,
  inode-preserving flock, symlink rejection, service ordering, installation,
  activation, and rollback coverage;
- Ruff 0.12.5, ShellCheck, shfmt, yamllint 1.37.1, actionlint,
  markdownlint-cli2 0.18.1, and whitespace checks pass;
- compatibility PR #104 passed all 15 protected checks before merge;
- this release PR must pass all protected checks before merge;
- publication must rebuild, inspect, sign, and upload exactly seven immutable
  assets;
- independent public-asset verification must pass before appliance use.

## Post-publication acceptance

- run signed v0.2.6 `check` from the physically installed v0.2.3 appliance;
- apply v0.2.6 and confirm committed identity plus all essential timing checks;
- confirm `0.0.0.0:8080`, loopback HTTP 200, and HTTP 200 on both current private
  IPv4 addresses without manual intervention;
- confirm one-decimal root, boot, and CPU-temperature card rendering;
- exercise rollback/reapply and routed out-of-CIDR denial separately;
- retain shortened public-image smoke as separately tracked issue #95 work.

## Decision

The pre-mutation failure, exact old-code reproduction, legacy-compatible package
boundary, inode-preserving lock design, full automated suite, and protected
checks support publication. Production v0.2.6 application-update acceptance
remains pending rather than pre-claimed. PPSPi must not be the sole production
time source.
