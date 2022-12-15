"""Platform for sensor integration."""


import datetime
import time
import requests
import json


HOST = "https://ocd5.azurewebsites.net:443"
APIKEY = "f219aab4-9ac0-4343-8422-b72203e2fac9"
USER = "your_usernname"
PASSWORD = your_password"

# Update frequency is secured to no spam the servers
# and then get the account blacklisted.
UPDATE_RATE_SEC = 1 * 60

# When selecting the BOOST preset
# the heating will be ON for this amount of time
# 120 is an offset to deal with some strange TZ handling.
BOOST_TIME = 120 + 30


class MWD5(object):

    REGMODE_AUTO = 1
    REGMODE_CONFORT = 2
    REGMODE_MANUAL = 3
    REGMODE_VACATION = 4
    REGMODE_UNKNOWN1 = 5
    REGMODE_FROSTPROT = 6
    REGMODE_UNKNOWN2 = 7
    REGMODE_BOOST = 8

    REGMODETXT = [
        "ERROR",
        "AUTO",
        "CONFORT",
        "MANUAL",
        "VACATION",
        "UNKNOWN1",
        "FROSTPROT",
        "UNKNOWN2",
        "BOOST",
    ]

    def __init__(self):
        self.sessionId = "B1b7KUifCE-p2jSbz4HqQg"
        self.stateJson = None
        self.list_of_thermos = []
        self.last_update = None
        self.update_budget = 1

        account = self
        account.login()
        account.getData()  # actual data gathering
        pass

    def log(self, msg):
        # print(msg)
        pass

    def logerr(self, msg):
        print(msg)

    def login(self, user=USER, psw=PASSWORD):
        path = "/api/UserProfile/SignIn"

        data = {
            "APIKEY": APIKEY,
            "UserName": user,
            "Password": psw,
            "CustomerId": "99",
            "ClientSWVersion": "1060",
        }
        r = requests.post(HOST + path, data)
        if r.ok:
            res = r.json()
            if res["ErrorCode"] == 0:
                self.log(f"Logged in with username {user}")
                self.sessionId = res["SessionId"]
                print(f"Session ID: {self.sessionId}")
            else:
                self.logerr(f"Failed to login, error code { res['ErrorCode']}")
        else:
            self.logerr("Failed to execute login request")

    def setThermoTemperature(self, thermo_id, thermo_sn, mode, name, temp):

        # calculate boost end time for 30 minutes
        # add two hours because smth is wrong with the time setting on the device
        # it substracts two hours. smth to do with the TZ, most likely.
        td = datetime.timedelta(minutes=BOOST_TIME)
        d = datetime.datetime.today()
        e = d + td
        BoostEndTime = e.strftime("%Y-%m-%dT%H:%M:%S")

        path = "/api/Thermostat/UpdateThermostat"
        params = {"sessionid": self.sessionId}
        data = {
            "APIKEY": APIKEY,
            "ThermostatID": thermo_id,
            "SetThermostat": {
                "AdaptiveMode": True,
                "CustomerId": 99,
                "DaylightSaving": True,
                "DaylightSavingActive": False,
                "Id": int(thermo_id),
                "MaxSetpoint": 2500,
                "MinSetpoint": 500,
                "OpenWindow": True,
                "SensorAppl": 4,
                "SerialNumber": thermo_sn,
                "TimeZone": 7200,
                "ThermostatName": name,
                "Action": 0,
                "ManualModeSetpoint": temp,
                "RegulationMode": mode,
                "BoostEndTime": BoostEndTime,
            },
        }

        r = requests.post(HOST + path, json=data, params=params)
        res = r.json()
        if res["ErrorCode"] != 0:
            self.login()
            r = requests.post(HOST + path, json=data, params=params)
            res = r.json()
            if res["ErrorCode"] != 0:
                self.logerr("Operation failed")
        self.allow_next_update()

    def update_allowed(self):
        now = time.time()
        if (self.last_update == None) or (
            int(now - self.last_update) > UPDATE_RATE_SEC
        ):
            dt = datetime.datetime.now()
            dt = dt.strftime("%Y-%m-%d %H:%M:%S")
            self.logerr(f"{dt} - Update allowed")
            self.last_update = now
            return True
        return False

    def allow_next_update(self):
        self.update_budget = self.update_budget + 1

    def getScheduleSetpoint(self, schedule):
        weekday = datetime.datetime.today().weekday()
        days = schedule["Days"]
        day = days[weekday]
        day_evt = day["Events"]
        sch_setpoint = -1
        for evt in day_evt:
            if evt["Active"] == True:
                # print(f"Clk: {evt['Clock']} : {evt['Temperature']}")
                now = datetime.datetime.now()
                now_mins = now.hour * 60 + now.minute
                h, m, s = evt["Clock"].split(":")
                sch_mins = int(h) * 60 + int(m)
                # print(f"Min now/setpoint: {now_mins}/{sch_mins}")
                if sch_mins >= now_mins:
                    # schedule was not yer reached
                    pass
                else:
                    # schedule time was passed
                    sch_setpoint = float(evt["Temperature"])
                last_setpoint = float(evt["Temperature"])
        if sch_setpoint == -1:
            sch_setpoint = last_setpoint
        return sch_setpoint

    def getData(self, force=False):
        if self.update_budget > 0:
            self.update_budget = self.update_budget - 1
        elif not self.update_allowed():
            return

        path = "/api/Group/GroupContents"
        data = {"sessionid": self.sessionId, "APIKEY": APIKEY}

        r = requests.get(HOST + path, params=data)
        if not r.ok:
            self.login()
            r = requests.get(HOST + path, params=data)
            if not r.ok:
                self.logerr("Failed to execute request ")
                return
        res = r.json()

        if res["ErrorCode"] != 0:
            self.logerr("Failed to get group information")
            return

        self.stateJson = res
        with open("data.json", "w") as outfile:
            json.dump(res, outfile)

    def getThermoInfo(self, data=None):
        if data == None:
            data = self.stateJson
        for group in data["GroupContents"]:
            # group mode may not match thermostat mode
            regmode = int(group["RegulationMode"])
            gname = group["GroupName"]
            if regmode == self.REGMODE_AUTO:
                # setpointTemp, determine from the schedule
                # there is also a thermostat schedule .. but seems like the data is duplicated.
                setpointTemp = self.getScheduleSetpoint(group["Schedule"])
                pass
            elif regmode == self.REGMODE_CONFORT:
                setpointTemp = group["ConfortSetpoint"]
            elif regmode == self.REGMODE_MANUAL or regmode == self.REGMODE_BOOST:
                setpointTemp = group["ManualModeSetpoint"]
            elif regmode == self.REGMODE_VACATION:
                setpointTemp = group["VacationTemperature"]
            elif regmode == self.REGMODE_FROSTPROT:
                setpointTemp = group["FrostProtectionTemperature"]

            setpointTemp = setpointTemp / 100

            # print(
            #     f"\nG: {gname:<20} : Setpoint: {setpointTemp:<4} : {self.REGMODETXT[regmode]}"
            # )

            for thermo in group["Thermostats"]:

                regmode = int(thermo["RegulationMode"])
                actualTemp = thermo["RoomTemperature"]
                actualTemp = actualTemp / 100
                if regmode == self.REGMODE_AUTO:
                    # This will give the temp from the thermo schedule
                    # print(thermo["ThermostatName"])
                    setpointTemp = self.getScheduleSetpoint(thermo["Schedule"])
                    # print(f"Decided {setpointTemp}")
                elif regmode == self.REGMODE_CONFORT:
                    setpointTemp = thermo["ConfortSetpoint"]
                elif regmode == self.REGMODE_MANUAL or regmode == self.REGMODE_BOOST:
                    setpointTemp = thermo["ManualModeSetpoint"]
                elif regmode == self.REGMODE_VACATION:
                    setpointTemp = thermo["VacationTemperature"]
                elif regmode == self.REGMODE_FROSTPROT:
                    setpointTemp = thermo["FrostProtectionTemperature"]

                setpointTemp = setpointTemp / 100
                heatingOn = thermo["Heating"]
                name = thermo["ThermostatName"]

                if heatingOn:
                    heatStatus = "Heating ON"
                else:
                    heatStatus = "Heating OFF"

                online = thermo["Online"]

                if online:
                    isOnline = "ONLINE"
                else:
                    isOnline = "OFFLINE"

                idn = thermo["Id"]
                sn = thermo["SerialNumber"]
                # print(f"   {name:<20} : {heatStatus:<12} : {actualTemp:>4}/{setpointTemp:>4} : {self.REGMODETXT[regmode]} : {isOnline}")

                # This will update the data for all thermostats
                # It's an ugly hack, but the amazing MWD does not allow getting information for a single thermostat
                # OR I didn't discover how

                therm = None
                for e in self.list_of_thermos:
                    if e.name == name:
                        therm = e
                if not therm:
                    therm = MWD5_Hvac()
                    # print(f"Adding {name}")
                    self.list_of_thermos.append(therm)
                therm.set_props(
                    name,
                    actualTemp,
                    setpointTemp,
                    heatingOn,
                    regmode,
                    online,
                    idn,
                    sn,
                    self,
                )

        return self.list_of_thermos


