#!/usr/bin/env python3
import argparse
import datetime
import glob
import hashlib
import itertools
import json
import logging
import multiprocessing.pool
import os
import re
import shutil
import socket
import sys
import tempfile
import urllib.request

import git
import toml


VERSION = '1.0.0'

class Config(object):
    DATEFMT = '%Y-%m-%d %H:%M:%S'
    SETTINGS = ['mirror_releases', 'mirror_metadata', 'mirror_packages',
                'registries', 'sync_latest', 'ignore_invalid']
    REMOTE_RELEASEINFO = 'https://github.com/sunoru/julia-mirror/raw/master/data/releaseinfo.json'
    METADATA_URL = 'https://github.com/JuliaLang/METADATA.jl.git'
    CLIENT_URL = 'https://github.com/sunoru/PkgMirrors.jl.git'
    REGISTRIES = {
        'General': 'https://github.com/JuliaRegistries/General.git'
    }
    REGISTRY_NAMES = list(REGISTRIES.keys())

    def __init__(self, root, mirror_releases, mirror_metadata, mirror_packages, registries, sync_latest,
                 max_processes, ignore_invalid, temp_dir, logging_args, mirror_name):
        self.root = os.path.abspath(root)
        self.mirror_releases = mirror_releases
        self.mirror_metadata = mirror_metadata
        self.mirror_packages = mirror_packages
        self.registries = registries
        self.sync_latest = sync_latest
        self.max_processes = max_processes
        self.ignore_invalid = ignore_invalid
        self.logging_args = logging_args
        self.temp_dir = temp_dir
        tempfile.tempdir = temp_dir
        self.packages = {}
        self.mirror_name = mirror_name

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

    @property
    def registries_dir(self):
        return os.path.join(self.root, 'registries')

    @property
    def metadata_dir(self):
        return os.path.join(self.root, 'metadata', 'METADATA.jl')

    @property
    def client_mirror_dir(self):
        return os.path.join(self.root, 'PkgMirrors.jl.git')


class LoggingWriter(object):
    def __init__(self, logger, logging_level):
        self.logger = logger
        self.logging_level = logging_level
    
    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.logging_level, line.rstrip())
    
    def flush(self):
        pass


def set_logging(config):
    logging_level = getattr(logging, config.logging_args[1], None)
    assert isinstance(logging_level, int)
    logging.basicConfig(filename=config.logging_args[0], level=logging_level,
                        format='[%(asctime)s]%(levelname)s:%(message)s', datefmt=Config.DATEFMT)
    # redirect STDOUT and STDERR.
    sys.stdout = LoggingWriter(logging, logging.INFO)
    sys.stderr = LoggingWriter(logging, logging.ERROR)


def makedir(path):
    try:
        os.makedirs(path, mode=0o755)
    except FileExistsError:
        if not os.path.isdir(path):
            raise Exception('%s already exists but is not a directory' % path)


def makelink(src, dst, relative=True):
    if relative:
        src = os.path.relpath(src, os.path.dirname(dst))
    try:
        os.symlink(src, dst)
    except FileExistsError:
        if not os.path.islink(dst):
            raise Exception('%s already exists but is not a link' % dst)


# NOTE: Be careful to use this function!
def cleardir(path):
    for f in os.listdir(path):
        os.remove(os.path.join(path, f))


def download(config, url, path_or_filename=None, logging_file=None, logging_level=logging.WARNING):
    set_logging(config)
    if path_or_filename is None or os.path.isdir(path_or_filename):
        path = os.getcwd() if path_or_filename is None else path_or_filename
        filename = os.path.join(path, url.split('/')[-1])
    else:
        filename = path_or_filename
    logging.info('Downloading %s to %s' % (url, filename))
    i = 0
    err = None
    while i < 3:
        try:
            f = tempfile.NamedTemporaryFile(delete=False)
            f.close()
            urllib.request.urlretrieve(url, f.name)
            if os.path.isfile(filename):
                os.unlink(filename)
            shutil.move(f.name, filename)
            os.chmod(filename, 0o644)
            i = 4
        except urllib.request.HTTPError as e:
            err = e
            i = 3
        except urllib.request.http.client.HTTPException as e:
            err = e
            i += 1
        except urllib.error.URLError as e:
            err = e
            i += 1
        except ConnectionError as e:
            err = e
            i += 1
    if i == 3:
        logging.error('Failed to download %s' % url)
        logging.error(err)
    else:
        logging.info('Downloaded: %s' % url)


