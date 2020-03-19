#!/usr/bin/python
# coding: utf-8

import sys
import math

sys.path.append('/opt/nipodialer/')

from settings import dialer_param_extlen

print """[nipo_agents](!)
ackcall=no
musiconhold=none
\n""";

format = '%0' + "%dd" % dialer_param_extlen
for i in range(0,int(math.pow(10, dialer_param_extlen))):
    print(("[" + format + "](nipo_agents)") % i)
    print(("fullname = " + format + "\n") %i)


