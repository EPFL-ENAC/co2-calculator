#!/bin/sh
# Prints the "Install" footer of a GitHub release: the release page has only
# the source archives, so this names the images and the chart of the tag.
# Usage: sh scripts/release-install-notes.sh 1.5.4
set -eu
V=$1
IMG=ghcr.io/epfl-enac/epfl/co2-calculator
cat <<NOTES

### Install

GitLab builds the images and the Helm chart after the tag. They are public on GHCR:

| Part     | Reference                            |
| -------- | ------------------------------------ |
| Backend  | \`$IMG/backend:v$V\`  |
| Frontend | \`$IMG/frontend:v$V\` |
| Docs     | \`$IMG/docs:v$V\`     |
| Chart    | \`oci://ghcr.io/epfl-enac/co2-calculator/helm/co2-calculator\` version \`$V\` |

\`\`\`sh
helm pull oci://ghcr.io/epfl-enac/co2-calculator/helm/co2-calculator --version $V
\`\`\`

The chart needs an institution folder and a backend secret. Read the [install guide](https://epfl-enac.github.io/co2-calculator/infra/install.html) before you deploy.
NOTES
