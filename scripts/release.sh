#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() {
  echo "release: $*" >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "missing required command: $1"
  fi
}

require_cmd gh
require_cmd git
require_cmd python
require_cmd shasum

VERSION="${VERSION:-$(python - <<'PY'
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)}"
TAG="${TAG:-v${VERSION}}"
TITLE="${TITLE:-Penny ${VERSION}}"
DRY_RUN="${DRY_RUN:-0}"
NOTES_FILE="${NOTES_FILE:-}"

upstream_ref="$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || true)"
if [[ -z "${upstream_ref}" ]]; then
  fail "current branch has no upstream; push it before creating a release"
fi

current_sha="$(git rev-parse HEAD)"
upstream_sha="$(git rev-parse "${upstream_ref}")"
if [[ "${current_sha}" != "${upstream_sha}" ]]; then
  fail "HEAD (${current_sha}) does not match ${upstream_ref} (${upstream_sha}); push first"
fi

shopt -s nullglob
dmg_artifacts=("$ROOT_DIR"/dist/Penny-"$VERSION"*.dmg)
shopt -u nullglob

if [[ ${#dmg_artifacts[@]} -eq 0 ]]; then
  fail "no DMG artifacts found for version ${VERSION}; run make build first"
fi

release_assets=()
for artifact in "${dmg_artifacts[@]}"; do
  checksum_file="${artifact}.sha256"
  shasum -a 256 "$artifact" > "$checksum_file"
  release_assets+=("$artifact" "$checksum_file")
done

if gh release view "$TAG" >/dev/null 2>&1; then
  release_exists=1
else
  release_exists=0
fi

echo "Version: ${VERSION}"
echo "Tag: ${TAG}"
echo "Title: ${TITLE}"
echo "Target: ${current_sha}"
echo "Upstream: ${upstream_ref}"
echo "Assets:"
for asset in "${release_assets[@]}"; do
  echo "  - ${asset#$ROOT_DIR/}"
done

if [[ "${DRY_RUN}" == "1" ]]; then
  if [[ "${release_exists}" == "1" ]]; then
    echo "Dry run: would upload assets to existing GitHub release ${TAG}"
  else
    echo "Dry run: would create GitHub release ${TAG}"
  fi
  exit 0
fi

if [[ "${release_exists}" == "1" ]]; then
  gh release upload "$TAG" "${release_assets[@]}" --clobber
  echo "Updated GitHub release ${TAG}"
  exit 0
fi

release_args=(gh release create "$TAG" "${release_assets[@]}" --target "$current_sha" --title "$TITLE" --latest)
if [[ -n "${NOTES_FILE}" ]]; then
  release_args+=(--notes-file "$NOTES_FILE")
else
  release_args+=(--generate-notes)
fi

"${release_args[@]}"
echo "Created GitHub release ${TAG}"
