from distutils.core import setup

setup(
    name="pysecspy",
    packages=["pysecspy"],
    version="1.1.2",
    license="MIT",
    description="Python Wrapper for SecuritySpy API",
    author="Bjarne Riis",
    author_email="bjarne@briis.com",
    url="https://github.com/briis/pysecspyt",
    keywords=["SecuritySpy", "Surveilance", "Bensoftware", "Home Assistant", "Python"],
    install_requires=[
        "aiohttp",
        "asyncio",
        "xmltodict",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",  # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