#############################################################################
from abc import abstractmethod
from datetime import timedelta
import functools as ft
import logging
from typing import Any, Dict, List, Optional
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceDataType
from homeassistant.util.temperature import convert as convert_temperature

from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.climate.const import *
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
)
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity


DEFAULT_MAX_TEMP = 25.0
DEFAULT_MIN_TEMP = 5.0


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    t = MWD5()
    thermos = t.getThermoInfo()
    add_entities(thermos)


class MWD5_Hvac(ClimateEntity):
    def set_props(
        self, name, temp_act, temp_setpoint, heatingOn, regmode, online, idn, sn, parent
    ):
        self._name = name
        self._temp_act = temp_act
        self._temp_setpoint = temp_setpoint
        self._isOnline = online
        self._isHeating = heatingOn
        self._regmode = regmode
        self._parent = parent
        self._thermoID = idn
        self._thermoSN = sn

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVAC_MODE_*.
        HVAC_MODE_OFF	The device is turned off.
        HVAC_MODE_HEAT	The device is set to heat to a target temperature.
        HVAC_MODE_AUTO	The device is set to a schedule, learned behavior, AI.
        """
        if not self._isOnline:
            return HVAC_MODE_OFF
        if self._isHeating:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_AUTO

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.
        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported.
        Need to be one of CURRENT_HVAC_*.
        CURRENT_HVAC_OFF	Device is turned off.
        CURRENT_HVAC_HEAT	Device is heating.
        CURRENT_HVAC_IDLE	Device is idle.
        """
        if not self._isOnline:
            return CURRENT_HVAC_OFF
        if self._isHeating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_IDLE

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._temp_act

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._temp_setpoint

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        # for key, value in kwargs.items():
        #     print("{0} = {1}".format(key, value))
        temp = float(kwargs["temperature"])
        self._parent.setThermoTemperature(
            self._thermoID,
            self._thermoSN,
            MWD5.REGMODE_MANUAL,
            self._name,
            int(temp * 100),
        )
        self._temp_setpoint = temp
        print(f"Setting temperature: {int(temp * 100)}")

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.
        Requires SUPPORT_PRESET_MODE.
        """
        return MWD5.REGMODETXT[self._regmode]

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.
        Requires SUPPORT_PRESET_MODE.
        """
        # this does not match the parent class because it can arrive
        # as input from the user
        PRESET_MODES = [
            "AUTO",
            # "CONFORT",
            "MANUAL",
            # "VACATION",
            "FROSTPROT",
            "BOOST",
        ]
        return PRESET_MODES

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # self.preset_mode = preset_mode
        regmode = MWD5.REGMODE_AUTO
        if preset_mode == "AUTO":
            regmode = MWD5.REGMODE_AUTO
        if preset_mode == "CONFORT":
            regmode = MWD5.REGMODE_CONFORT
        if preset_mode == "MANUAL":
            regmode = MWD5.REGMODE_MANUAL
        if preset_mode == "VACATION":
            regmode = MWD5.REGMODE_VACATION
        if preset_mode == "FROSTPROT":
            regmode = MWD5.REGMODE_FROSTPROT
        if preset_mode == "BOOST":
            regmode = MWD5.REGMODE_BOOST
        self._regmode = regmode
        self._parent.setThermoTemperature(
            self._thermoID,
            self._thermoSN,
            regmode,
            self._name,
            int(self._temp_setpoint * 100),
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return convert_temperature(
            DEFAULT_MIN_TEMP, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return convert_temperature(
            DEFAULT_MAX_TEMP, TEMP_CELSIUS, self.temperature_unit
        )

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._parent.getData()
        self._parent.getThermoInfo()
