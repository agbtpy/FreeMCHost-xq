#!/bin/sh
set -e
cd "$(dirname "$0")"

export GOMEMLIMIT=24MiB
export GOGC=20
export GOMAXPROCS=1

exec ./sb-box run -c config.json
