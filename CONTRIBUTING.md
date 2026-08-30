# Contributing to BitPolito SeedSigner

BitPolito is maintained as a downstream visual customization of SeedSigner.
All development and pull requests belong to
[BitPolito/seedsigner](https://github.com/BitPolito/seedsigner). Do not modify
the official SeedSigner repositories.

## Workflow

- Create or update work on the `dev` branch.
- Keep `main` reserved for validated code and releases.
- Open pull requests from `dev` (or a focused feature branch) into `dev`.
- Keep changes focused and explain the user-visible effect in the pull request.

## Local setup and tests

~~~bash
./scripts/setup-dev.sh
scripts/run-quality-gate.sh --quick
~~~

Before a pull request or release, run the complete gate:

~~~bash
scripts/run-quality-gate.sh --release
~~~

When changing the UI, compile translations and regenerate the screenshot review
set. Obtain visual approval before creating the final release commits.

## Scope and safety

Keep runtime differences graphical: theme, rendering, branding, assets, version
metadata and the approved 30-second screensaver. Do not modify wallet logic, QR
or SeedQR handling, PSBT processing, camera or GPIO behavior, display drivers,
security code, Buildroot or SeedSigner OS.

Never enter real seeds, private keys or funds in the simulator. Use deterministic
fixtures and test data only.

## Pull requests

Describe:

- what changed and why;
- affected screens or assets;
- tests and quality gates run;
- visual review files or screenshots for UI changes;
- any known hardware follow-up.
