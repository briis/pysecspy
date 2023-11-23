# Python Wrapper for the SecuritySpy API

![Latest PyPI version](https://img.shields.io/pypi/v/pysecspy) ![Supported Python](https://img.shields.io/pypi/pyversions/pysecspy)

This module communicates with a [SecuritySpy Video Server](https://www.bensoftware.com/securityspy/) and can retrieve and set data for:

* Cameras
* Motion Sensors
* Motion Events

It will require the Webserver component activated on SecuritySpy, and a Username, Password, IP Address and Port number for the Webserver.

See `devicelist.py` and `eventlist.py` for examples on how to use this wrapper. And before doing so, create a file called `.env` in the same directory as these two files. Add the following lines to `.env`:

```python
USERNAME = YOUR_USERNAME
PASSWORD = YOUR_PASSWORD
IPADDRESS = YOUR_IP_ADDRESS
PORT = 8000
```

Change all the items to the right of the = sign to your personal settings.
