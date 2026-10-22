#!/bin/bash
set -euo pipefail
umask 077
# TODO: Write the exact service-scoped recipe and remove this guard only after review.
printf '%s\n' 'Migration recipe is a draft; no operation performed.' >&2
exit 64
