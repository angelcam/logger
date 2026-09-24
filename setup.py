#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="logger",
    version='2.0.0',
    description="Angelcam Python logging helper",
    keywords="logging betterstack loggly syslog",
    author="Angelcam",
    author_email="dev@angelcam.com",
    url="https://bitbucket.org/angelcam/logger/",
    license="MIT",
    packages=find_packages(exclude=["logger.tests"]),
    python_requires=">=3.7",
    install_requires=["aiohttp >= 3.0"],
    include_package_data=True,
    platforms='any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
    ]
)