def get_config():
    parser = argparse.ArgumentParser(
        description='Build a mirror for the Julia language.')
    parser.add_argument('pathname', type=str,
                        help='path to the root of the mirror')
    parser.add_argument('--no-releases', action='store_true',
                        help='do not mirror Julia releases')
    parser.add_argument('--no-metadata', action='store_true',
                        help='do not mirror METADATA.jl')
    parser.add_argument('--no-general', action='store_true',
                        help='do not mirror General registry (which is the default for registries)')
    parser.add_argument('--no-packages', action='store_true',
                        help='do not mirror packages (and will be automatically set if no registries are to mirrored)')
    parser.add_argument('--add-registry', type=str, dest='registry_names', action='append',
                        choices=Config.REGISTRY_NAMES, default=['General'],
                        help='add a registry specified by name')
    parser.add_argument('--add-custom-registry', type=str, dest='custom_registries',
                        nargs=2, action='append', default=[],
                        help='add a registry specified by a custom URL')
    parser.add_argument('--max-processes', type=int, default=4, metavar='N',
                        help='use up to N processes for downloading (default: 4)')
    parser.add_argument('--sync-latest-packages', action='store_true',
                        help='also mirror packages on master branch')
    parser.add_argument('--ignore-invalid-registry', action='store_true',
                        help='ignore when a registry is not valid')
    parser.add_argument('--temp-dir', type=str, default=None,
                        help='directory for saving temporary files')
    parser.add_argument('--logging-file', type=str, default=None,
                        help='save log to a file instead of to STDOUT')
    parser.add_argument('--logging-level', type=lambda x: str(x).upper(),
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default='WARNING', help='set logging level (default: %(default)s)')
    parser.add_argument('--mirror-name', type=str, default=socket.gethostname(),
                        help='name of this mirror (default: %(default)s)')
    args = parser.parse_args()
    registry_names = set(args.registry_names)
    if args.no_general:
        registry_names.discard('General')
    registries = {name: Config.REGISTRIES[name] for name in registry_names}
    for (name, url) in args.custom_registries:
        if name in registries:
            raise Exception('duplicated name for custom registry: %s' % name)
        registries[name] = url
    if len(registries) == 0:
        args.no_packages = True
    if args.no_packages and args.sync_latest_packages:
        raise Exception('--sync-latest-packages must not be used with --no-packages')
    root = os.path.abspath(args.pathname)
    makedir(root)
    config = Config(
        root, not args.no_releases, not args.no_metadata, not args.no_packages, registries,
        args.sync_latest_packages, args.max_processes, args.ignore_invalid_registry,
        args.temp_dir, (args.logging_file, args.logging_level), args.mirror_name
    )
    set_logging(config)
    logging.info('Running with settings:\n%s' % config)
    return config


def _get_current_time():
    now = datetime.datetime.now()
    return now.strftime(Config.DATEFMT)


def save_status(config, status, name=None, registry_name=None):
    status['last_updated'] = _get_current_time()
    if name is not None:
        status[name]['last_updated'] = status['last_updated']

    if registry_name is not None:
        status['registries']['registries'][registry_name]['last_updated'] = _get_current_time()
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


def initialize(config, status):
    if status is None:
        logging.info('Creating status file and starting building mirror.')
        status = {}
    def set_status(name, value, force=False):
        if force or name not in status:
            status[name] = value
    set_status('name', config.mirror_name, True)
    set_status('created_time', _get_current_time())
    set_status('releases', {'status': 'unavailable'})
    set_status('metadata', {'status': 'unavailable'})
    set_status('registries', {'status': 'unavailable'})
    set_status('packages', {'status': 'unavailable'})
    set_status('mirror_version', VERSION, True)
    set_status('client', {'status': 'unavailable'})
    save_status(config, status)
    return get_current_status(config)


