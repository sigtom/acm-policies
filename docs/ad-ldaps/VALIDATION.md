# LDAPS pre-push validation

The LDAPS change was prepared against repository main commit
`79a9fb84b47c1b3bb52242f1d89d9866bc5037a8`.

## Checked locally

- YAML parsed with duplicate mapping keys rejected.
- New Policy identities and child ConfigurationPolicy names are unique within
  this capability. Root namespace-plus-name lengths are below 62 characters.
- Dependency names resolve inside the new policy set; optional access stays excluded.
- The settings template is excluded from the active build and starts unapproved,
  with the CronJob suspended and group writes disabled.
- Actual raw Go template text rendered with Go text/template and local helper
  implementations using neutral fixtures, including direct/nested group membership,
  OAuth, trust, optional access and secret-existence checks.
- Rendered object checks cover group-only RBAC, allowlisted group update names,
  matching login/sync username attributes, mounted-password references, verified TLS,
  suspended scheduling and preview mode.
- Negative fixtures reject absent/duplicate settings, unapproved settings,
  unresolved placeholders, malformed boolean flags, plain LDAP, tag-only images,
  empty groups, binary usernames, private-key text and automatic identity linking.
- Credential sentinel values do not appear in rendered secret-check output.
- Python syntax and shell syntax passed. The settings helper accepted a neutral
  completed fixture with a parseable public CA. The OAuth preview preserved an
  existing provider while adding the desired named provider.
- Outgoing files were scanned for known customer identifiers and private-key material.
- All existing capability content is retained through a Git tree based on the
  current repository tree. Only new files and four parent Kustomizations change.

## Not claimed

Native Kustomize execution was not available in this environment; installing the
binary was blocked by network/DNS access. File-reference checks are not a substitute
for running `oc kustomize acm/` on the jump host.

The local rendering harness used helper stubs and JSON-compatible YAML fixtures;
it was not the live ACM controller. Hub and managed-cluster API admission, live
AD binds/queries, OAuth login, real CLI image execution under restricted SCC,
empty/deleted-group behavior and token/session revocation require client testing.

No customer cluster changes, credentials or customer-specific configuration are
part of the commit. No claim is made that the client integration is already working.
