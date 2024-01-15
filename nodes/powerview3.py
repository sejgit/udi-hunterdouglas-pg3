
import base64
import math
import requests
import udi_interface

LOGGER = udi_interface.LOGGER

class PowerViewGen3:

    URL_ROOM_ = 'http://{h}/home/rooms/{id}'
    URL_SHADES_ = 'http://{h}/home/shades/{id}'
    URL_SHADES_MOTION_ = 'http://{h}/home/shades/{id}/motion'
    URL_SHADES_POSITIONS_ = 'http://{h}/home/shades/positions?ids={id}'
    URL_SHADES_STOP_ = 'http://{h}/home/shades/stop?ids={id}'
    URL_SCENES_ = 'http://{h}/home/scenes/{id}'
    URL_SCENES_ACTIVATE_ = 'http://{h}/home/scenes/{id}/activate'

    def __init__(self):
        super().__init__()

    def activateScene(self, hubHostname, sceneId):
        activateSceneUrl = self.URL_SCENES_ACTIVATE_.format(h=hubHostname, id=sceneId)
        self.put(activateSceneUrl)

    def jogShade(self, hubHostname, shadeId):
        shadeUrl = self.URL_SHADES_MOTION_.format(h=hubHostname, id=shadeId)
        body = {
            "motion": "jog"
        }
        self.put(shadeUrl, data=body)

    def stopShade(self, hubHostname, shadeId):
        shadeUrl = self.URL_SHADES_STOP_.format(h=hubHostname, id=shadeId)
        self.put(shadeUrl)

    def room(self, hubHostname, roomId) -> dict:
        roomUrl = self.URL_ROOM_.format(h=hubHostname, id=roomId)

        data = self.get(roomUrl)

        data['name'] = base64.b64decode(data.pop('name')).decode()

        return data

    def setShadePosition(self, hubHostname, shadeId, pos):
        # convert 0-100 values to 0-1.
        if pos.get('primary', '0') in range(0, 101) and \
                pos.get('secondary', '0') in range(0, 101) and \
                pos.get('tilt', '0') in range(0, 101) and \
                pos.get('velocity', '0') in range(0, 101):

            primary = float(pos.get('primary', '0')) / 100.0
            secondary = float(pos.get('secondary', '0')) / 100.0
            tilt = float(pos.get('tilt', '0')) / 100.0
            velocity = float(pos.get('velocity', '0')) / 100.0
            positions = {"primary": primary, "secondary": secondary, "tilt": tilt, "velocity": velocity}

            shade_url = self.URL_SHADES_POSITIONS_.format(h=hubHostname, id=shadeId)
            pos = {'positions': positions}
            self.put(shade_url, pos)
            return True
        else:
            LOGGER.info('Position sent to Set Shade Position must be values from 0 to 100.')
            return False

    def scenes(self, hubHostname):
        scenesURL = self.URL_SCENES_.format(h=hubHostname, id='')

        data = self.get(scenesURL)

        for scene in data:
            name = base64.b64decode(scene.pop('name')).decode()

            if len(scene['roomIds']) == 1:
                room = self.room(hubHostname, scene['roomIds'][0])
                room_name = room['name']
            else:
                room_name = "Multi-Room"
            scene['name'] = '%s - %s' % (room_name, name)

        return data

    def shade(self, hubHostname, shadeId, room=False) -> dict:
        shadeUrl = self.URL_SHADES_.format(h=hubHostname, id=shadeId)

        data = self.get(shadeUrl)
        if data:
            data['shadeId'] = data.pop('id')

            data['name'] = base64.b64decode(data.pop('name')).decode()
            if room and 'roomId' in data:
                room_data = self.room(hubHostname, data['roomId'])
                data['room'] = room_data['name']
            if 'batteryStrength' in data:
                data['batteryLevel'] = data.pop('batteryStrength')
            else:
                data['batteryLevel'] = 'unk'

            if 'positions' in data:
                # Convert positions to integer percentages
                data['positions']['primary'] = self.to_percent(data['positions']['primary'])
                data['positions']['secondary'] = self.to_percent(data['positions']['secondary'])
                data['positions']['tilt'] = self.to_percent(data['positions']['tilt'])
                data['positions']['velocity'] = self.to_percent(data['positions']['velocity'])

        LOGGER.debug("shade V3: Return data={}".format(data))
        return data

    def shadeIds(self, hubHostname) -> list:
        shadesUrl = self.URL_SHADES_.format(h=hubHostname, id='')

        data = self.get(shadesUrl)
        shadeIds = []
        for shade in data:
            shadeIds.append(shade['id'])

        return shadeIds

    def to_percent(self, pos, divr=1.0) -> int:
        LOGGER.debug(f"to_percent: pos={pos}, becomes {math.trunc((float(pos) / divr * 100.0) + 0.5)}")
        return math.trunc((float(pos) / divr * 100.0) + 0.5)

    
    def get(self, url):
        res = None
        try:
            res = requests.get(url, headers={'accept': 'application/json'})
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error {e} fetching {url}")
            if res:
                LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
            return {}

        if res.status_code != requests.codes.ok:
            LOGGER.error(f"Unexpected response fetching {url}: {res.status_code}")
            LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
            return {}

        response = res.json()
        return response

    def put(self, url, data=None):
        res = None
        try:
            if data:
                res = requests.put(url, json=data, headers={'accept': 'application/json'})
            else:
                res = requests.put(url, headers={'accept': 'application/json'})

        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error {e} in put {url} with data {data}:", exc_info=True)
            if res:
                LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
            return False

        if res and res.status_code != requests.codes.ok:
            LOGGER.error('Unexpected response in put %s: %s' % (url, str(res.status_code)))
            LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
            return False

        response = res.json()
        return response
