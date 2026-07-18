# Development

## Repository layout

```text
config/                 validated defaults and hardware profiles
files/ppstime/          installed Python commands and shared core
files/systemd/          RTC, health, and service-ordering units
files/udev/             PPS permissions
scripts/                installer, image builder, metadata, packaging
pi-gen/stage-pps-pi/    custom official pi-gen stage
tests/                  unit tests and hardware-free command fixtures
docs/                   operator and release documentation
.github/workflows/      lint, test, manual image, explicit release workflows
```

## Local requirements

Runtime and tests use Python's standard library. Static checks use:

- Python 3.10 or 3.11;
- Ruff 0.12.5;
- ShellCheck;
- shfmt;
- yamllint 1.37.1;
- actionlint 1.7.7;
- markdownlint-cli2 0.18.1.

GitHub Actions installs pinned versions. Local package installation varies by
distribution; keep tools outside the appliance runtime.

## Tests

Run all hardware-free tests:

```console
make test
```

The suite covers:

- strict profile parsing and invalid values;
- all RFC 1918/ULA defaults and explicit exclusion of other non-global ranges;
- Pi 4 acceptance and out-of-scope model rejection;
- duplicate-safe boot blocks and serial-console removal;
- generated GPSD and Chrony configuration;
- Chrony, GPSD, PPS, RTC, and systemd fixture parsing;
- successful Stratum-1 and degraded timing states;
- full `ppstime-test` fixture behavior;
- alternate-root installation run twice;
- XZ packaging, build metadata, and SHA-256 output.

Fixture data lives in `tests/fixtures`. Keep it representative of real command
formats and remove hostnames, IP addresses, serials, and other private data
before committing captures.

## Static checks

```console
make lint
```

Ruff formatting, shfmt, and unrelated reformatting should not be mixed with a
functional change. Shell code must preserve `set -Eeuo pipefail` behavior.

## Profile development

Profiles are data, not executable shell fragments. Add recognized keys to the
core allow-list, validation, serialization, documentation, and tests together.
Every hardware pin, chip, address, overlay, and edge needs authoritative or
measured evidence.

Validate a model string without writing:

```console
python3 scripts/configure-profile.py --validate-only --model 'Raspberry Pi 4 Model B Rev 1.5'
```

Use `--allow-unsupported-model` only for development roots and never to claim a
supported release.

## Installer development

The installer supports a root filesystem path so tests never modify the
developer machine. The alternate-root test creates modern boot files, installs
twice, and verifies content and backup counts. Any new installed file should be
covered by this path.

Generated files must be atomic, deterministic, and validated. Preserve
unrelated operating-system configuration. Do not add fixed sleeps where device
units, explicit ordering, or bounded retries work.

## Prepare pi-gen without Docker

The preparation path verifies the pinned checkout and constructs the stage:

```console
./scripts/build-image.sh --prepare-only
```

Image builds require a clean Git tree so `build-info.json` identifies the exact
source. For an explicitly non-release experiment, `ALLOW_DIRTY=1` bypasses this
guard and should never be used for published artifacts.

The checkout is stored under ignored `.pi-gen/checkout`. Remove it with
`make clean`.

## Build an image locally

Requirements:

- Linux host;
- Git and Docker;
- Docker daemon access;
- enough disk for pi-gen containers, root filesystems, and the uncompressed
  image (allow tens of gigabytes);
- network access to Debian/Raspberry Pi repositories and GitHub.

```console
./scripts/build-image.sh --version 0.1.0-dev
```

The script checks out the pinned `bookworm-arm64` pi-gen commit, prepares the
custom stage, invokes `build-docker.sh`, and writes `artifacts/`. It expects
exactly one `.img.xz` output.

CI runner disk cleanup is deliberately in the image workflows, not in the build
script, because deleting host SDKs is appropriate only on an ephemeral runner.

## Hardware tests

CI cannot emulate GNSS reception, PPS electrical timing, RTC retention, or LAN
access boundaries on a Raspberry Pi. Complete `docs/hardware-test-plan.md` on
the named board revision and attach a report before release.

Measured offsets should include duration, temperature range, antenna location,
firmware, kernel, Chrony, GPSD, and receiver details. A one-minute screenshot is
not stability evidence.
