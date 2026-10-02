# AD over LDAPS: hub first, workload cluster second

This capability configures OpenShift 4.21's built-in LDAP identity provider and
runs `oc adm groups sync` in a CronJob. No community Group Sync Operator or AAP
is installed. Existing operator, networking and Dell storage policies are unchanged.

## Start here: replace values in ONE settings file per cluster

Template: `acm/clusters/managed-cluster-template/ad-ldaps/examples/settings.yaml`.
**Do not edit customer values into this sanitized repository.** Make a completed
copy in the restricted client repository. Never commit passwords, tokens or
private keys. The issuing/root CA certificate chain is public trust material.

| Location / setting | Replace or review |
|---|---|
| ConfigMap `metadata.name` | Replace `managed-cluster-template` with the actual target ManagedCluster name. |
| Label `managed-cluster` | Actual ACM ManagedCluster name, not the API hostname. |
| `ldapURL` | `REPLACE_WITH_LDAPS_FQDN`; certificate-matching DNS endpoint and TLS port. |
| `bindDN` | `REPLACE_WITH_READ_ONLY_BIND_DN`; directory read/search account. |
| `usersBaseDN` | `REPLACE_WITH_USERS_BASE_DN`; covers all intended users. |
| `oauthUserFilter` | `REPLACE_WITH_APPROVED_LOGIN_FILTER`; AD-approved login restriction and disabled-account handling. |
| `groups[].ldapDN` | `REPLACE_WITH_PILOT_GROUP_DN`; explicitly approved group DNs only. |
| `groups[].openshiftName` | Unique new `ad-*` OpenShift group names; review before using an existing name. |
| `caBundle` | `REPLACE_WITH_PEM_CA_CHAIN`; public PEM issuing/root CA chain, no private key. |
| `syncImage` | `REPLACE_WITH_APPROVED_CLI_IMAGE` and `REPLACE_WITH_64_HEX_DIGEST`; approved OpenShift 4.21 CLI image/mirror. |
| Username / identity attributes | Confirm `sAMAccountName` versus `userPrincipalName`, and `objectGUID` for OAuth identity ID. Login and group sync use the same username attribute. |
| `syncUserFilter`, `nestedGroups` | Confirm user scope, disabled users and direct/nested membership with AD. |
| `idpName`, `mappingMethod` | Default `ad-ldaps` / `claim`; do not take over an existing provider. |
| `syncSchedule` | Default every 30 minutes in UTC; agree the interval and revocation needs. |
| `configurationApproved` | Keep `false` until the completed values have been reviewed; then set `true`. |
| `syncSuspend`, `syncConfirm` | Initially `true` / `false`; schedule suspended and group writes disabled. |
| `rbacBindings` | Initially empty. Approve access separately; no automatic administrator grant. |

Do not change identity names, attributes, mapped groups or the LDAP endpoint later
without reviewing existing Users, Identities and Groups. `sAMAccountName` must be
unique within the chosen domain scope. AD primary-group membership is not assumed
to appear in `memberOf`. Test direct, nested and empty group membership explicitly.

## Files and GitOps wiring

Five active Policies live in `acm/capabilities/ad-ldaps/`:

```
ad-ldaps-prereqs -> ad-ldap-sync namespace
ad-ldaps-trust   -> CA ConfigMaps in openshift-config and ad-ldap-sync
ad-ldaps-secrets -> inform-only checks of target-local bind-password Secrets
ad-ldaps-groups  -> sync ConfigMap, allowlist, ServiceAccount, RBAC and CronJob
ad-ldaps-oauth   -> one named LDAP provider in OAuth/cluster
```

There are two Placements and two PlacementBindings: `ad-ldaps` for preparation,
and `ad-ldaps-login` for OAuth activation. Each cluster queries AD independently;
the workload cluster does not inherit the hub's Groups or authenticate via the hub.

The repository parent Kustomizations include these reusable files. When copying
to the client repository, preserve existing entries and add each reference once:

- `acm/capabilities/kustomization.yaml`: `ad-ldaps/`
- `acm/placements/kustomization.yaml`: `ad-ldaps.yaml`, `ad-ldaps-login.yaml`
- `acm/bindings/kustomization.yaml`: `ad-ldaps.yaml`, `ad-ldaps-login.yaml`

The cluster template has `resources: []`; placeholder settings are NOT deployed.
For each real target, copy the completed settings to
`acm/clusters/<actual-managed-cluster>/ad-ldaps/settings.yaml`, list `settings.yaml`
in that directory's Kustomization, and include `ad-ldaps/` from its cluster parent.
Ensure that cluster directory is included by `acm/clusters/kustomization.yaml`.
Do not rename or replace existing client cluster directories or Dell configuration.

