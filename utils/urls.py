"""PowerView gateway URL templates shared across node modules."""

# HunterDouglas PowerView G3 URLs
URL_DEFAULT_GATEWAY = "powerview-g3.local"
URL_GATEWAY = "http://{g}/gateway"
URL_HOME = "http://{g}/home"
URL_ROOMS = "http://{g}/home/rooms"
URL_ROOM = "http://{g}/home/rooms/{id}"
URL_SHADES = "http://{g}/home/shades/{id}"
URL_SHADES_MOTION = "http://{g}/home/shades/{id}/motion"
URL_SHADES_POSITIONS = "http://{g}/home/shades/positions?ids={id}"
URL_SHADES_STOP = "http://{g}/home/shades/stop?ids={id}"
URL_SCENES = "http://{g}/home/scenes/{id}"
URL_SCENES_ACTIVATE = "http://{g}/home/scenes/{id}/activate"
URL_SCENES_ACTIVE = "http://{g}/home/scenes/active"
URL_EVENTS = "http://{g}/home/events?sse=false&raw=true"
URL_EVENTS_SCENES = "http://{g}/home/scenes/events"
URL_EVENTS_SHADES = "http://{g}/home/shades/events"

# HunterDouglas PowerView G2 URLs
# from api file: https://github.com/sejgit/indigo-powerview/blob/master/PowerView%20API.md
URL_G2_HUB = "http://{g}/api/userdata/"
URL_G2_ROOMS = "http://{g}/api/rooms"
URL_G2_ROOM = "http://{g}/api/rooms/{id}"
URL_G2_SHADES = "http://{g}/api/shades"
URL_G2_SHADE = "http://{g}/api/shades/{id}"
URL_G2_SHADE_BATTERY = "http://{g}/api/shades/{id}?updateBatteryLevel=true"
URL_G2_SCENES = "http://{g}/api/scenes"
URL_G2_SCENE = "http://{g}/api/scenes?sceneid={id}"
URL_G2_SCENES_ACTIVATE = "http://{g}/api/scenes?sceneId={id}"

G2_DIVR = 65535
