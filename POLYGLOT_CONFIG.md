
# PG3 Plugin/Nodeserver for HunterDouglas V3 Shades

[![license](https://img.shields.io/github/license/mashape/apistatus.svg)](https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/LICENSE)

This Poly provides an interface between HunterDouglas window shades and [Polyglot PG3](https://github.com/UniversalDevicesInc/pg3-dist) server.

[This thread](https://forum.universal-devices.com/forum/439-hunter-douglas/) on UDI forums has more details, ask questions there.

 1. **IMPORTANT:** This is for HunterDouglas V3 API only, V2 API is out of scope

 2. Best to set your gateway(s) to a determined IP through your router

 3. If you have more than one Gateway You no longer will need to determine the primary gateway. Per #2 You only need to enter the gateways as an array of
    string ip's to as many Hunter Douglas gateways you have. eg ['10.0.1.150', '10.0.1.151', '10.0.1.152']
 
 4. You will need to define the custom parameter **`gatewayip`** 
     - this will default to **powerview-g3.local**  when it is not defined
     - although this works well in a browser it does not resolve consistently on the PGx
     - better to use an ip address per #2 or an array of string ip's as per #3
     
 5. Polling:  Full update of shade and scene datae loaded from the gateway
    - happens at start-up and LongPoll
    - really should just be the extra belt/suspenders as the Push should catch all/most events.  
    - program limited to no faster than once per 3s
    - suggest 60s for LongPoll
    
 6. Pushing: Data is pushed from the gateway and regularly checked
    - updates are checked for every ShortPoll
    - includes Motion-Started, Motion-Stopped, Scene-Activated, Scene-Deactivated, and Shade-Online (pushed infrequently, likely as a keep-alive for the push stream)
    - suggest 5s for ShortPoll
    

