from setuptools import setup
from os import path

def get_changelog():
    if path.isfile('changelog.json'):
        try:
            import simplejson as json

        except ImportError:
            import json

        with open('changelog.json') as fp:
            changelog = json.load(fp)

    else:
        raise RuntimeError("changelog.json not found!")

    return changelog

changelog = get_changelog()

# read the contents of README file
this_dir = path.abspath(path.dirname(__file__))

long_description = None

if path.isfile('README.md'):
    with open(path.join(this_dir, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()

setup(
    name=changelog['name'],
    version=changelog['versions'][-1]['name'],
    packages=changelog['packages'],

    # metadata to display on PyPI
    author=changelog['authorName'],
    author_email=changelog['authorEmail'],
    description=changelog.get('description', ''),
    license=changelog['license'],
    keywords=" ".join([x.replace(' ', '-') for x in changelog['tags']]),
    install_requires=changelog['dependencies'],

    long_description=long_description,
    long_description_content_type=('text/markdown' if long_description is not None else None)
)
