# AD / LDAPS policies

Start with [the hub-first runbook](../../../docs/ad-ldaps/README.md).

Replace AD values only in a copy of
`acm/clusters/managed-cluster-template/ad-ldaps/examples/settings.yaml`
in the restricted client repository. The runbook lists every placeholder.

No customer settings or credentials are stored here. The default settings stay
unapproved, scheduled sync stays suspended, and LDAP login has its own capability
label. Do not label the workload cluster before the hub tests pass.