## Hub preflight

Use a separate admin kubeconfig. Do not overwrite it during AD login testing.

```bash
export HUB_KUBECONFIG=/REPLACE_WITH_PATH_TO_HUB_ADMIN_KUBECONFIG
oc --kubeconfig="$HUB_KUBECONFIG" whoami
oc --kubeconfig="$HUB_KUBECONFIG" whoami --show-server
oc --kubeconfig="$HUB_KUBECONFIG" get managedclusters -l local-cluster=true
```

Record the actual self-managed hub name as `HUB_MC`. Verify Available/Accepted
conditions, policy add-ons in its namespace, and the ManagedClusterSet binding:

```bash
export HUB_MC=REPLACE_WITH_ACTUAL_HUB_MANAGEDCLUSTER_NAME
oc --kubeconfig="$HUB_KUBECONFIG" get managedcluster "$HUB_MC" -o yaml
oc --kubeconfig="$HUB_KUBECONFIG" get managedclusteraddons -n "$HUB_MC"
oc --kubeconfig="$HUB_KUBECONFIG" get managedclustersetbindings \
  -n open-cluster-management-policies -o yaml
oc --kubeconfig="$HUB_KUBECONFIG" get oauth.config.openshift.io cluster -o yaml
```

If the hub's set is not bound, adapt `optional/managedclustersetbinding.yaml` to
the actual set. Add it through `acm/configurations` only after checking existing
bindings. Do not blindly bind a global set. Review any existing policy or GitOps
owner of OAuth, the helper namespace, Groups and RBAC before proceeding.

Keep non-AD emergency administrator access. Back up OAuth securely outside Git.
Confirm DNS and LDAPS reachability from authentication pods and the sync job,
trusted server certificates, firewall/proxy rules and approved CLI image access.
Do not bypass certificate verification.

## Validation before activation

Requires `oc`, Git and Python 3/PyYAML for the helper scripts.

```bash
export SETTINGS_FILE=acm/clusters/REPLACE_WITH_HUB_MANAGEDCLUSTER/ad-ldaps/settings.yaml
python3 scripts/validate_ad_settings.py "$SETTINGS_FILE"
oc kustomize acm/ > /tmp/acm-ldaps-rendered.yaml

oc --kubeconfig="$HUB_KUBECONFIG" apply --server-side --dry-run=server \
  -k acm/capabilities/ad-ldaps

oc --kubeconfig="$HUB_KUBECONFIG" apply --server-side --dry-run=server \
  -f acm/placements/ad-ldaps.yaml \
  -f acm/placements/ad-ldaps-login.yaml \
  -f acm/bindings/ad-ldaps.yaml \
  -f acm/bindings/ad-ldaps-login.yaml
```

A hub Policy dry-run does not validate
rendered target objects, AD queries or login. Check the target configuration with
ACM's template tooling and server dry-runs after replacing placeholders.

Before merge, inspect both capability labels on all ManagedClusters. Existing
labels may already select a target; this change does not add any labels itself.
Use the client feature-branch/review/merge workflow, then verify Argo synced the
correct revision and the five Policies, two Placements and two bindings exist.

## Phase 1: hub preparation and group preview

Only after the hub settings and recovery access have been reviewed:

```bash
oc --kubeconfig="$HUB_KUBECONFIG" label managedcluster "$HUB_MC" \
  capability.ad-ldaps=true --overwrite
```

Do NOT add the login label or label the workload cluster yet. Missing credentials
make `ad-ldaps-secrets` NonCompliant and block group configuration by design.

Provision the following two target-local Opaque Secrets, each with a nonempty
`bindPassword` key, through Vault/ESO or the approved secret process:

- `openshift-config/ad-ldap-bind`
- `ad-ldap-sync/ad-ldap-bind`

After the namespace exists, the optional helper prompts without echoing the
password, checks the target server, uses a 0600 temporary file and submits the
Secrets via server-side apply. It does not force field-ownership conflicts.

```bash
bash scripts/bootstrap-ldaps-secrets.sh "$HUB_KUBECONFIG" \
  https://REPLACE_WITH_EXPECTED_HUB_API_FQDN:6443
```

Wait for the four preparation policies to become Compliant. Verify the CronJob
is suspended and its `SYNC_CONFIRM` environment value is `false` before preview.