def download_all(config, path, urllist):
    with multiprocessing.pool.Pool(config.max_processes) as pool:
        pool.starmap(download, ((config, url, os.path.join(path, filename))
                                for (filename, url) in urllist))


def fetch_releaseinfo(config, status):
    download(config, Config.REMOTE_RELEASEINFO, config.releaseinfo_file)
    with open(config.releaseinfo_file) as fi:
        meta = json.load(fi)
    return meta


def update_releases(config, status):
    s = status['releases']
    if s.get('created_time') is None:
        s = status['releases'] = {
            'created_time': _get_current_time()
        }
    makedir(config.releases_dir)
    logging.info('Updating mirror for Julia releases.')
    s['status'] = 'synchronizing'
    save_status(config, status, 'releases')
    logging.info('Fetching releaseinfo.json')
    meta = fetch_releaseinfo(config, status)
    for version in meta['versions']:
        need_update = False
        mv = meta['versions'][version]
        version_dir = os.path.join(config.releases_dir, version)
        makedir(version_dir)
        if version == 'latest':
            need_update = True
        else:
            sv = s.get(version)
            if sv is None or sv.get('subversion') != mv['subversion'] or sv.get('last_updated') is None:
                need_update = True
            elif len(os.listdir(version_dir)) != len(mv['urllist']):
                need_update = True
        if not need_update:
            continue
        cleardir(version_dir)
        s[version] = {
            'subversion': 'latest' if version == 'latest' else mv['subversion']
        }
        download_all(config, version_dir, mv['urllist'])
        s[version]['last_updated'] = _get_current_time()
        save_status(config, status, 'releases')
    s['status'] = 'updated'
    save_status(config, status, 'releases')
    logging.info('Releases mirror update completed.')


def clone_from(url, to, mirror=False, shallow=True):
    tempdir = tempfile.mkdtemp()
    if mirror:
        repo = git.Repo.clone_from(url, tempdir, mirror=True)
    elif shallow:
        repo = git.Repo.clone_from(url, tempdir, depth=1, shallow_submodules=True)
    else:
        repo = git.Repo.clone_from(url, tempdir)
    if os.path.exists(to):
        shutil.rmtree(to)
    shutil.move(tempdir, to)
    os.chmod(to, 0o755)
    return repo


def update_repo(repo, mirror=False):
    repo.remote().update()
    if mirror:
        hookfile = os.path.join(repo.git_dir, 'hooks/post-update')
        if not os.path.exists(hookfile):
            shutil.copyfile(hookfile + '.sample', hookfile)
            shutil.copymode(hookfile + '.sample', hookfile)
        os.system(hookfile)
    else:
        repo.remotes.origin.pull()


def update_metadata(config, status):
    s = status['metadata']
    if s.get('created_time') is None:
        s = status['metadata'] = {
            'created_time': _get_current_time()
        }
    makedir(config.metadata_dir)
    logging.info('Updating mirror for METADATA.jl.')
    s['status'] = 'synchronizing'
    save_status(config, status, 'metadata')
    mirror_dir = config.metadata_dir + '.git'
    if not os.path.exists(mirror_dir):
        logging.info('Cloning from upstream.')
        clone_from(Config.METADATA_URL, mirror_dir, True)
    if not os.path.exists(os.path.join(config.metadata_dir, '.git')):
        logging.info('Cloning to a working tree.')
        clone_from(mirror_dir, config.metadata_dir, False, False)
    logging.info('Loading information in METADATA.jl')
    mirror_repo = git.Repo(mirror_dir)
    repo = git.Repo(config.metadata_dir)
    logging.info('Fetching updates from upstream')
    update_repo(mirror_repo, True)
    update_repo(repo, False)
    s['status'] = 'updated'
    save_status(config, status, 'metadata')
    logging.info('Metadata mirror update completed.')


def get_package_info(package_dir):
    package_file = os.path.join(package_dir, 'Package.toml')
    if not os.path.isfile(package_file):
        return None
    with open(package_file) as fi:
        package_info = toml.load(fi)
    return package_info


def get_version_list(package_dir):
    with open(os.path.join(package_dir, 'Versions.toml')) as fi:
        version_list = toml.load(fi)
    return version_list


