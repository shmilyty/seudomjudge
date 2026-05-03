#!/usr/bin/env bash
set -euo pipefail

# Install CPython in DOMjudge judgehost chroots and align the public Python 3
# language version commands with the interpreter used by the compile script.
#
# Run this on the Docker host after judgehost containers have been created.

DOMSERVER_CONTAINER="${DOMSERVER_CONTAINER:-dj-domserver}"
JUDGEHOSTS="${JUDGEHOSTS:-dj-judgehost-0 dj-judgehost-1 dj-judgehost-2 dj-judgehost-3}"

for container in $JUDGEHOSTS; do
    echo "==> Enabling python3 in $container"
    docker exec "$container" test -d /chroot/domjudge
    docker exec "$container" chroot /chroot/domjudge /bin/sh -c '
        set -eu
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y python3
        python3 --version
    '
done

echo "==> Updating DOMjudge Python 3 language version commands"
docker exec "$DOMSERVER_CONTAINER" bash -lc '
    set -eu
    cd /opt/domjudge/domserver/webapp
    bin/console dbal:run-sql "UPDATE language SET compiler_version_command=\"python3 --version\", runner_version_command=\"python3 --version\", compiler_version=NULL, runner_version=NULL WHERE langid=\"py3\""
    bin/console cache:clear --env=prod --no-debug
'

echo "==> Python 3 chroot support enabled"
