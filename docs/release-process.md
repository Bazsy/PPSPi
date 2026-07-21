# Release process

PPSPi separates merge validation, test images, version decisions, and release
publication. No pull-request event, merge, push to `main`, or tag push can
publish a release.

## GitHub repository setup

Maintainers should configure:

1. an active branch ruleset targeting `main`;
2. pull requests before merging, with zero required approvals while this is a
    single-maintainer repository;
3. required status checks named **Static checks** and
    **Required test gate**, with branches required to be up to date;
4. required conversation resolution;
5. branch deletion and force pushes blocked;
6. a GitHub environment named `release` with a required reviewer when another
    trusted maintainer is available;
7. GitHub private vulnerability reporting;
8. Actions permissions that allow the release workflow's `contents: write`.

Do not require one pull-request approval until another maintainer can review:
GitHub does not allow an author to approve their own pull request. Once a
reviewer is available, require one approval, dismiss stale approvals, and
require approval of the most recent reviewable push.

The stable **Required test gate** depends on every Python and Raspberry Pi model
matrix job. Protecting that one context avoids updating the ruleset whenever a
matrix entry changes. Do not enable required signed commits until the project
has a documented signing workflow. Leave linear history disabled while merge
commits are allowed.

The workflow uses the repository-scoped `GITHUB_TOKEN`. Do not add a personal
access token secret for normal releases.

## Version preparation

PPSPi uses Semantic Versioning. Prepare a release pull request that:

1. changes `VERSION` from a development identifier to the exact release version,
   for example `0.1.0`;
2. moves relevant changelog entries into that version and adds the date;
3. updates documentation and draft release notes;
4. records the pinned pi-gen revision and operating-system release;
5. links all deferred work;
6. includes static and hardware test results.

The release tag must be the same version prefixed with `v`, for example
`v0.1.0`. The release workflow rejects any mismatch.

## Build a test image

From the GitHub **Actions** tab, run **Build test image** manually on the release
candidate commit. Enter the candidate semantic version. This workflow:

- runs the complete static test suite;
- builds Trixie arm64 with pinned pi-gen;
- creates the compressed image, SHA-256 file, and metadata;
- validates that a local `cloudinit-rpi` Imager manifest can be generated from
    the built image and metadata;
- uploads a seven-day workflow artifact;
- does not create a tag or release.

Flash this exact candidate artifact and execute the hardware plan. If code or
configuration changes, build and test a new artifact.

## Hardware release gate

Complete [the hardware test plan](hardware-test-plan.md) and create a report
from [the report template](hardware-test-report-template.md). A report must name
the Git commit and artifact SHA-256. Resolve or explicitly block release on
every failed item.

Do not publish an image release while:

- the HAT revision or RTC identity is unknown;
- PPS GPIO or edge is inferred rather than verified;
- any required acceptance item is untested or failed;
- first-boot account creation or SSH defaults are unverified;
- NTP access boundaries have neither been tested from applicable allowed/denied
    clients nor explicitly scope-waived with compensating controls in the final
    hardware report.

## Publish through GitHub

After merging the version pull request and verifying the target commit:

1. open **Releases** and choose **Draft a new release**;
2. create tag `v<contents of VERSION>` targeting the tested commit;
3. use the reviewed release notes;
4. mark pre-release status as appropriate;
5. explicitly choose **Publish release**.

Only the `release.published` event starts **Attach release image**. The workflow
checks out the tag, validates tag and `VERSION`, repeats static tests, rebuilds
from the tagged source, and attaches:

- `ppspi-<version>-raspios-trixie-arm64.img.xz`;
- its `.sha256` file;
- `build-info.json`;
- `ppspi-<version>-raspios-trixie-arm64.rpi-imager-manifest`.

Publishing makes the release visible before the long image build finishes. Add
a release note that assets are building, then verify all four attachments and
their checksums when the workflow completes. A failed workflow can be re-run;
asset upload uses `--clobber` for that tag.

## Post-release checks

1. Download the assets from the public release page.
2. Verify the SHA-256 file from a clean directory.
3. Validate every `build-info.json` field against the tag and workflow.
4. Open the public `.rpi-imager-manifest` in current Imager 2.x and confirm the
    versioned PPSPi entry and customisation pages appear.
5. Flash the public download and perform a shortened smoke boot.
6. Confirm no credentials or local identifiers are present.
7. Open the next development version pull request, such as `0.2.0-dev`.

The test-image hardware report and public release rebuild must identify their
respective commits and hashes. The public asset is rebuilt from the reviewed tag,
so it is not expected to have the same compressed hash as an earlier temporary
workflow artifact. Runtime/configuration changes after hardware acceptance
require a new full candidate test; version, changelog, and documentation-only
release preparation still requires the public-asset checksum and shortened smoke
boot above.

## Release trigger summary

| Event | Lint/test | Image artifact | GitHub Release |
| --- | --- | --- | --- |
| Pull request | Yes | No | No |
| Merge/push to `main` | Yes | No | No |
| Tag push | No release trigger | No | No |
| Manual **Build test image** | Tests first | Temporary artifact | No |
| Explicit GitHub Release publication | Tests first | Release build | Existing release receives assets |
