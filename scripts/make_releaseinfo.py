#!/usr/bin/env python3
from bs4 import BeautifulSoup
import datetime
import json
import os
import re
import requests
import sys


VERSION_REGEX = re.compile(r'v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(-(?P<status>\w+))?')
STATUS_TYPES = ['rc', 'pre', 'beta', 'alpha']

def compare_version(v1, v2):
    for v in ('major', 'minor', 'patch'):
        if v1[v] != v2[v]:
            return int(v1[v]) > int(v2[v])
    if v1['status'] is None:
        return True
    if v2['status'] is None:
        return False
    # Since 'rc3' > 'rc2' > 'pre' > 'beta2' > 'beta' > 'alpha'.
    # And it's normally impossible to have a status like 'rc10'.
    return v1['status'] > v2['status']


def update_versions(versions, tag):
    m = VERSION_REGEX.match(tag['name'])
    if m is None:
        return False
    m = m.groupdict()
    version = 'v%s.%s' % (m['major'], m['minor'])
    if version not in versions:
        versions[version] = {'subversion': tag['name']}
    else:
        ms = VERSION_REGEX.match(versions[version]['subversion']).groupdict()
        if compare_version(m, ms):
            versions[version]['subversion'] = tag['name']
    return True


def make_versions():
    print('Generating version info...')
    versions = {
        'latest': {
            'subversion': 'latest'
        }
    }
    julia_tags = requests.get('https://api.github.com/repos/JuliaLang/julia/tags').json()
    for tag in julia_tags:
        update_versions(versions, tag)
    return versions


def make_url(base, path, filename=None):
    return [
        filename if filename else os.path.basename(path),
        os.path.join(base, path)
    ]


def make_urllist(versions):
    print('Generating URL list...')
    base_url = 'https://julialang-s3.julialang.org/'
    github_url = 'https://github.com/JuliaLang/julia/archive/'
    julia_files = BeautifulSoup(requests.get(base_url).content, 'xml')
    keys = [key.string for key in julia_files.find_all('Key')]
    for version in versions:
        if version == 'latest':
            continue
        urllist = versions[version]['urllist'] = []
        # 'v0.7.0-beta' -> '0.7.0-beta-'
        subversion_regex = re.compile('%s-(?!(%s))' % (
            versions[version]['subversion'][1:], '|'.join(STATUS_TYPES)
        ))
        for key in keys:
            if subversion_regex.search(key) is not None:
                urllist.append(make_url(base_url, key))
        urllist.append(
            make_url(github_url, 'release-%s.tar.gz' % version[1:])
        )
    nightly_url = 'https://julialangnightlies-s3.julialang.org/'
    nightly_files = BeautifulSoup(requests.get(nightly_url).content, 'xml')
    urllist = versions['latest']['urllist'] = [
        make_url(nightly_url, key.string)
        for key in nightly_files.find_all('Key')
        if key.string.find('latest') >= 0
    ]
    urllist.append(make_url(github_url, 'master.tar.gz', 'julia-latest.tar.gz'))
    return versions


def should_update(data, old_data):
    return old_data is None or data['versions'] != old_data['versions']


def main():
    if len(sys.argv) not in (2, 3) or os.path.isdir(sys.argv[1]):
        print('Usage: ./make_releaseinfo.py ../data/releaseinfo.json [force_update=0]')
        exit(1)
    infofile = sys.argv[1]
    force_update = len(sys.argv) == 3 and bool(sys.argv[2])
    data = {
        'versions': make_urllist(make_versions())
    }
    data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    old_data = None
    if not force_update and os.path.isfile(infofile):
        with open(infofile) as fi:
            old_data = json.load(fi)
    if should_update(data, old_data):
        with open(infofile, 'w') as fo:
            json.dump(data, fo, indent=4)
        print('Release info generated in %s' % infofile)
    else:
        print('No update needed.')


if __name__ == '__main__':
    main()

# The following items are removed from the json file because of 404.
# [
#     "julia-latest-linuxarmv7l.tar.gz",
#     "https://julialangnightlies-s3.julialang.org/bin/linux/armv7l/julia-latest-linuxarmv7l.tar.gz"
# ],
# [
#     "julia-latest-linuxaarch64.tar.gz",
#     "https://julialangnightlies-s3.julialang.org/bin/linux/aarch64/julia-latest-linuxaarch64.tar.gz"
# ],
