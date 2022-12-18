"""Platform for sensor integration."""


import datetime
import time
import requests
import json


HOST = "https://ocd5.azurewebsites.net:443"
APIKEY = "f219aab4-9ac0-4343-8422-b72203e2fac9"
USER = "your_username"
PASSWORD = "your_password"

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
        print(msg)
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

            print(
                f"\nG: {gname:<20} : Setpoint: {setpointTemp:<4} : {self.REGMODETXT[regmode]}"
            )

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
                print(f"   {name:<20} : {heatStatus:<12} : {actualTemp:>4}/{setpointTemp:>4} : {self.REGMODETXT[regmode]} : {isOnline}")


if __name__ == "__main__":
   mwd5 = MWD5()
   mwd5.getThermoInfo()