def remove_empty_dir(dirname):
    if len(os.listdir(dirname)) == 0:
        os.rmdir(dirname)
        parent = os.path.abspath(os.path.join(dirname, os.pardir))
        remove_empty_dir(parent)


def delete_package(config, package_name, registry_name):
    # in registry
    package_dir = os.path.join(config.registries_dir, registry_name, package_name[0].upper(), package_name)
    files = os.listdir(package_dir) if os.path.isdir(package_dir) else []
    if len(files) == 1 and files[0] == 'releases':
        os.unlink(os.path.join(package_dir, 'releases'))
        remove_empty_dir(package_dir)
    # in packages
    package_dir = os.path.join(config.packages_dir, package_name, registry_name)
    package_link = os.path.join(package_dir, package_name)
    if os.path.islink(package_link):
        os.unlink(package_link)
        cleardir(package_dir)
        remove_empty_dir(package_dir)


def update_package_list(config, registry_name, registry_dir):
    packages = config.packages
    for each_dir in glob.glob(os.path.join(registry_dir, '*/*/')):
        package_name = os.path.basename(each_dir[:-1])
        package_info = get_package_info(each_dir)
        if package_info is None:
            delete_package(config, package_name, registry_name)
            continue
        if package_name not in packages:
            packages[package_name] = {}
        packages[package_name][registry_name] = package_info
        packages[package_name][registry_name]['versions'] = get_version_list(each_dir)


def update_registry(config, status, name, url):
    s = status['registries']['registries'][name]
    if s.get('created_time') is None:
        s = status['registries']['registries'][name] = {
            'created_time': _get_current_time(),
        }
    logging.info('Updating mirror for registry: %s.' % name)
    s['status'] = 'synchronizing'
    save_status(config, status, 'metadata')
    registry_dir = os.path.join(config.registries_dir, name)
    mirror_dir = registry_dir + '.git'
    if not os.path.exists(mirror_dir):
        logging.info('Cloning from upstream.')
        clone_from(url, mirror_dir, True)
    if not os.path.exists(os.path.join(registry_dir, '.git')):
        logging.info('Cloning to a working tree.')
        clone_from(mirror_dir, registry_dir, False, False)
    logging.info('Loading information in %s' % name)
    mirror_repo = git.Repo(mirror_dir)
    repo = git.Repo(registry_dir)
    logging.info('Fetching updates from upstream')
    update_repo(mirror_repo, True)
    update_repo(repo, False)
    update_package_list(config, name, registry_dir)
    s['status'] = 'updated'
    save_status(config, status, 'registries', name)
    logging.info('Registry %s mirror update completed.' % name)


def update_registries(config, status):
    s = status['registries']
    if s.get('created_time') is None:
        s = status['registries'] = {
            'created_time': _get_current_time(),
            'registries': {}
        }
    makedir(config.registries_dir)
    logging.info('Updating mirror for registries.')
    s['status'] = 'synchronizing'
    save_status(config, status, 'registries')
    for name in config.registries:
        if name not in s['registries']:
            s['registries'][name] = {}
        try:
            update_registry(config, status, name, config.registries[name])
        except Exception as e:
            logging.error('Failed to update registry: %s' % name)
            s['registries'][name]['status'] = 'failed'
            save_status(config, status, 'registries', name)
            if not config.ignore_invalid:
                raise e
    with open(os.path.join(config.registries_dir, 'list.txt'), 'w') as fo:
        fo.writelines([name + '\n' for name in s['registries']])
    s['status'] = 'updated'
    save_status(config, status, 'registries')
    logging.info('Registries mirror update completed.')


def get_file_hash(filename):
    sha256_hash = hashlib.sha256()
    with open(filename, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b''):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def check_hash(filename):
    hashfile = filename + '.sha256'
    if not os.path.exists(hashfile):
        return False
    hash_1 = get_file_hash(filename)
    with open(hashfile) as fi:
        hash_2 = fi.read().replace('\n', '')
    return hash_1 == hash_2


