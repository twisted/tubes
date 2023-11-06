#/usr/bin/env python3

"""
Report output in real time and then fail if there was any.

workaround for https://github.com/twisted/twistedchecker/issues/89
"""

import os
import sys
f = os.popen(sys.argv[1])
data = f.read(1024)
ever = False
while data:
    sys.stdout.write(data)
    data = f.read(1024)
    ever = True
if ever:
    sys.exit(1)
