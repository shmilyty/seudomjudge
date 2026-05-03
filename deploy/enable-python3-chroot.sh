#!/usr/bin/env bash
set -euo pipefail

# Install CPython in DOMjudge judgehost chroots, repair Java runtime lookup, and
# ensure per-judging sandboxes contain a standard /tmp directory for compile
# scripts.
#
# Run this on the Docker host after judgehost containers have been created.

DOMSERVER_CONTAINER="${DOMSERVER_CONTAINER:-dj-domserver}"
JUDGEHOSTS="${JUDGEHOSTS:-dj-judgehost-0 dj-judgehost-1 dj-judgehost-2 dj-judgehost-3}"

patch_chroot_startstop() {
    local container="$1"

    docker exec "$container" bash -s <<'PATCH_CHROOT_STARTSTOP'
set -euo pipefail

script=/opt/domjudge/judgehost/lib/judge/chroot-startstop.sh

if ! grep -q 'SEU: provide /tmp for compile scripts' "$script"; then
    sed -i '/# copy dev\/random/i\
        # SEU: provide /tmp for compile scripts such as Java.\
        mkdir -p tmp\
        chmod 1777 tmp\
' "$script"
fi

bash -n "$script"
PATCH_CHROOT_STARTSTOP
}

for container in $JUDGEHOSTS; do
    echo "==> Enabling judgehost runtimes in $container"
    docker exec "$container" test -d /chroot/domjudge
    docker exec "$container" chroot /chroot/domjudge /bin/sh -c '
        set -eu
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y python3

        mkdir -p /tmp
        chmod 1777 /tmp

        if [ -x /usr/bin/java ] || [ -x /usr/bin/javac ]; then
            java_bin="$(readlink -f /usr/bin/java || true)"
            java_home="${java_bin%/bin/java}"
            if [ -n "$java_home" ] && [ -d "$java_home/lib" ]; then
                {
                    printf "%s\n" "$java_home/lib"
                    if [ -d "$java_home/lib/jli" ]; then
                        printf "%s\n" "$java_home/lib/jli"
                    fi
                } > /etc/ld.so.conf.d/java.conf
                ldconfig
            fi
        fi

        python3 --version
        if command -v java >/dev/null 2>&1; then
            java --version | head -n 1
        fi
        if command -v javac >/dev/null 2>&1; then
            javac --version
        fi
    '
    patch_chroot_startstop "$container"
done

echo "==> Updating DOMjudge Python 3 language version commands"
docker exec "$DOMSERVER_CONTAINER" bash -lc '
    set -eu
    cd /opt/domjudge/domserver/webapp
    bin/console dbal:run-sql "UPDATE language SET compiler_version_command=\"python3 --version\", runner_version_command=\"python3 --version\", compiler_version=NULL, runner_version=NULL WHERE langid=\"py3\""
    bin/console cache:clear --env=prod --no-debug
'

echo "==> Judgehost runtime support enabled"