```bash
oc --kubeconfig="$HUB_KUBECONFIG" get cronjob ad-ldap-group-sync -n ad-ldap-sync -o yaml
JOB="ad-ldap-preview-$(date +%s)"
oc --kubeconfig="$HUB_KUBECONFIG" create job "$JOB" \
  --from=cronjob/ad-ldap-group-sync -n ad-ldap-sync
oc --kubeconfig="$HUB_KUBECONFIG" wait --for=condition=Complete \
  "job/$JOB" -n ad-ldap-sync --timeout=600s
oc --kubeconfig="$HUB_KUBECONFIG" logs "job/$JOB" -n ad-ldap-sync
```

Review exact group names and memberships, including empty/nested groups and
membership removal. Logs can contain user/group information; keep them private.
No `--confirm` means no Group changes are saved. If the job fails, inspect its
status/logs and stop. Do not loosen TLS, RBAC or the allowlist to make it pass.

After approval, set `syncConfirm: true` in the hub settings but keep
`syncSuspend: true`. Commit/review the change, wait for reconciliation, verify
the CronJob value, then create one new manual Job. Validate the resulting Groups.
Scheduled concurrency control does not prevent overlapping manually created Jobs.

## Phase 2: hub login, then scheduled synchronization

Preflight the new provider while preserving the live providers:

```bash
oc --kubeconfig="$HUB_KUBECONFIG" get oauth.config.openshift.io cluster -o json | \
  python3 scripts/preview_oauth.py "$SETTINGS_FILE" | \
  oc --kubeconfig="$HUB_KUBECONFIG" replace --dry-run=server -f -
```

Run this pipeline in a shell with `set -o pipefail`. It is a preview only; do not
apply its full output. The helper refuses an already-used provider name. The ACM
policy uses `musthave` for one named provider, not replacement of the whole list.

After the group checks and OAuth preview pass:

```bash
oc --kubeconfig="$HUB_KUBECONFIG" label managedcluster "$HUB_MC" \
  capability.ad-ldaps-login=true --overwrite
oc --kubeconfig="$HUB_KUBECONFIG" get clusteroperator authentication
```

Check Authentication Available=True, Degraded=False, Progressing=False; verify
other identity providers remain intact. Test an authorized pilot login using a
NEW kubeconfig, an unauthorized user, a disabled account, intended username
mapping, group membership removal and non-AD emergency access.

Group sync is not an access grant, and its allowlist is not the login filter.
Review baseline authenticated-user rights. No `cluster-admin` binding is created.

Optional approved access uses
`acm/capabilities/ad-ldaps/examples/ad-ldaps-access.yaml` plus
`optional/ad-ldaps-access-placementbinding.yaml`. These files are excluded from
the default build. Approve explicit `rbacBindings`, include the optional files,
and verify each target namespace and referenced ClusterRole before activation.

Only after testing, set `syncSuspend: false` with `syncConfirm: true` in Git.
Monitor scheduled job failures and group-sync timestamps. No group pruning is
configured. Define handling of deleted AD groups, stale memberships and existing
sessions/tokens; do not assume disabling an AD account instantly revokes them.

## Workload rollout

Repeat with a separate target settings ConfigMap and target-local Secrets. Use
its own administrator kubeconfig. Enable preparation, preview and confirmed sync
first, then its login label. Do not copy the hub's Users, Identities or Groups.
No new policies are needed. Keep the workload target unlabeled until hub tests pass.

## Rollback

Removing a capability label removes targeting, not the retained resources. First
stop reconciliation for ONLY the affected target/capability using the approved
GitOps/ACM process. Coordinate emergency edits so active policies do not revert
them. Do not stop unrelated Dell, network or operator policies.

Suspend the affected target's CronJob and check for active manual/scheduled Jobs.
After reviewing any active job, stop it through the approved change process. Remove
only the new named LDAP provider, preserving all other OAuth providers. Dry-run a
name-specific guarded JSON patch and review it before applying. Do not replace
OAuth with an empty provider list. Verify non-AD access and authentication health.

Review optional access bindings, Group memberships and active sessions separately;
removing the provider does not remove group-based authorization. Retain CA and
Secrets until references are checked. Do not bulk-delete Groups or shared RBAC.

## Sources and limits

- [OpenShift 4.21 LDAP provider](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/authentication_and_authorization/configuring-identity-providers)
- [OpenShift 4.21 group sync, CronJobs and nested AD membership](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/authentication_and_authorization/ldap-syncing)
- [ACM 2.14 governance and template functions](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.14/html/governance/governance)

This wrapper's gates, naming, schedule, resources and RBAC are design choices.
No live cluster or AD validation is claimed. See `VALIDATION.md` in this directory.
