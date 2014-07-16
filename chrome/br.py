# -*- coding: UTF-8 -*-
__author__ = 'Administrator'

import httplib

c = httplib.HTTPSConnection("61.219.131.245")
c.request("GET", "/")
response = c.getresponse()
print response.status, response.reason
data = response.read()
print data

# import urllib2
# urllib2.urlopen("https://61.219.131.245", timeout=3)