import json
import requests

URL_EVENTS = 'http://{g}/home/events'
gateway = "10.0.1.50"

try:
    if False:
        with open('/Users/stephenjenkins/Projects/txt.json', 'r') as file:
            data = file.read().splitlines()
    else:
        sse = []
        url = URL_EVENTS.format(g=gateway)
        for n in range(10):
            try:
                print(f"GET: {url}")
                s = requests.Session()
                with s.get(url,headers=None, stream=True, timeout=3) as gateway_sse:
                    for val in gateway_sse.iter_lines():
                        print(f"val:{val}")
                        if val:
                            if val == "100HELO":
                                print(f"sse:{val}")
                                continue
                            try:
                                sse.append(json.loads(val))
                            except:
                                print(f"noadd:{val}")
                                pass
            except requests.exceptions.Timeout:
                print(f"see timeout error")
            except requests.exceptions.RequestException as e:
                print(f"sse error: {e}")

        print(sse)
        print("Done.")
except (KeyboardInterrupt, SystemExit):
    print(f"keyboard interupt")



