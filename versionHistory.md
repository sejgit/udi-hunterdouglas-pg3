# Version History

## see hunterdouglas-pg3.py for current version

1.12.5
DONE Some doc clean-up
DONE Some string clean-up
TODO Make more robust to controller faults

1.12.4
DEBUG Gen-2 make a default capability if none exists in JSON

1.12.3
DONE G2 Scene event fix

1.12.2
DONE add shade-offline event handling to error log; currently not passed to ISY
DONE add updating of scene activation status on longPoll as backup to event

1.12.1
DONE environment updates
DONE small refactors

1.12.0
DONE change versioning to align with workflow
DONE update docs: README, versionHistory, logging

0.1.11
DEBUG event rewrite to handle edge cases

0.1.12
DONE update docs: README, versionHistory, logging

0.1.11
DEBUG event rewrite to handle edge cases

0.1.10
DEBUG multi-room scenes sending Discover into exception

past versions:
0.1.9
DONE Fix G3 Events stop working after some period of time

0.1.8
DEBUG branch

0.1.7
DONE rename nodes if changed in PowerView app

0.1.6
DONE parameters based on shade capabilities

0.1.5
DONE format for program setShadePosition
DONE set Shade Position change using False to define which parameters to change
DONE more debug on G2 so it acts as expected

0.1.4
DONE add node_queue & as result need pause updates while in discovery
DONE FIRST TRY G2 tilt feature

0.1.3
DONE node discover rewrite to allow add/remove
DONE add event 'homedoc-updated' currently no actions
DONE limit room label size to 15 as room - shade/scene < 30 for ISY
DONE clean up LOGGING.debug messages
DONE G2 bug fixes

0.1.2
DONE change icons to nicer ones
DONE docs with screenshots & description for udi spotlight
DONE add troubleshooting document
DONE add some support for G2 gateways (no gateway push, only polling)

0.1.1
DONE tap into gateway events, which allows longPoll update to move from 30s to 60s
DONE active scene indications from events
DONE shade motion indicator from events
DONE shade position update from start, stop, online events
DONE remove parameters based on shade capability (primary, secondary, tilt)
DONE update readme & config instructions to highlight G3 scope

0.1.0
DONE handle multiple gateways automatically, picking primary & switching if required
DONE updated configuration instructions as well as link to the forums

0.0.9
DONE fix uom for positions(100) & ids(107)
DONE more notices clean-up
DONE shade naming to include room as scenes
DONE remove status based on shade capability (primary, secondary, tilt)

0.0.8:
DONE handling of notices individually
DONE polling 5s short-poll 30s long-poll
DONE status for programs (positions etc)

0.0.7:
DONE faster status updates when command is given
DONE bug fix
DONE re-order of parameters displayed

0.0.6:
DONE move shade by specific amounts
DONE bug fix scenes not activating

0.0.5:
DONE change shortpoll to 30s
DONE update shades on shortpoll
DONE clear start notice at shortpoll
DONE clean up error proofing in get
DONE fix updating variables with shortpoll
DONE limit device ping to 5s

0.0.4:
DONE discover when new gatewayip is entered
DONE poll status regularly using shortpoll
DONE update required after nodes added to get status
DONE notice when gateway get error
