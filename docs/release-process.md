# Release process

PPSPi separates merge validation, test images, version decisions, and release
publication. No pull-request event, merge, push to `main`, or tag push can
publish a release.

## GitHub repository setup

Maintainers should configure:

1. branch protection on `main` requiring **Lint** and **Test**;
2. pull requests and at least one approval;
3. a GitHub environment named `release`;
4. optional required reviewers on that environment;
5. GitHub private vulnerability reporting;
6. Actions permissions that allow the release workflow's `contents: write`.

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
- builds Bookworm arm64 with pinned pi-gen;
- creates the compressed image, SHA-256 file, and metadata;
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
- NTP access boundaries have not been tested from allowed and denied clients.

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

- `ppspi-<version>-raspios-bookworm-arm64.img.xz`;
- its `.sha256` file;
- `build-info.json`.

Publishing makes the release visible before the long image build finishes. Add
a release note that assets are building, then verify all three attachments and
their checksums when the workflow completes. A failed workflow can be re-run;
asset upload uses `--clobber` for that tag.

## Post-release checks

1. Download the assets from the public release page.
2. Verify the SHA-256 file from a clean directory.
3. Validate every `build-info.json` field against the tag and workflow.
4. Flash the public download and perform a shortened smoke boot.
5. Confirm no credentials or local identifiers are present.
6. Open the next development version pull request, such as `0.2.0-dev`.

## Release trigger summary

| Event | Lint/test | Image artifact | GitHub Release |
| --- | --- | --- | --- |
| Pull request | Yes | No | No |
| Merge/push to `main` | Yes | No | No |
| Tag push | No release trigger | No | No |
| Manual **Build test image** | Tests first | Temporary artifact | No |
| Explicit GitHub Release publication | Tests first | Release build | Existing release receives assets |
