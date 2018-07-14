#!/usr/bin/env python3
from bs4 import BeautifulSoup
import datetime
import json
import os
import re
import requests


def makepair(url):
    return [url.split('/')[-1], url]


def addurls(versions, version, subversion, table):
    assert table['class'] == ['downloads']
    if version not in versions:
        versions[version] = {
            'subversion': subversion,
            'urllist': []
        }
    urllist = versions[version]['urllist']
    links = table.find_all('a')
    for link in links:
        url = link['href']
        if any(map(lambda x: url.endswith(x), ['.exe', '.dmg', '.zip', '.tar.gz', '.asc'])):
            urllist.append(makepair(url))
    for checksum in ['md5', 'sha256']:
        url = 'https://julialang-s3.julialang.org/bin/checksums/julia-%s.%s' % (subversion[1:], checksum)
        t = requests.get(url)
        if t.ok:
            urllist.append(makepair(url))


def main():
    infofile = os.path.join(os.path.dirname(__file__), '../data/releaseinfo.json')

    data = {
        'versions': {}
    }
    versions = data['versions']
    subversion_regex = re.compile(r'v\d+\.\d+\.\d+(-\w+)?')
    version_regex = re.compile(r'v\d+\.\d+')

    # Older releases
    r = requests.get('https://julialang.org/downloads/oldreleases.html')
    soup = BeautifulSoup(r.content, 'html.parser')
    h2s = soup.find_all('h2')
    for h2 in h2s:
        m = subversion_regex.search(h2.string)
        subversion = h2.string[m.start():m.end()]
        version = subversion[:version_regex.search(subversion).end()]
        table = h2.find_next('table')
        addurls(versions, version, subversion, table)

    # Current releases
    r = requests.get('https://julialang.org/downloads/')
    soup = BeautifulSoup(r.content, 'html.parser')
    h1s = soup.find_all('h1')
    for h1 in h1s:
        m = subversion_regex.search(h1.string)
        if m is None:
            continue
        subversion = h1.string[m.start():m.end()]
        version = subversion[:version_regex.search(subversion).end()]
        table = h1.find_next('table')
        addurls(versions, version, subversion, table)

    # Nightly builds
    r = requests.get('https://julialang.org/downloads/nightlies.html')
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find('table')
    addurls(versions, 'latest', 'latest', table)
    versions['latest']['urllist'].append(['julia-latest.tar.gz', 'https://github.com/JuliaLang/julia/archive/master.tar.gz'])

    data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(infofile, 'w') as fo:
        json.dump(data, fo, indent=4)


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
