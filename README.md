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
