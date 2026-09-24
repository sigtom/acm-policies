# ACM policies

Sanitized ACM and Kustomize templates for deploying Dell Container Storage Modules (CSM) for PowerFlex to an OpenShift managed cluster.

The repository separates reusable policies from cluster-specific data:

```text
acm/
├── bindings/
├── capabilities/
│   └── dell-csm/
├── clusters/
│   └── managed-cluster-template/
├── configurations/
├── placements/
└── kustomization.yaml
```

## Policy chain

```text
powerflex-storage-network
        |
        v
dell-csm-operator
        |
        +--> dell-csm-pf-prereqs
        |              |
        |              v
        |    dell-csm-powerflex-secret
        |              |
        +--------------+
                       v
             dell-csm-powerflex
                       |
                       v
        dell-csm-powerflex-storage
```

The placement selects a managed cluster only when it has all three labels:

```yaml
capability.nmstate: "true"
capability.powerflex: "true"
capability.dell-csm: "true"
```

## Before use

1. Rename `acm/clusters/managed-cluster-template/` to the ACM managed-cluster name.
2. Replace every `managed-cluster-template` value in that directory with the same managed-cluster name.
3. Replace the PowerFlex placeholders in `dell-csm/examples/storage-class.yaml`.
4. Review the pinned Dell CSM operator and driver configuration versions.
5. Copy the completed storage files out of `examples/`, add them to the cluster `kustomization.yaml`, and validate the build.
6. Create `vxflexos/vxflexos-config` through Vault or a controlled process outside Git.
7. Confirm the PowerFlex storage-network policy is compliant.
8. Add `capability.dell-csm: "true"` to the managed cluster only when the configuration is ready.

The cluster-specific files remain excluded from Kustomize until they are copied from `examples/` and listed in the active cluster `kustomization.yaml`.

## Secret handling

Do not commit the PowerFlex username, password, gateway endpoint, MDM addresses, or rendered Secret manifest.

The policies expect this Secret on the managed cluster:

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

Create this manifest outside the repository. HashiCorp Vault can later manage the same Secret without changing the Dell CSM policy.

## Settings to review

The template preserves these deployment choices and does not claim they suit every cluster:

- Dell CSM operator CSV: `dell-csm-operator-certified.v1.12.2`
- PowerFlex driver configuration: `v2.17.0`
- Controller replicas: `2`
- Storage capacity tracking: disabled
- Force driver removal: enabled
- StorageClass filesystem: `xfs`
- StorageClass default annotation: enabled
- StorageClass reclaim policy: `Delete`
- Volume binding mode: `WaitForFirstConsumer`
- Snapshot deletion policy: `Delete`
- CDI clone strategy: `csi-clone`
