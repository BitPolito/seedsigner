# Maintaining the downstream theme

Keep the official source layout. Do not reorganize or delete inherited files
just because BitPolito does not currently use them: a small, explicit upstream
diff is easier to review and update than a rewritten application.

## Where things belong

| Location | Purpose |
| --- | --- |
| `src/seedsigner/` | Official app layout plus the allowed graphical changes |
| `design/bitpolito-theme.json` | Palette, asset hashes and baseline metadata |
| `design/source-assets/` | Editable branding sources, not device resources |
| `design/review/` | Current English review sheets and screenshot manifest |
| `tools/simulator/` | Desktop-only hardware adapters and launcher |
| `tests/` | Upstream tests plus downstream regression checks |
| `scripts/` | Setup, quality gates and reproducible build helpers |
| `docs/bitpolito-*.md` | Downstream build and maintenance instructions |
| `artifacts/`, `.build/` | Ignored outputs and local build caches |

Keep the official translation and screenshot submodules pinned. They are
read-only inputs, not output folders. Preserve inherited tools, documents,
fonts and images unless a reviewed upstream update removes them.

## Updating SeedSigner

1. Start a focused branch from validated BitPolito `dev`. Select an official
   stable application and compatible OS release; do not track moving upstream
   branches. Fetch upstream read-only and review its release notes and diff.
2. Test the untouched official release in an isolated checkout first. Merge or
   rebase the application update on the feature branch, never on release `main`.
   Resolve conflicts by preserving the new official behavior and reapplying
   only the approved graphical changes. Do not use legacy BitPolito `main` as
   the new application baseline.
3. Update the pins in `scripts/release.env`, then align the theme manifest,
   controller version, package version and manual build workflow metadata.
   The workflow intentionally declares its pins explicitly; regression tests
   catch mismatches. The package version uses `+bitpolito.N`, while the image
   revision uses `-bitpolito.N`.
4. Review `scripts/check_upstream_scope.sh` against the new baseline. Its
   controller delta is intentionally exact; do not weaken protected-path
   checks just to make an upgrade pass. Changes needed in protected runtime
   code require stopping and reconsidering the upgrade.
5. Regenerate the Bitcoin font with `scripts/build-brand-icons.py` from the
   new official font, then update its manifest hash. This preserves all other
   upstream glyphs. Run the font regression tests.
6. Run the release quality gate on Python 3.10 and 3.12 (or explicitly review
   a new upstream Python requirement). Generate fresh English sheets using
   `scripts/build-review-sheets.py --input <generated-screenshots>/en`.
   Its default destination follows the theme release metadata. Keep only the
   current review set in the working tree; earlier committed sets remain in
   Git history. Obtain visual approval before final commits.
7. Inspect the complete diff against the selected official baseline. Commit
   and publish only in BitPolito, then build the pinned Pi Zero candidate.
   Complete [hardware acceptance](bitpolito-build.md#hardware-acceptance-and-publication)
   before releasing the same tested bytes and checksum.

## Local outputs

Raw screenshots, coverage, experiments and CI outputs are disposable and must
stay ignored. Keep release images, manifests and checksums until they have been
safely published or backed up. Keep `.build/pi0` when rebuilding locally to
avoid downloading and compiling everything again. Do not use `git clean -fdx`
as routine cleanup: it would also remove environments and unpublished images.
