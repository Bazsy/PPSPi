# Contributing to PPSPi

Thank you for helping improve PPSPi. Precision timing changes can look harmless
while shifting time by a full second, so contributions favour evidence,
reproducibility, and small reviewable changes.

## Before opening a change

1. Search existing issues and discussions.
2. Open an issue for hardware mappings, timing-source changes, security-impacting
   behavior, or new hardware profiles.
3. Cite manufacturer documentation, Raspberry Pi source, kernel source, or
   direct measured results for hardware claims.
4. Never infer or copy a GPIO/RTC value from a visually similar board.

## Development workflow

Create a focused branch, make the smallest coherent change, and run:

```console
make test
make lint
```

Tests must not require physical GPS hardware unless clearly placed in the
hardware acceptance process. Add or update fixture outputs for parser and status
changes. Installer changes require an alternate-root idempotency test.

## Coding standards

Shell code must use `set -Eeuo pipefail`, quote expansions, pass ShellCheck and
shfmt, and avoid unbounded sleeps. Python supports the Bookworm interpreter,
uses type hints and the standard library by default, and passes Ruff. Generated
configuration must be controlled and validated rather than unrestricted text
replacement.

## Pull requests

Include:

- the problem and chosen design;
- safety or timing implications;
- exact reproduction and validation commands;
- test results;
- hardware and board revision, if tested;
- documentation updates;
- explicit unverified assumptions or deferred work.

Do not include generated image files, credentials, device identifiers, private
network details, or unsanitised support bundles.

## Commits and releases

Use logical commits that keep tests passing. Pull-request merges never publish
releases. Maintainers control versions through `VERSION`, the changelog,
hardware acceptance, and explicit GitHub Release publication as documented in
`docs/release-process.md`.
