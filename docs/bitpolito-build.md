# Building the BitPolito Pi Zero image

BitPolito uses the unmodified SeedSigner OS 0.8.7 build system at commit
`d13859392660fe512a753bc14ecd0edc86c35510`. The only supported image target
for this release is `pi0`.

The build helpers in `scripts/` are intentionally version controlled. They are
part of the reviewable and reproducible release process. Local virtual
environments, Docker caches, generated screenshots, images, manifests, and
checksums belong under ignored `.build/` and `artifacts/`. Secrets and signing
keys must never be stored in this repository.

## Recommended path: GitHub Actions

The manual workflow is the canonical candidate builder because it starts from a
clean, published application commit and retains the resulting artefacts.

Before the first run, a repository administrator must configure the GitHub
Environment named `bitpolito-image-build` and add the required BitPolito
reviewers. This protection is configured on GitHub and cannot be committed in
the repository.

To create a candidate:

1. Approve the English visual review sheets.
2. Commit the reviewed source and push it to `BitPolito/seedsigner`.
3. Wait for the Python 3.10 and 3.12 CI matrix to pass.
4. Open the manual **Build** workflow on the exact branch or tag.
5. Paste the selected 40-character application commit into
   `expected_app_commit`.
6. Select `BUILD PI0 CANDIDATE`.
7. Approve the protected `bitpolito-image-build` environment.
8. Download the unsigned artifact; do not publish it before hardware acceptance.

The workflow checks out the pinned official OS and calls its existing
`build.sh` with `--pi0`, the public BitPolito repository, and the exact
application commit. This deliberately uses the official application-download
path: SeedSigner OS compiles translation catalogs, subsets fonts, removes
development files, and then builds the root filesystem. No SeedSigner OS file is
patched by BitPolito.

## Local setup and validation

Create or refresh the development environment:

```bash
./scripts/setup-dev.sh
```

Use the quick gate while iterating:

```bash
./scripts/run-quality-gate.sh --quick
```

Before a candidate build, run the complete local gate:

```bash
./scripts/run-quality-gate.sh --release
```

The release gate covers all three official display configurations, the real
30-second screensaver timeout, camera-to-zbar SettingsQR ingestion, and
screenshots for every official locale. Generated files go to `artifacts/`;
the official screenshot submodule remains clean.

## Optional local image build

A local build requires Git, SHA-256 tools, Docker with a working daemon, network
access, and approximately 20–30 GB of free disk space. The official guide notes
that a build may take from roughly 25 minutes to more than two hours.

The local wrapper refuses to build unless the working tree is clean, submodules
match their recorded commits, and the current commit is visible as the tip of a
public BitPolito ref:

```bash
./scripts/build-pi0.sh --check
./scripts/build-pi0.sh
```

It runs the full release gate first, checks out the pinned SeedSigner OS under
`.build/pi0`, and uses the same official `--app-repo` and
`--app-commit-id` path as the cloud workflow. It never writes to either
official GitHub repository.

Successful output is placed under
`artifacts/release/0.8.7-bitpolito.1/`:

- `seedsigner_os.0.8.7-bitpolito.1.pi0.img`;
- `seedsigner_os.0.8.7-bitpolito.1.pi0.manifest.txt`;
- `seedsigner_os.0.8.7-bitpolito.1.pi0.sha256`.

Existing release artefacts are never overwritten.

## Verifying a candidate

Verify the image against the BitPolito manifest:

```bash
./scripts/verify-image.sh \
  artifacts/release/0.8.7-bitpolito.1/seedsigner_os.0.8.7-bitpolito.1.pi0.img \
  artifacts/release/0.8.7-bitpolito.1/seedsigner_os.0.8.7-bitpolito.1.pi0.manifest.txt
```

The verifier checks the image filename, pinned OS commit, commit-id formats, and
SHA-256. The manifest also records the exact application and Buildroot commits.

## Hardware acceptance and publication

Flash the candidate bytes to the Pi Zero and complete the checklist in
the hardware acceptance checklist below. Use test funds only. If the
hardware test passes, publish the same image bytes and SHA-256 without rebuilding
them. Any source change requires a new revision, build, hash, and hardware test.

The upstream build implementation and requirements remain authoritative:

- [SeedSigner OS build documentation](https://github.com/SeedSigner/seedsigner-os/blob/0.8.7/docs/building.md)
- [SeedSigner OS 0.8.7 build script](https://github.com/SeedSigner/seedsigner-os/blob/0.8.7/opt/build.sh)
