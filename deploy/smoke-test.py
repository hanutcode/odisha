"""Run inside the deployed container after Apache routing is enabled."""
import re
import requests
from pathlib import Path

base = 'http://167.172.152.167/cm'
session = requests.Session()
r = session.get(base + '/login/', timeout=20)
assert r.status_code == 200, r.status_code
assert '/cm/static/workspace/app.css' in r.text
assert 'Starting passwords' not in r.text
credentials = Path('/tmp/initial-logins.txt').read_text()
password = re.search(r'^\s*admin\s+(\S+)', credentials, re.M).group(1)
r = session.post(base + '/login/', data={'username': 'admin', 'password': password, 'csrfmiddlewaretoken': session.cookies['hcm_csrftoken']}, timeout=20)
assert r.status_code == 200 and r.url == base + '/', (r.status_code, r.url)
for path in ['/', '/data/', '/pipeline/', '/review/', '/panel/', '/seal/', '/map/', '/log/', '/password/', '/admin/', '/static/workspace/app.css']:
    r = session.get(base + path, timeout=20)
    assert r.status_code == 200, (path, r.status_code)
    print(path, r.status_code)
print('Authenticated deployment smoke test passed.')
