#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="logger",
    version='1.0.1',
    description="Angelcam Python logging helper",
    keywords="logging loggly syslog",
    author="Angelcam",
    author_email="dev@angelcam.com",
    url="https://bitbucket.org/angelcam/logger/",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "requests-futures >= 0.9.4"
    ],
    include_package_data=True,
    platforms='any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers'
    ]
)
