# MWD5
MWD5 custom component for Home Assistant

Features:
- Auto detection of thermostats associated with your account
- Supports MANUAL/BOOST/FROSTPROTECTION/AUTO settings (as presets)

# How to use
- Copy the MWD5 folder in your home assistant `config/custom_components` folder
- Edit `climate.py` and set your username/password
- Add the following in your `configuration.yaml` file:
```yaml
climate:
   platform: mwd5
   # scan_interval default is 30 (internal code protects against server bashing)
   scan_interval: 20
```
