# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

setup(
    name='pnut',
    version='0.1.0',
    description='Customizable network-based universal remote using a TiVo Slide remote.',
    author='Jonathan LaCour',
    author_email='jonathan@cleverdevil.org',
    install_requires=[
        "homeassistant-api",
        "requests",
        "pyatv",
        "aiohttp",
        "hidapi",
        "idna",
        "urllib3",
        "certifi",
        "cffi",
        "six",
        "mutagen",
        "aiohttp_client_cache"
    ],
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(),
)
