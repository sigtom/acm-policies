#!/usr/bin/env python3
"""Print a complete merged OAuth object for SERVER DRY-RUN ONLY.
Reads the live OAuth JSON from stdin; emits no passwords or Secret values.
The desired provider name must be unused for this first-install preflight.
Do not apply this output: ACM owns the new named identity provider.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote
from validate_ad_settings import load_settings

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('settings_configmap', type=Path)
a = p.parse_args()
try:
    _, s = load_settings(a.settings_configmap)
    live = json.load(sys.stdin)
    assert live.get('kind') == 'OAuth' and live['metadata']['name'] == 'cluster', 'Input must be OAuth/cluster.'
    existing = live.setdefault('spec', {}).setdefault('identityProviders', [])
    if any(v.get('name') == s['idpName'] for v in existing):
        raise ValueError('The desired identity-provider name already exists; review ownership/configuration before continuing.')
    url = f"{s['ldapURL']}/{quote(s['usersBaseDN'], safe='')}?{s['userNameAttribute']}?sub?{quote(s['oauthUserFilter'], safe='')}"
    existing.append({
        'name': s['idpName'], 'mappingMethod': 'claim', 'type': 'LDAP',
        'ldap': {'url': url, 'bindDN': s['bindDN'], 'bindPassword': {'name': 'ad-ldap-bind'},
                 'ca': {'name': 'ad-ldaps-ca'}, 'insecure': False,
                 'attributes': {'id': [s['userIDAttribute']], 'preferredUsername': [s['userNameAttribute']],
                                'name': [s['displayNameAttribute']], 'email': [s['emailAttribute']]}}
    })
    live.pop('status', None)
    live['metadata'].pop('managedFields', None)
    json.dump(live, sys.stdout, indent=2)
    print()
except Exception as e:
    print(f'OAuth preview failed: {e}', file=sys.stderr)
    sys.exit(1)
