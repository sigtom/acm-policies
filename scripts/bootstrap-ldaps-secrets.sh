#!/usr/bin/env bash
# Run locally with the intended cluster's separate admin kubeconfig.
# This script generates Secret payloads only in a pipe; never commit a Secret.
set +x
set -euo pipefail
umask 077
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 /absolute/path/to/admin-kubeconfig https://api.expected.example:6443" >&2
  exit 2
fi
KUBECONFIG_FILE="$1"
EXPECTED_SERVER="$2"
[[ -r "$KUBECONFIG_FILE" ]] || { echo "Kubeconfig is not readable." >&2; exit 2; }
actual_server="$(oc --kubeconfig="$KUBECONFIG_FILE" whoami --show-server)"
[[ "$actual_server" == "$EXPECTED_SERVER" ]] || { echo "Cluster server does not match the expected target; refusing." >&2; exit 2; }
oc --kubeconfig="$KUBECONFIG_FILE" whoami
printf 'Target cluster: %s\n' "$actual_server"
for ns in openshift-config ad-ldap-sync; do
  oc --kubeconfig="$KUBECONFIG_FILE" get namespace "$ns" >/dev/null
  if oc --kubeconfig="$KUBECONFIG_FILE" get secret ad-ldap-bind -n "$ns" --ignore-not-found -o name | grep -q .; then
    printf 'Secret already exists in %s. Use its authoritative secret manager if one owns it.\n' "$ns"
  fi
done
read -r -p 'Type PROVISION to create/update both bind Secrets on this cluster: ' consent
[[ "$consent" == PROVISION ]] || { echo 'Stopped without changing Secrets.'; exit 1; }
read -r -s -p 'AD read-only bind password: ' password
printf '\n'
read -r -s -p 'Repeat bind password: ' repeated
printf '\n'
[[ -n "$password" && "$password" == "$repeated" ]] || { echo 'Passwords are empty or do not match.' >&2; exit 2; }
tmp="$(mktemp "${TMPDIR:-/tmp}/ad-ldap-bind.XXXXXX")"
trap 'rm -f "$tmp"; unset password repeated' EXIT
printf '%s' "$password" >"$tmp"
unset password repeated
for ns in openshift-config ad-ldap-sync; do
  oc --kubeconfig="$KUBECONFIG_FILE" create secret generic ad-ldap-bind \
    --namespace="$ns" --type=Opaque \
    --from-file="bindPassword=$tmp" --dry-run=client -o json |
  oc --kubeconfig="$KUBECONFIG_FILE" apply --server-side \
    --field-manager=ad-ldaps-secret-bootstrap -f -
done
echo 'Both bind-password Secrets were submitted. No secret values were printed.'
echo 'If one update failed, fix ownership/authorization, then reconcile both copies. Do not use --force-conflicts.'
