
# PG3 Plugin/Nodeserver for HunterDouglas PowerView Shades

udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy\
(C) 2024 Stephen Jenkins

[![license](https://img.shields.io/github/license/mashape/apistatus.svg)](https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/LICENSE)

## Intro & Help

This Poly provides an interface between HunterDouglas window shades
and [**Polyglot PG3**][polyglot] server

[**This thread**][forum] on UDI forums has more details, ask questions there\
[Troubleshooting][troubleshoot] available in this document

**IMPORTANT:** There are differences for HunterDouglas G3 API versus G2 API

## Set-up & Configuration

Set your gateway(s) to static IP's through your router

### Custom Parameters

You will need to define the custom parameter **gatewayip**

- this will default to **powerview-g3.local**  when it is not defined
- although this works in a browser & should on PGx, it does not, YMMV
- better to use an ip address per #2 or an array of string ip's as per #3

### Multiple Gateways

Primary gateway will be determined if you have more than one Gateway

- Enter **gatewayip** configuration as an array of string IP's with all Hunter Douglas\
gateways you have\
- example for variable  **gatewayip** ['10.0.1.150', '10.0.1.151', '10.0.1.152']

## Functionality

### Polling: Both PowerView G3 & G2

- happens at start-up and **LongPoll**
- program limited to no faster than once per 3s so as not to flood
- Full update of shade data and scene activation loaded from the gateway

#### PowerView G3 Polling

- this is extra belt/suspenders as the gateway Pushes events
      - additionally battery data
      - suggest 60s for LongPoll

#### PowerView G2 Polling

- this is the only way to get data except battery command
      - you may want to try 30s for **LongPoll** but be wary of flooding PGx

### Event Pushing: PowerView G3 ONLY feature

- Event Data pushed from the gateway and checked by plugin every ShortPoll
- includes **Motion-Started**, **Motion-Stopped**, **Scene-Activated**, and **Scene-Deactivated**
- Additionally **Shade-Online** pushed infrequently & randomly so it seems
- suggest 5s for **ShortPoll**

### Commands: Both PowerView G3 & G2

- Open / Close
- Query
- Jog: PowerView G2 also does battery update, automatic in PowerView G3

#### PowerView G3 Commands

- Stop
- Tilt Open / Close:  Open set at 50% (flat), Close is 100% (down)
  - TODO: could add a parameter for choice of 0% (up) if desired
- Scene Activate:  Activation turns on after movement completion (can take a bit)
- Battery Updates are automatic

#### PowerView G2 Commands

- Tilt Open / Close:  UNKNOWN feature, fired by primary or secondary position?
  - therefore buttons do not do anything in PowerView G2
- Battery Update:  implemented as part of jog as it does both
- Calibrate:  NOT IMPLEMENTED likely should just stay on the PowerView app
- Scene Activate:  Activation result is manually turned on as no event

[polyglot]: https://github.com/UniversalDevicesInc/pg3-dist
[forum]: https://forum.universal-devices.com/forum/439-hunter-douglas/
[troubleshoot]: https://github.com/sejgit/udi-hunterdouglas-pg3/blob/api-v2/docs/troubleshooting.md
