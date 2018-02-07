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
    # Older releases
    r = requests.get('https://julialang.org/downloads/oldreleases.html')
    soup = BeautifulSoup(r.content, 'html.parser')
    versions = data['versions']
    h2s = soup.find_all('h2')
    subversion_regex = re.compile(r'v\d+\.\d+\.\d+')
    version_regex = re.compile(r'v\d+\.\d+')
    for h2 in h2s:
        m = subversion_regex.search(h2.string)
        subversion = h2.string[m.start():m.end()]
        version = subversion[:version_regex.search(subversion).end()]
        table = h2.find_next('table')
        addurls(versions, version, subversion, table)
    # Current releases
    r = requests.get('https://julialang.org/downloads/')
    soup = BeautifulSoup(r.content, 'html.parser')
    string = soup.find(string=subversion_regex)
    m = subversion_regex.search(string)
    subversion = string[m.start():m.end()]
    version = subversion[:version_regex.search(subversion).end()]
    table = soup.find('table')
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
#     "julia-latest-win32.exe",
#     "https://julialangnightlies-s3.julialang.org/bin/winnt/x86/julia-latest-win32.exe"
# ],
# [
#     "julia-latest-linuxarmv7l.tar.gz",
#     "https://julialangnightlies-s3.julialang.org/bin/linux/armv7l/julia-latest-linuxarmv7l.tar.gz"
# ],
# [
#     "julia-latest-linuxaarch64.tar.gz",
#     "https://julialangnightlies-s3.julialang.org/bin/linux/aarch64/julia-latest-linuxaarch64.tar.gz"
# ],
