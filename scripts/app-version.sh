#!/bin/sh
# APP_VERSION build arg (#2437), the version the images report at runtime,
# from the same root package.json the release tag comes from. Called by both
# deploy pipelines (.github/workflows/deploy.yml, .gitlab-ci.yml) so the
# rule lives once. Only a tag build gets the bare version; dev adds the
# commit's UTC timestamp so every dev image between two bumps reports a
# different string; any other branch is marked so a ci-test image can never
# look like a release. The commit date, not the clock: the images are built
# in parallel and must agree.
set -eu
VERSION=$(jq -r '.version // ""' package.json)
[ -n "$VERSION" ] || { echo "root package.json has no version" >&2; exit 1; }
STAMP=$(TZ=UTC git show -s --format=%cd --date=format-local:%Y-%m-%d-%H%M HEAD)
ref="${CI_COMMIT_REF_NAME:-${GITHUB_REF_NAME:?no CI ref}}"
kind=branch
[ -z "${CI_COMMIT_TAG:-}" ] && [ "${GITHUB_REF_TYPE:-}" != tag ] || kind=tag
case "$kind:$ref" in
  tag:*)        ;;
  branch:dev)   VERSION="$VERSION-dev-$STAMP" ;;
  branch:stage) VERSION="$VERSION-rc" ;;
  *)            VERSION="$VERSION-$(echo "$ref" | tr '/' '-')" ;;
esac
echo "APP_VERSION=$VERSION"
