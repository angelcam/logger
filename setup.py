#!/usr/bin/env python

import sys

from setuptools import setup, find_packages

if sys.version_info.major > 2:
    install_requires=["aiohttp >= 0.21.6", "pytz"]
else:
    install_requires=["requests-futures >= 0.9.4", "pytz"]

setup(
    name="logger",
    version='1.1.4',
    description="Angelcam Python logging helper",
    keywords="logging loggly syslog",
    author="Angelcam",
    author_email="dev@angelcam.com",
    url="https://bitbucket.org/angelcam/logger/",
    license="MIT",
    packages=find_packages(),
    install_requires=install_requires,
    include_package_data=True,
    platforms='any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers'
    ]
)
