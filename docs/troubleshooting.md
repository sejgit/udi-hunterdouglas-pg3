# Troubleshooting

1. Through your router did you reserve an IP for it / them?
Use your router settings for this.
It is beyond the scope here to help how to do this
but a search on your router will help
2. Best place to start is to make sure that your gateway(s) are responding as expected.
Open a browser and type in the following for each gateway

    ```bash
    http://10.0.1.150/home
    #replace 10.0.1.150 with the ip's of your gateways
    ```

    You should see one of the following:

- it worked!!

    ```bash
    {"modApp":"IOS: com.hunterdouglas.powerview v15280","modDate":{"seconds":1707432094,"nanoseconds":781701000},"automations":[{"enabled":true,"min":0,"days":127,"type":10,"bleId":187,"scene_Id":49,"hour":0,"_id":65,"errorShd_Ids":[]},{"enabled":true,"scene_Id":66,"_id":69,"min":30,"bleId":146,"errorShd_Ids":[],"hour":0,"days":127,"type":6},{"days":127,"enabled":true,"hour":0,"min":31,"scene_Id":25,"type":6,"errorShd_Ids":[],"_id":37,"bleId":137},{"_id"
    #It will be much longer than this
    ```
  
  Good news! You have found your primary V3 gateway!

- it also worked, but you need more

    ```bash
    {"errMsg":"Multi-Gateway environment - this is not the primary gateway"}
    ```

    Error 400, you have found (one of) your secondary gateway(s)
    You still want to put this ip into the gatewayip array as primary/secondary
    can move so gatewayip ['10.0.1.151', '10.0.1.150'] in your config is good

- you have likely found a v2 gateway

    ```bash
    {"message":"Not Found","error":{}}
    ```

    Currently I am working on basic functionality for V2

- Your V3 gateway is not set-up with Hunter Douglas

    ```bash
    {"errMsg":"No HomeDoc found"}
    ```

    This is also a V3 gateway hub, and is likely your primary

    The HomeDoc is not something that the user needs to 'have' or edit
     but resides on the gateway if it has been connected with a Hunter Douglas
     account, and a Home created.

    From the HD Docs...

>Note: If the Home does not have a HomeDoc, all /home APIs return statusCode
503/SERVICE_UNAVAILABLE until the Home is correctly configured and a HomeDoc
is successfully retrieved from the Cloud

- HomeDoc is created when you run the PowerView App & create an account
    and then a "Home", this should have been done for you by your installer.

- You need to download the HD PowerView app on your phone

- If you have never run the app before there is a Setup Wizard which will run
out of the box and allow you to create an account and then a home

- If you have run the app before and do not have a home created you can go
into the **More** area in the bottom right, which will come up with a screen you
can pick Set-up Wizard from.

- I would do a restart on the plugin after you complete the HD app process

- If you want to check yourself after you complete the app HomeDoc process then
go back and check your gateway again in the browser

Of Course if none of this worked go to [**the forum**][forum] and ask for help.
Logs are always helpful if you can get them.

[forum]: https://forum.universal-devices.com/forum/439-hunter-douglas/
