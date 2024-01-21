
# PG3 Plugin/Nodeserver for HunterDouglas V3 Shades

[![license](https://img.shields.io/github/license/mashape/apistatus.svg)](https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/LICENSE)

This Poly provides an interface between HunterDouglas window shades and [Polyglot PG3](https://github.com/UniversalDevicesInc/pg3-dist) server.

[This thread](https://forum.universal-devices.com/forum/???-hunterdouglas/) on UDI forums has more details, ask questions there.

 1. This is for HunterDouglas V3 API only, V2 API is out of scope

 2. Best to set your gateway to a determined IP through your router

 3. If you have more than one Gateway (I have two), you will need to determine the primary gateway. This is done using a browser and the address of each of the
    gateways /home.  eg. 10.0.1.150/home then 10.0.1.151/home  The response of the primary will be data while the secondary will complain with {"errMsg":"Multi-Gateway environment - this is not the primary gateway"}.
 
4. You will need to define the following custom parameters:
     - `gatewayip` - defaults to **powerview-g3.local** which seems to not consistently resolve on pg3
                   - use an ip address per #3


