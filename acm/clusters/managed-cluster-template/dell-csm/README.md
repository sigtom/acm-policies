# Dell CSM cluster configuration template

This directory holds hub-side ConfigMaps for one ACM managed cluster.

Before use:

1. Rename the parent directory `managed-cluster-template` to the ACM managed-cluster name.
2. Replace every `managed-cluster-template` string in the copied YAML files with the same managed-cluster name.
3. Replace every PowerFlex placeholder.
4. Copy the completed YAML files from `examples/` into this directory.
5. List the copied files in `kustomization.yaml`.

The reusable `dell-csm-powerflex-storage` policy selects ConfigMaps with these labels:

```yaml
acm-config: dell-csm-powerflex
managed-cluster: managed-cluster-template
```

It then enforces the Kubernetes object stored in `data.object` on the matching managed cluster.

## StorageClass values

Replace these placeholders in `examples/storage-class.yaml`:

- `REPLACE_WITH_STORAGE_POOL`
- `REPLACE_WITH_PROTECTION_DOMAIN`
- `REPLACE_WITH_SYSTEM_ID`

The same system ID must appear in both `parameters.systemID` and the `allowedTopologies` key.

## Required Secret

Do not store the Secret in Git. Create it through Vault or a controlled process outside this repository:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: vxflexos-config
  namespace: vxflexos
type: Opaque
stringData:
  config: |
    - username: REPLACE_WITH_POWERFLEX_USERNAME
      password: REPLACE_WITH_POWERFLEX_PASSWORD
      systemID: REPLACE_WITH_SYSTEM_ID
      endpoint: REPLACE_WITH_POWERFLEX_ENDPOINT
      skipCertificateValidation: true
      mdm: REPLACE_WITH_MDM_VALUE
```

The ACM secret policy checks only that `vxflexos/vxflexos-config` exists and has type `Opaque`. It does not read or copy the Secret data to the hub.

## Activation

After replacing the values and copying the three storage files into this directory, set:

```yaml
resources:
  - storage-class.yaml
  - volume-snapshot-class.yaml
  - storage-profile.yaml
```

Confirm that no other StorageClass remains marked as default before enabling this template. Then add `capability.dell-csm: "true"` to the managed cluster.
