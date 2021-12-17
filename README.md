# Python Wrapper for the SecuritySpy API

![Latest PyPI version](https://img.shields.io/pypi/v/pysecspy) ![Supported Python](https://img.shields.io/pypi/pyversions/pysecspy)

This module communicates with a [SecuritySpy Video Server](https://www.bensoftware.com/securityspy/) and can retrieve and set data for:

* Cameras
* Motion Sensors
* Motion Events

It will require the Webserver component activated on SecuritySpy, and a Username, Password, IP Address and Port number for the Webserver.

See `devicelist.py` and `eventlist.py` for examples on how to use this wrapper. And before doing so, edit each file and insert your SecuritySpy IP Adress, Port Number, Username and Password in the designated variables.

```python
USERNAME = "YOUR_USERNAME"
PASSWORD = "YOUR_PASSWORD"
IPADDRESS = "YOUR_IP_ADDRESS"
PORT = 8000
```

Change all the items in CAPITAL letters to your personal settings.
