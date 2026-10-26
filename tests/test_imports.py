import importlib
import pkgutil

import pytest

PACKAGES = ("ai", "core", "entities", "items", "states", "util", "world")


def _all_modules():
    modules = set()
    for package_name in PACKAGES:
        package = importlib.import_module(package_name)
        modules.add(package_name)
        for info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            modules.add(info.name)
    return sorted(modules)


@pytest.mark.parametrize("module_name", _all_modules())
def test_module_imports(module_name):
    assert importlib.import_module(module_name) is not None


def test_entry_points_import():
    assert importlib.import_module("main") is not None
    assert importlib.import_module("server").app is not None