def update_package(config, status, package_name, registry):
    logging.debug('Updating mirror for package: %s (%s)' % (package_name, registry))
    package = config.packages[package_name][registry]
    version_list = package['versions']
    current_dir = os.path.join(config.packages_dir, package_name, registry)
    makedir(current_dir)
    linkdir = os.path.join(
        config.registries_dir, registry,
        package_name[0].upper(), package_name
    )
    makelink(current_dir, os.path.join(linkdir, 'releases'))
    makelink(linkdir, os.path.join(current_dir, package_name))
    urllist = []
    m = re.match(r'https://github.com/(.*?)/(.*?).git', package['repo'])
    if m is None:
        # TODO: Add support for non-github registries.
        logging.warning('Packages not on github are currently not supported.')
        return
    url_base = 'https://api.github.com/repos/%s/%s/tarball/' % m.groups()
    verlist = []
    for version in version_list:
        sha = version_list[version]['git-tree-sha1']
        filename = '%s-%s.tar.gz' % (package_name, sha)
        url = url_base + sha
        filepath = os.path.join(current_dir, filename)
        if os.path.exists(filepath) and check_hash(filepath):
            continue
        urllist.append((filename, url))
        verlist.append(version)
    if config.sync_latest:
        urllist.append(('%s-latest.tar.gz' % package_name, url_base + 'master'))
    download_all(config, current_dir, urllist)
    for version, (filename, url) in itertools.zip_longest(verlist, urllist):
        filepath = os.path.join(current_dir, filename)
        if not os.path.exists(filepath):
            continue
        sha256_file = filepath + '.sha256'
        sha256_hash = get_file_hash(filepath)
        with open(sha256_file, 'w') as fo:
            fo.write(sha256_hash)
            fo.write('\n')
        if version is None:
            continue
        version_filepath = os.path.join(current_dir, '%s-%s.tar.gz' % (package_name, version))
        version_sha256 = version_filepath + '.sha256'
        if os.path.exists(version_filepath):
            os.unlink(version_filepath)
        if os.path.exists(version_sha256):
            os.unlink(version_sha256)
        makelink(filepath, version_filepath)
        makelink(sha256_file, version_sha256)


def update_packages(config, status):
    s = status['packages']
    if s.get('created_time') is None:
        s = status['packages'] = {
            'created_time': _get_current_time()
        }
    makedir(config.packages_dir)
    logging.info('Updating mirror for packages.')
    s['status'] = 'synchronizing'
    save_status(config, status, 'packages')
    for package_name in config.packages:
        for registry in config.packages[package_name]:
            update_package(config, status, package_name, registry)
    s['status'] = 'updated'
    save_status(config, status, 'packages')
    logging.info('Packages mirror update completed.')


def update_client(config, status):
    s = status['client']
    if s.get('created_time') is None:
        s = status['client'] = {
            'created_time': _get_current_time()
        }
    logging.info('Updating mirror for PkgMirrors.jl.')
    s['status'] = 'synchronizing'
    save_status(config, status, 'client')
    mirror_dir = config.client_mirror_dir
    if not os.path.exists(mirror_dir):
        logging.info('Cloning from upstream.')
        clone_from(Config.CLIENT_URL, mirror_dir, True)
    logging.info('Loading information in PkgMirrors.jl')
    mirror_repo = git.Repo(mirror_dir)
    logging.info('Fetching updates from upstream')
    update_repo(mirror_repo, True)
    s['status'] = 'updated'
    save_status(config, status, 'client')
    logging.info('Client mirror update completed.')


def try_update(name, update, config, status):
    try:
        update(config, status)
    except Exception as e:
        logging.error('Failed to update %s' % name)
        status[name]['status'] = 'failed'
        save_status(config, status, name)
        raise e


def main():
    config = get_config()
    status = get_current_status(config)
    if status is None or status.get('mirror_version') != VERSION:
        status = initialize(config, status)
    try_update('client', update_client, config, status)
    if config.mirror_releases:
        try_update('releases', update_releases, config, status)
    if config.mirror_metadata:
        try_update('metadata', update_metadata, config, status)
    if len(config.registries) > 0:
        try_update('registries', update_registries, config, status)
    if config.mirror_packages:
        try_update('packages', update_packages, config, status)


if __name__ == '__main__':
    main()
