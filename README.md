# HunterDouglas PowerView Interface

## Universal Devices PG3

[![license](https://img.shields.io/github/license/mashape/apistatus.svg)][license]

This plugin/nodeserver provides an interface between HunterDouglas Shades
and Polyglot V3 server supporting Universal Devices EISY or Polisy controllers

### Get your amazing EISY at [**Universal-Devices**][udi]

## [Screenshots][screenshots]

## Installation

You can install This node server from the PG3 NodeServer Store.\
Read the [**Configuration**][configuration] file for instructions\
[**The Forum**][forum] is a great place to ask questions\
And [**troubleshooting**][troubleshoot] steps are also available,
and will be updated as questions are asked

## Requirements

**IMPORTANT:** There are differences for HunterDouglas G3 API versus G2 API\

See the [**Configuration**][configuration] file for details\

This node server will only run on Polyglot version 3. You will
need to have an EISY/Polisy with PG3 installed to run this node server

### See also [Hunter Douglas PowerView][hd_powerview] for product details

For PowerView G3 hubs, the API can be self hosted by your hub:

* Enable Swagger on your hub: [swagger_enable]
* Get the Swagger results: [swagger_results]
* Disable Swagger on your hub: [swagger_disable]

For PowerView G2 hubs, the API can be found [**here**][G2-API]

## Polling

### longPoll

* currently every 60s

#### controller longPoll

* update all data from Gateway, set event array updating each shade, scene

#### shade longPoll

* G3: logged
* G2: logged MAYBE: could clear ST, Motion flag, this flag is not set at all in G2

#### scene longPoll

* G3: logged
* G2: clear ST, Activated flag

### shortPoll

* currently every 5s

#### controller shortPoll

* process general events, sse heartbeat check
* if no events (60min curently) reset sse cient

#### shade shortPoll

* process shade events

#### scene shortPoll

* process scene events

## Events: controller

### homeDoc-updated

* G3 generated
* signals update of the G3 login to HunterDouglas
* NOTE: just logged
* MAYBE: no additional ideas

### home

* plugin generated
* sequentially update all shades, scenes once per longPoll
* NOTE: each node checks once per shortPoll;updates then removes itself from array
* MAYBE: with event engine this way seemed easy to control updates; over engineered?

## Events: scene

### scene-activated

* G3 generated
* signal movement to scene positions on completion from any source
* NOTE:
  * G3 turn on ST, Activated
  * G2 is turned on when plugin activates (does not get info from remote or app)
* MAYBE: speed up position update by up to 59s if we polled just these shades

### scene-deactivated

* G3 generated
* signal movement away from scene positions immediate from any source
* NOTE:
  * G3 turn off ST, Activated
  * G2 is turned off on next longPoll when plugin activates scene
  * G2 (does not get info from remote or app
* MAYBE: speed up position update by up to 59s if we polled just these shades

## Events: shade

### shade-online

* G3 generated
* kind of a heartbeat which keeps the sse client-server connection alive
* NOTE: checked in controller for any event, this being one of them
* MAYBE: not sure what drives this on the G3 side, so no plans for other actions

### motion-started

* G3 generated
* any shade motion from any source by any command
* NOTE: currenly just set the ST, Motion flag
* MAYBE:
  * Motion timeout: reset or fire jog after timeout
  * if plugin stopped in mid motion, motion-stopped event missed

### motion-stopped

* G3 generated
* shade motion from any source by any command
* NOTE: currenly just clear the ST, Motion flag
* MAYBE: Motion timeout: as above, happened once to me, but rare

[license]: https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/LICENSE
[udi]: https://www.universal-devices.com/hunter-douglas/
[screenshots]: https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/docs/screenshots.md
[configuration]: https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/POLYGLOT_CONFIG.md
[forum]: https://forum.universal-devices.com/forum/439-hunter-douglas/
[troubleshoot]: https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/docs/troubleshooting.md
[hd_powerview]: https://www.hunterdouglas.com/operating-systems/powerview-motorization
[swagger_enable]: http://powerview-g3.local/gateway/swagger?enable=true
[swagger_results]: http://powerview-g3.local:3002
[swagger_disable]: http://powerview-g3.local/gateway/swagger?enable=false
[G2-API]: https://github.com/sejgit/udi-hunterdouglas-pg3/blob/master/docs/PowerViewG2api.md
