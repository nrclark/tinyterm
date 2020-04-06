#!/usr/bin/env python3

import os
from setuptools import setup
from subprocess import check_output

def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))

    paths = [x for x in paths if '.git' not in x]
    paths = [x for x in paths if '__pycache__' not in x]
    paths = [x for x in paths if '.pyc' not in x]
    return paths

setup(
    name='tinyterm',
    version="1.1",
    description='Minimalistic serial console',
    long_description=open('README.md').read(),
    author='Nick Clark',
    author_email='nicholas.clark@gmail.com',
    url='https://github.com/nrclark/tinyterm',

    packages=['tinyterm'],
    package_data = {'tinyterm': ['tiny_term.py']},
    entry_points = {'console_scripts': ['tinyterm = tinyterm:main']},
    install_requires = ['pyserial'],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
    ],
)
