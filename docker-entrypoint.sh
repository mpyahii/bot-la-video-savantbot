#!/bin/sh
set -eu

mkdir -p /data/downloads
chown -R bot:bot /data/downloads
exec gosu bot "$@"