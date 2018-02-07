#!/usr/bin/env python3
import argparse
import datetime
import json
import logging
import os
import urllib.request
import multiprocessing.pool


class Config(object):
    DATEFMT = '%Y-%m-%d %H:%M:%S'
    SETTINGS = ['mirror_releases', 'mirror_metadata', 'mirror_packages', 'sync_latest']
    REMOTE_RELEASEINFO = 'https://github.com/sunoru/julia-mirror/raw/master/data/releaseinfo.json'

    def __init__(self, root, mirror_releases, mirror_metadata, mirror_packages, sync_latest, force, max_processes):
        self.root = root
        self.mirror_releases = mirror_releases
        self.mirror_metadata = mirror_metadata
        self.mirror_packages = mirror_packages
        self.sync_latest = sync_latest
        self.force = force
        self.max_processes = max_processes

    def __str__(self):
        return '\n'.join(['%s=%s' % (k, getattr(self, k)) for k in self.__dict__])

    @property
    def status_file(self):
        return os.path.join(self.root, 'status.json')

    @property
    def releases_dir(self):
        return os.path.join(self.root, 'releases')

    @property
    def releaseinfo_file(self):
        return os.path.join(self.releases_dir, 'releaseinfo.json')

    @property
    def packages_dir(self):
        return os.path.join(self.root, 'packages')


def makedir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        if not os.path.isdir(path):
            raise Exception('%s already exists but is not a directory.' % path)


# Be careful to use this function!
def cleardir(path):
    for f in os.listdir(path):
        os.remove(os.path.join(path, f))


def download(url, path_or_filename=None):
    if path_or_filename is None or os.path.isdir(path_or_filename):
        path = os.getcwd() if path_or_filename is None else path_or_filename
        filename = os.path.join(path, url.split('/')[-1])
        # overflow can be catched anyway
    else:
        filename = path_or_filename
    # logging.info('Downloading %s to %s' % (url, filename))
    # won't work with multiprocessing
    urllib.request.urlretrieve(url, filename)


def get_config():
    parser = argparse.ArgumentParser(
        description='Build a mirror for the Julia language.')
    parser.add_argument('pathname', type=str,
                        help='path to the root of the mirror')
    parser.add_argument('--force', action='store_true',
                        help='force to rebuild the mirror')
    parser.add_argument('--no-releases', action='store_true',
                        help='do not mirror Julia releases')
    parser.add_argument('--no-metadata', action='store_true',
                        help='do not mirror METADATA.jl (and will automatically set --no-packages)')
    parser.add_argument('--no-packages', action='store_true',
                        help='do not mirror packages (but METADATA.jl)')
    parser.add_argument('--max-processes', type=int, nargs=1, default=4, metavar='N',
                        help='use up to N processes for downloading (default: 4)')
    parser.add_argument('--sync-latest-packages', type=float, nargs='?', default=0, const=1, metavar='N',
                        help='also mirror packages (at most %(metavar)s times in a day) on master branch ' +
                        '(default: 1)')
    parser.add_argument('--logging-file', type=str, default=None,
                        help='save log to a file instead of to STDOUT')
    parser.add_argument('--logging-level', type=lambda x: str(x).upper(), choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default='WARNING', help='set logging level (default: %(default)s)')
    args = parser.parse_args()
    if args.no_metadata:
        args.no_packages = True
    if args.no_packages and args.sync_latest_packages > 0:
        raise Exception('--sync-latest-packages must not be used with --no-packages.')
    logging_level = getattr(logging, args.logging_level, None)
    assert isinstance(logging_level, int)
    logging.basicConfig(filename=args.logging_file, level=logging_level,
                        format='[%(asctime)s]%(levelname)s:%(message)s', datefmt=Config.DATEFMT)
    root = os.path.abspath(args.pathname)
    makedir(root)
    config = Config(root, not args.no_releases, not args.no_metadata, not args.no_packages,
                    args.sync_latest_packages, args.force, args.max_processes)
    logging.info('Running with settings:\n%s' % config)
    return config


def _get_current_time():
    now = datetime.datetime.now()
    return now.strftime(Config.DATEFMT)


def save_status(config, status):
    status['last_updated'] = _get_current_time()
    with open(config.status_file, 'w') as fo:
        json.dump(status, fo, indent=4, sort_keys=True)


def get_current_status(config):
    if not os.path.exists(config.status_file):
        return None
    with open(config.status_file) as fi:
        status = json.load(fi)
    status_config = status.get('config', {})
    for arg in Config.SETTINGS:
        v1 = status_config.get(arg)
        v2 = getattr(config, arg)
        if v1 != v2:
            logging.warning('Setting %s changed from %s to %s.' % (arg, v1, v2))
            status_config[arg] = v2
    status['config'] = status_config
    return status


def initialize(config):
    logging.info('Creating status file and starting building mirror.')
    status = {
        'created_time': _get_current_time(),
        'releases': {'status': 'unavailable'},
        'pacakges': {'status': 'unavailable'},
    }
    makedir(config.releases_dir)
    makedir(config.packages_dir)
    save_status(config, status)
    return get_current_status(config)


def download_all(config, path, urllist):
    with multiprocessing.pool.Pool(config.max_processes) as pool:
        pool.starmap(download, ((url, os.path.join(path, filename)) for (filename, url) in urllist))


def fetch_releaseinfo(config, status):
    download(Config.REMOTE_RELEASEINFO, config.releaseinfo_file)
    with open(config.releaseinfo_file) as fi:
        meta = json.load(fi)
    return meta


def update_releases(config, status):
    s = status['releases']
    if config.force or s.get('created_time') is None:
        s = status['releases'] = {
            'created_time': _get_current_time()
        }
    logging.info('Updating mirror for Julia releases.')
    s['status'] = 'synchronizing'
    save_status(config, status)
    try:
        meta = fetch_releaseinfo(config, status)
    except Exception as e:
        logging.error('Failed to fetch_releaseinfo')
        raise e
    download_list = []
    for version in meta['versions']:
        need_update = False
        mv = meta['versions'][version]
        if config.force or version == 'latest':
            need_update = True
        else:
            sv = s.get(version)
            if sv is None or sv.get('subversion') != mv['subversion'] or sv.get('last_updated') is None:
                need_update = True
        if not need_update:
            continue
        version_dir = os.path.join(config.releases_dir, version)
        makedir(version_dir)
        cleardir(version_dir)
        s[version] = {
            'subversion': 'latest' if version == 'latest' else mv['subversion']
        }
        for url in mv['urllist']:
            download_list.append((version, url))
        download_all(config, version_dir, mv['urllist'])
        s[version]['last_updated'] = _get_current_time()


def update_metadata(config, status):
    logging.warning('Metadata mirror function unimplemented.')


def update_packages(config, status):
    logging.warning('Packages mirror function unimplemented.')


def try_update(name, update, config, status):
    try:
        update(config, status)
    except Exception as e:
        logging.error('Failed to update %s' % name)
        status[name]['status'] = 'failed'
        save_status(config, status)
        raise e


def main():
    config = get_config()
    status = get_current_status(config)
    if config.force or status is None:
        status = initialize(config)
    if config.mirror_releases:
        try_update('releases', update_releases, config, status)
    if config.mirror_metadata:
        try_update('metadata', update_metadata, config, status)
    if config.mirror_packages:
        try_update('packages', update_packages, config, status)


if __name__ == '__main__':
    main()
