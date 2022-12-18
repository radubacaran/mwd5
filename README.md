# MWD5
MWD5 custom component for Home Assistant

Features:
- Auto detection of thermostats associated with your account
- Supports MANUAL/BOOST/FROSTPROTECTION/AUTO settings (as presets)


# Limitations
 - Thermostats must belong to zones/groups
 - Confirmed to be working with thermostats branded:
   - TECE
   - SpeedHeat
 - Energy download not supported (since I don't use that feature)
 - The code polls the server for thermostat status once a minute
   - using a socket implementation would be better
 
 - API endpoint is : "https://ocd5.azurewebsites.net:443"
   - I'm mentioning this because I've seen some other endpoints used with these thermostats
 - ... Probably others
 

# How to use
- Copy the MWD5 folder to your home assistant `custom_components` folder
  - example: /opt/home-assistant/custom_components/mwd5
- Edit `climate.py` and set your username/password
   - I have used the same user/pass used in the SWATT app by OJ Electronics
   - https://play.google.com/store/apps/details?id=com.ojelectronics.owd5.r1099&hl=en&gl=US
   
- Add the following in your `configuration.yaml` file:
```yaml
climate:
   platform: mwd5
   # scan_interval default is 30 (internal code protects against server bashing)
   scan_interval: 20
```
