#!/usr/bin/env python3
from pathlib import Path
from setuptools import find_packages, setup

ROOT = Path(__file__).resolve().parent

setup(
    name="agiros-tools",
    version="0.1.0",
    description="AGIROS packaging and build helper CLI",
    author="AGIROS Team",
    packages=find_packages(exclude=("tests", "tests.*")),
    py_modules=[
        "agiros_tools_menu",
        "oob_builder_procedural",
        "oob_tracks_to_sources",
        "yaml_git_downloader_release",
        "git_build_any",
        "rpmbuild_any",
        "clean_generated"
    ],
    include_package_data=True,
    install_requires=[
        "PyQt5>=5.15",
        "pyautogui>=0.9",
        "pyperclip>=1.8",
        "python-dotenv>=1.0.0",
        "setuptools>=65.5"
    ],
    entry_points={
        "console_scripts": [
            "agiros-tools-menu = agiros_tools_menu:main",
            "agiros-oob-build = oob_builder_procedural:main",
            "agiros-tracks-download = oob_tracks_to_sources:main",
            "agiros-release-download = yaml_git_downloader_release:main",
            "agiros-git-build = git_build_any:main",
            "agiros-rpm-build = rpmbuild_any:main",
            "agiros-clean-generated = clean_generated:main"
        ]
    },
    python_requires=">=3.8",
)
