# Copyright (c) Amber Brown, 2015
# See LICENSE for details.

import os
import sys

from importlib.metadata import version as metadata_version
from unittest import mock

from click.testing import CliRunner
from twisted.trial.unittest import TestCase

from .._project import get_project_name, get_version
from .._shell import cli as towncrier_cli
from .helpers import write


towncrier_cli.name = "towncrier"


class VersionFetchingTests(TestCase):
    def test_str(self):
        """
        A str __version__ will be picked up.
        """
        temp = self.mktemp()
        os.makedirs(os.path.join(temp, "mytestproj"))

        with open(os.path.join(temp, "mytestproj", "__init__.py"), "w") as f:
            f.write("__version__ = '1.2.3'")

        version = get_version(temp, "mytestproj")
        self.assertEqual(version, "1.2.3")

    def test_tuple(self):
        """
        A tuple __version__ will be picked up.
        """
        temp = self.mktemp()
        os.makedirs(os.path.join(temp, "mytestproja"))

        with open(os.path.join(temp, "mytestproja", "__init__.py"), "w") as f:
            f.write("__version__ = (1, 3, 12)")

        version = get_version(temp, "mytestproja")
        self.assertEqual(version, "1.3.12")

    def test_incremental(self):
        """
        An incremental Version __version__  is picked up.
        """
        pkg = "../src"

        with self.assertWarnsRegex(
            DeprecationWarning, "Accessing towncrier.__version__ is deprecated.*"
        ):
            # Previously this triggered towncrier.__version__ but now the first version
            # check is from the package metadata. Let's mock out that part to ensure we
            # can get incremental versions from __version__ still.
            with mock.patch(
                "towncrier._project._get_metadata_version", return_value=None
            ):
                version = get_version(pkg, "towncrier")

            version = get_version(pkg, "towncrier")

        with self.assertWarnsRegex(
            DeprecationWarning, "Accessing towncrier.__version__ is deprecated.*"
        ):
            name = get_project_name(pkg, "towncrier")

        self.assertEqual(metadata_version("towncrier"), version)
        self.assertEqual("towncrier", name)

    def test_version_from_metadata(self):
        """
        A version from package metadata is picked up.
        """
        version = get_version(".", "towncrier")
        self.assertEqual(metadata_version("towncrier"), version)

    def _setup_missing(self):
        """
        Create a minimalistic project with missing metadata in a temporary
        directory.
        """
        tmp_dir = self.mktemp()
        pkg = os.path.join(tmp_dir, "missing")
        os.makedirs(pkg)
        init = os.path.join(tmp_dir, "__init__.py")

        write(init, "# nope\n")

        return tmp_dir

    def test_missing_version(self):
        """
        Missing __version__ string leads to an exception.
        """
        tmp_dir = self._setup_missing()

        with self.assertRaises(Exception) as e:
            # The 'missing' package has no __version__ string.
            get_version(tmp_dir, "missing")

        self.assertEqual(
            ("No __version__ or metadata version info for the 'missing' package.",),
            e.exception.args,
        )

    def test_missing_version_project_name(self):
        """
        Missing __version__ string leads to the package name becoming the
        project name.
        """
        tmp_dir = self._setup_missing()

        self.assertEqual("Missing", get_project_name(tmp_dir, "missing"))

    def test_unknown_type(self):
        """
        A __version__ of unknown type will lead to an exception.
        """
        temp = self.mktemp()
        os.makedirs(os.path.join(temp, "mytestprojb"))

        with open(os.path.join(temp, "mytestprojb", "__init__.py"), "w") as f:
            f.write("__version__ = object()")

        self.assertRaises(Exception, get_version, temp, "mytestprojb")

        self.assertRaises(TypeError, get_project_name, temp, "mytestprojb")

    def test_import_fails(self):
        """
        An exception is raised when getting the version failed due to missing Python package files.
        """
        with self.assertRaises(ModuleNotFoundError):
            get_version(".", "projectname_without_any_files")

    def test_already_installed_import(self):
        """
        An already installed package will be checked before cwd-found packages.
        """
        project_name = "mytestproj_already_installed_import"

        temp = self.mktemp()
        os.makedirs(os.path.join(temp, project_name))

        with open(os.path.join(temp, project_name, "__init__.py"), "w") as f:
            f.write("__version__ = (1, 3, 12)")

        sys_path_temp = self.mktemp()
        os.makedirs(os.path.join(sys_path_temp, project_name))

        with open(os.path.join(sys_path_temp, project_name, "__init__.py"), "w") as f:
            f.write("__version__ = (2, 1, 5)")

        sys.path.insert(0, sys_path_temp)
        self.addCleanup(sys.path.pop, 0)

        version = get_version(temp, project_name)

        self.assertEqual(version, "2.1.5")

    def test_installed_package_found_when_no_source_present(self):
        """
        The version from the installed package is returned when there is no
        package present at the provided source directory.
        """
        project_name = "mytestproj_only_installed"

        sys_path_temp = self.mktemp()
        os.makedirs(os.path.join(sys_path_temp, project_name))

        with open(os.path.join(sys_path_temp, project_name, "__init__.py"), "w") as f:
            f.write("__version__ = (3, 14)")

        sys.path.insert(0, sys_path_temp)
        self.addCleanup(sys.path.pop, 0)

        version = get_version("some non-existent directory", project_name)

        self.assertEqual(version, "3.14")


class InvocationTests(TestCase):
    def test_dash_m(self):
        """
        `python -m towncrier` invokes the main entrypoint.
        """
        runner = CliRunner()
        temp = self.mktemp()
        new_dir = os.path.join(temp, "dashm")
        os.makedirs(new_dir)
        orig_dir = os.getcwd()
        try:
            os.chdir(new_dir)
            with open("pyproject.toml", "w") as f:
                f.write("[tool.towncrier]\n" 'directory = "news"\n')
            os.makedirs("news")
            result = runner.invoke(towncrier_cli, ["--help"])
            self.assertIn("[OPTIONS] COMMAND [ARGS]...", result.stdout)
            self.assertRegex(result.stdout, r".*--help\s+Show this message and exit.")
        finally:
            os.chdir(orig_dir)

    def test_version(self):
        """
        `--version` command line option is available to show the current production version.
        """
        runner = CliRunner()
        result = runner.invoke(towncrier_cli, ["--version"])
        self.assertTrue(result.output.startswith("towncrier, version 2"))
