"""Validate mail infrastructure configuration files."""

import configparser
import glob
import sys


def check_toml():
    import toml

    for f in sorted(glob.glob("mail/**/*.toml", recursive=True)):
        try:
            toml.load(f)
            print(f"OK toml {f}")
        except Exception as e:
            print(f"FAIL toml {f}: {e}")
            sys.exit(1)


def check_yaml():
    import yaml

    for f in sorted(glob.glob("mail/**/*.yaml", recursive=True)):
        try:
            yaml.safe_load(open(f))
            print(f"OK yaml {f}")
        except Exception as e:
            print(f"FAIL yaml {f}: {e}")
            sys.exit(1)


def check_ini():
    for f in sorted(glob.glob("mail/haraka/**/*.ini", recursive=True)):
        try:
            configparser.ConfigParser().read(f)
            print(f"OK ini {f}")
        except Exception as e:
            print(f"FAIL ini {f}: {e}")
            sys.exit(1)


if __name__ == "__main__":
    check_toml()
    check_yaml()
    check_ini()
    print("All mail config files valid.")
