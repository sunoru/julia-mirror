import os
import sys

from mirror_julia import cleardir, remove_empty_dir


def check(packages_dir, package):
    package_dir = os.path.join(packages_dir, package)
    if not os.path.isdir(package_dir):
        return
    registries = os.listdir(package_dir)
    for registry in registries:
        registry_dir = os.path.join(package_dir, registry)
        link = os.path.join(registry_dir, package)
        if os.path.islink(link) and not os.path.isdir(link):
            print('Removing %s (%s)...' % (package, registry))
            os.unlink(link)
            cleardir(registry_dir)
            remove_empty_dir(registry_dir)


def main():
    if len(sys.argv) != 2:
        print('Usage: ./remove_packages path_to_packages')
        exit(1)
    packages_dir = os.path.abspath(sys.argv[1])
    packages = os.listdir(packages_dir)
    for package in packages:
        check(packages_dir, package)


if __name__ == '__main__':
    main()
