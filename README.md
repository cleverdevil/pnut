# PNut Network Universal Remote Control

PNut is a Python-based platform for creating a customizable / programmable 
universal remote from a [tivo-slide-pro][1] via its USB RF dongle attached to
any Linux device with a supporting driver. I am using it with a Raspberry Pi 4
running Raspberry Pi OS.

Using this platform does require a basic working knowledge of Python.

There are a few components that are bundled within PNut:

* A web service for controlling an Apple TV via [pyyatv][2]
* A daemon called `pnut-agent` that monitors for button presses and then
  dispatches them to a programmable custom remote that you can create
* A library of devices that can be used together to control a variety of
  devices, including Apple TVs, AVRs, lights, fans, and more.

Much of the capabilities for supported devices comes from [home-assistant][3],
which is required for using PNut.

## Usage

### Creating a Universal Remote

The first step to working with PNut is to create a custom remote control using
the PNut building blocks. Here is an extremely simple example, which we'll place
into `myremote.py`.

```python
from homeassistant_api as hass
from pnut import remote, atv

hass_client = hass.Client(
    '<url to home assistant here>',
    '<token for home assistant here>',
    cache_session=False
)

apple_tv = remote.AppleTV(
    hass_client,
    'living_room',
    atv.ATVService('localhost', '8080')
)

receiver = remote.Receiver(
    hass_client,
    'media_player.living_room_avr',
    default_source='Apple TV'
)

button_map = {
    'PLAY': { apple_tv: apple_tv.play },
    'TIVO': { apple_tv: apple_tv.top_menu },
    'VOLUP': { apple_tv: receiver.volume_up },
    'GUIDE': { 
        apple_tv: lambda: apple_tv.launch_app('com.google.ios.youtubeunplugged')
    }
}

my_remote = remote.UniversalRemote(
    sources={'Apple TV': apple_tv},
    source_control=receiver,
    source_default=apple_tv,
    button_map=button_map
)
```

To start a `pnut-agent` that uses this remote control, we would run:

    `bin/pnut-agent myremote:my_remote`

Note that the `pnut-agent` will require permissions to connect to devices via
the HID, which will necessitate running the agent as root or otherwise providing
permission.

### Controlling Apple TVs

In our example, you'll see that we have an Apple TV that we're controlling.
While Home Assistant does provide a mechanism for controlling Apple TVs, the 
latency is far too high to be usable. Instead, PNut provides a web service that
can be used to control an Apple TV.

To run the Apple TV service, you first need to create a JSON configuration file
about which Apple TV you want to control, credentials, and service
configuration:

```
{
  "name": "<Name of your Apple TV>",
  "identifiers": [
    "<MAC address of your Apple TV>"
  ],
  "credentials": {
    "AirPlay": "<credentials for AirPlay>",
    "Companion": "<credentials for Companion>",
    "RAOP": "<credentials fo RAOP>"
  },
  "service": {
    "host": "localhost",
    "port": "8080"
  }
}
```

To find identifiers and generate credentials, use [pyatv-tools][4].

Once configured, run your Apple TV service:

    `bin/appletv-service atvconfig.json`

Note that your universal remote instance will need to be pointed to the
appropriate host and port.

## Complete Example

Check out the [included example](myremote.py.sample), which is essentially what
I use to control my own home theater, which features an Apple TV, an AVR,
multiple sets of dimmable lights, a controllable fan, and a Zidoo media player.


[1]: <https://tivoidp.tivo.com/tivoCommunitySupport/s/article/TiVo-Slide-Pro-Remote-Product-Info?language=en_US> "TiVo Slide Pro Remote"
[2]: <https://pyatv.dev> "the PyATV Library"
[3]: <https://www.home-assistant.io/> "Home Assistant"
[4]: <https://pyatv.dev/documentation/getting-started/> "PyATV's command line tools"
