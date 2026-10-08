#!/bin/sh
# How far does one password reach? (auth_admin_keep, exercise 8.2)
#
# Runs ONE harmless helper verb through pkexec and shows polkit's temporary
# authorizations before and after. Run it from different places within five
# minutes and write down where you are asked for the password:
#
#   1. terminal A:                          sh keep-probe.sh
#   2. terminal A again:                    sh keep-probe.sh
#   3. a new terminal B:                    sh keep-probe.sh
#   4. B, detached from the terminal:       setsid -f sh keep-probe.sh > /tmp/probe.log 2>&1
#   5. B, as a systemd user service:        systemd-run --user --wait --pipe sh "$PWD/keep-probe.sh"
#   6. B, a DIFFERENT action:               VERB=firewall-phones ARG=off sh keep-probe.sh
#   7. a text console (Ctrl+Alt+F2, log in as the same user)
#   8. after 5 minutes:                     sh keep-probe.sh
#
# The verb: "firefox-memory off" deletes /etc/firefox-esr/flickos-memory.js,
# which only exists if you turned on Settings > Memory > Firefox. Do this in a
# test VM, or check that file doesn't exist first. "firewall-phones off" does
# nothing while Settings > Phone hasn't let phones through the firewall.
#
# Forget everything you were granted:   pkcheck --revoke-temp

HELPER=/usr/libexec/flickos/control-helper
VERB="${VERB:-firefox-memory}"
ARG="${ARG:-off}"

echo "== who am I: pid $$, session ${XDG_SESSION_ID:-none}, tty $(tty 2>/dev/null || echo none)"
echo "== temporary authorizations BEFORE:"
pkcheck --list-temp 2>&1 | sed 's/^/   /'
echo "== pkexec $HELPER $VERB $ARG"
start=$(date +%s)
pkexec "$HELPER" "$VERB" "$ARG"
status=$?
echo "== exit code $status after $(( $(date +%s) - start )) s (more than ~2 s usually means you typed a password)"
echo "== temporary authorizations AFTER:"
pkcheck --list-temp 2>&1 | sed 's/^/   /'
