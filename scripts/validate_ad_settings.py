#!/usr/bin/env python3
"""Check one completed hub-side settings ConfigMap. Requires Python 3 and PyYAML.
This validates input shape and PEM parsing, not AD connectivity or filter results.
"""
from __future__ import annotations
import argparse
import re
import ssl
import sys
from pathlib import Path
import yaml

class UniqueLoader(yaml.SafeLoader):
    pass

def unique_map(loader: UniqueLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_map)

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def load_settings(path: Path, *, verify_pem: bool = True) -> tuple[dict, dict]:
    cm = yaml.load(path.read_text(), Loader=UniqueLoader)
    require(isinstance(cm, dict), 'Expected one ConfigMap document.')
    require(cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap', 'Expected v1 ConfigMap.')
    md = cm.get('metadata', {})
    require(md.get('namespace') == 'open-cluster-management-policies', 'Wrong hub ConfigMap namespace.')
    labels = md.get('labels', {})
    require(labels.get('acm-config') == 'ad-ldaps', 'Missing acm-config=ad-ldaps label.')
    cluster = labels.get('managed-cluster', '')
    require(bool(cluster) and cluster != 'managed-cluster-template' and 'REPLACE_WITH_' not in cluster,
            'Set managed-cluster to the actual ACM ManagedCluster name.')
    data = cm.get('data', {})
    require(isinstance(data, dict) and isinstance(data.get('settings.yaml'), str), 'Missing data.settings.yaml string.')
    s = yaml.load(data['settings.yaml'], Loader=UniqueLoader)
    require(isinstance(s, dict), 'settings.yaml must be a YAML mapping.')
    encoded = yaml.safe_dump(s)
    require('REPLACE_WITH_' not in encoded, 'Unresolved settings placeholder.')
    require('{{' not in encoded, 'Do not place Go/ACM template delimiters inside settings.')
    for key in ('configurationApproved', 'syncSuspend', 'syncConfirm', 'nestedGroups'):
        require(type(s.get(key)) is bool, f'{key} must be a YAML boolean, not a quoted string.')
    require(s['configurationApproved'], 'Review settings and then set configurationApproved: true.')
    for key in ('bindDN', 'usersBaseDN', 'oauthUserFilter', 'syncUserFilter', 'userNameAttribute',
                'userIDAttribute', 'displayNameAttribute', 'emailAttribute', 'caBundle', 'syncImage', 'syncSchedule'):
        require(isinstance(s.get(key), str) and bool(s[key].strip()), f'{key} must be a nonempty string.')
    require(re.fullmatch(r'ldaps://[A-Za-z0-9.-]+:[0-9]+', str(s.get('ldapURL', ''))) is not None,
            'ldapURL must be ldaps://DNS-NAME:PORT, without credentials, path, or query.')
    port = int(s['ldapURL'].rsplit(':', 1)[1])
    require(1 <= port <= 65535, 'Invalid LDAPS TCP port.')
    require(re.fullmatch(r'[a-z0-9][a-z0-9.-]*[a-z0-9]', str(s.get('idpName', ''))) is not None, 'Invalid idpName.')
    require(s.get('mappingMethod') == 'claim', 'Initial rollout uses mappingMethod: claim.')
    for key in ('userNameAttribute', 'userIDAttribute', 'displayNameAttribute', 'emailAttribute'):
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', s[key]) is not None, f'Invalid {key}.')
    require(s['userNameAttribute'].lower() not in ('objectguid', 'objectsid'), 'Group usernames must not be binary attributes.')
    for key in ('bindDN', 'usersBaseDN', 'oauthUserFilter', 'syncUserFilter'):
        require('\n' not in s[key] and '\r' not in s[key], f'{key} must occupy one line.')
    for key in ('oauthUserFilter', 'syncUserFilter'):
        require(s[key].startswith('(') and s[key].endswith(')'), f'{key} must be a complete LDAP filter.')
    ca = s['caBundle']
    require('-----BEGIN CERTIFICATE-----' in ca and 'PRIVATE KEY' not in ca, 'Use public PEM CA certificates only.')
    if verify_pem:
        ssl.create_default_context().load_verify_locations(cadata=ca)
    require(re.fullmatch(r'[-A-Za-z0-9._/:]+@sha256:[a-f0-9]{64}', s['syncImage']) is not None,
            'Use a digest-pinned approved OpenShift CLI image.')
    require(len(s['syncSchedule'].split()) == 5, 'Use a five-field CronJob schedule. Server dry-run verifies its syntax.')
    groups = s.get('groups')
    require(isinstance(groups, list) and bool(groups), 'Provide at least one approved group mapping.')
    dns, names = set(), set()
    for group in groups:
        require(isinstance(group, dict), 'Each group must be a mapping.')
        dn, name = group.get('ldapDN', ''), group.get('openshiftName', '')
        require(isinstance(dn, str) and bool(dn) and '\n' not in dn and '\r' not in dn, 'Invalid group DN.')
        require(isinstance(name, str) and re.fullmatch(r'ad-[a-z0-9]([a-z0-9.-]*[a-z0-9])?', name) is not None,
                'OpenShift group names must be distinct ad-* names.')
        require(dn not in dns and name not in names, 'Duplicate LDAP group DN or OpenShift group name.')
        dns.add(dn); names.add(name)
    bindings = s.get('rbacBindings', [])
    require(isinstance(bindings, list), 'rbacBindings must be a list.')
    binding_ids = set()
    for b in bindings:
        require(isinstance(b, dict), 'Each role binding must be a mapping.')
        require(b.get('kind') in ('RoleBinding', 'ClusterRoleBinding'), 'Invalid RBAC binding kind.')
        require(b.get('group') in names, 'RBAC group is not in the approved mapping.')
        require(str(b.get('name', '')).startswith('ad-ldaps-'), 'Use unique ad-ldaps-* binding names.')
        require(bool(b.get('clusterRole')), 'RBAC clusterRole is missing.')
        require(b['kind'] != 'RoleBinding' or bool(b.get('namespace')), 'RoleBinding requires an existing project namespace.')
        identity = (b['kind'], b.get('namespace', ''), b['name'])
        require(identity not in binding_ids, 'Duplicate RBAC binding identity.')
        binding_ids.add(identity)
    return cm, s

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('settings_configmap', type=Path)
    args = parser.parse_args()
    try:
        cm, s = load_settings(args.settings_configmap)
    except Exception as exc:
        print(f'Validation failed: {exc}', file=sys.stderr)
        sys.exit(1)
    print('Settings structure, placeholder checks, and CA PEM parsing passed.')
    print(f"Approved group mappings: {len(s['groups'])}; scheduled job suspended: {s['syncSuspend']}; group writes enabled: {s['syncConfirm']}")
    print('AD query behavior, TLS trust, group membership, username mapping, and server admission still require live validation.')

if __name__ == '__main__':
    main()
