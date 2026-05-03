#!/bin/bash
chown postgres:postgres /logs
chmod 0755 /logs
exec docker-entrypoint.sh "$@"