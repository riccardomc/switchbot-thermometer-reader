# switchbot-thermometer-reader
A simple script to read and decode switchbot thermometers data


## Setup

There are tons of alternatives but I used
[virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/) to bootstrap
this project for no particular reason:


```shell
mkvirtualenv -p $(which python3) --system-site-packages smarthome
workon smarthome
pip install -r requirements.txt
```

## Run

Here's how you can run it:

```json
python3 switchbot_thermometer.py 
{
  "XX:XX:XX:XX:XX:XX": {
    "alerts": {
      "temperature_alert": 0,
      "humidity_alert": 0
    },
    "raw_values": {
      "battery_value": 100,
      "humidity_value": 65,
      "temperature_scale": "C",
      "temperature_sign": 1,
      "temperature_value": 22.0
    },
    "human_readable": {
      "temperature": "22.0\u00b0C",
      "humidity": "65%",
      "battery": "100%"
    }
  }
```

## What's next

I plan to improve the loop and maybe demonize it.
