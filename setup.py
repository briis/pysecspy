"""Package Setup."""

import setuptools

with open("README.md") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pysecspy",
    version="2.0.0",
    author="briis",
    author_email="bjarne@briis.com",
    description="Handles camera feeds and events from SecuritySpy Soft NVR",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/briis/pysecspy",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
    ],
)
