'''
A collection of virtual remote controls for a variety of devices, including:

    * Home Assistant fan
    * Home Assistant light
    * Home Assistant generic "scriptable" device
    * Home Assistant "media players"
    * Home Assistant AVR
    * Apple TV
    * Zidoo Android media player

In addition, a "UniversalRemote" which can be used by the pnut agent to control
a variety of sources intelligently based upon active source.
'''

import string
import subprocess
import functools
import logging
import time
import itertools

import homeassistant_api as hass


logging.basicConfig(filename='logs/remote.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)

#
# utilities
#

def chain(*callables):
    '''
    Call a list of collables in sequence.
    '''

    for c in callables:
        c()


def accelerates(func):
    '''
    Decorator for specifying that a remote action accelerates repeated
    execution if the mapped button is held down.
    '''

    func.accelerates = True
    return func


#
# Devices
#

class Device:
    '''
    A generic Home Assistant device.
    '''

    def __init__(self, client, entity_id):
        self.client = client
        self.media_player = self.client.get_domain('media_player')
        self.remote = self.client.get_domain('remote')
        self.entity_id = entity_id

    @property
    def entity(self):
        return self.client.get_entity(
            entity_id=self.entity_id
        )


class ControllableLight:
    '''
    An individual controllable light within Home Assistant.
    '''

    def __init__(self, light, entity):
        self.light = light
        self.entity = entity

    def turn_on(self, brightness=100, transition=3):
        '''
        Set the light to the specified brightness level [0-100], with the
        specified "transition" time in seconds.
        '''

        self.light.turn_on(
            entity_id=self.entity.entity_id,
            brightness_pct=brightness,
            transition=transition
        )

    def turn_off(self, transition=3):
        '''
        Turn off the light with the specified "transition" time in seconds.
        '''

        self.light.turn_off(
            entity_id=self.entity.entity_id,
            transition=transition
        )

    def turn_up(self):
        '''
        Increase brightness by 10%.
        '''

        self.light.turn_on(
            entity_id=self.entity.entity_id,
            brightness_pct=min(self.brightness + 10, 100)
        )

    def turn_down(self):
        '''
        Decrease brightness by 10%.
        '''

        self.light.turn_on(
            entity_id=self.entity.entity_id,
            brightness_pct=max(self.brightness - 10, 0)
        )

    def toggle(self):
        '''
        Toggle the light
        '''

        self.light.toggle(entity_id=self.entity.entity_id)

    @property
    def brightness(self):
        '''
        Get the current brightness level [0-100]
        '''

        return int(round((
            self.entity.state.attributes.get('brightness', 0) / 255) * 100, 0
        ))

    @property
    def is_on(self):
        '''
        Get the current light state (True means "on", False means "off.")
        '''

        return self.brightness > 0


class Lighting:
    '''
    A device that supports controlling any light in Home Assistant from
    a single "source," which makes it easier to configure a UniversalRemote
    without having to enumerate and instantiate every single light in the
    home that you want to control.

    Automatically returns a ControllableLight when accessed as an attribute
    that maps to its entity id within Home Assistant.
    '''

    def __init__(self, client):
        self.client = client
        self.light = self.client.get_domain('light')

    def __getattr__(self, key):
        try:
            entity = self.client.get_entity(entity_id=f'light.{key}')
            return ControllableLight(self.light, entity)
        except homeassistant_api.errors.EndpointNotFoundError:
            return super().__getattr__(key)


class Fan:
    '''
    A Home Assitant fan.
    '''

    def __init__(self, client, entity_id):
        self.client = client
        self.fan = self.client.get_domain('fan')
        self.entity_id = entity_id

    def set_direction(self, direction):
        '''
        Control the direction of the fan (forward or reverse).
        '''

        self.fan.set_direction(
            entity_id=self.entity_id,
            direction=direction
        )

    def set_percentage(self, percentage):
        '''
        Set the fan speed percentage.
        '''

        self.fan.set_percentage(
            entity_id=self.entity_id,
            percentage=percentage
        )

    def turn_on(self):
        '''
        Turn the fan on.
        '''

        self.fan.turn_on(entity_id=self.entity_id)

    def turn_off(self):
        '''
        Turn the fan off.
        '''

        self.fan.turn_off(entity_id=self.entity_id)

    def turn_up(self):
        '''
        Increase the fan speed.
        '''

        self.fan.increase_speed(entity_id=self.entity_id)

    def turn_down(self):
        '''
        Decrease the fan speed.
        '''

        self.fan.decrease_speed(entity_id=self.entity_id)


class HassScriptDevice:
    '''
    A generic Home Assistant device that is controllable entirely
    via Home Assistant scripts. Specify a mapping between a symbolic
    button press and a script to call in Home Assistant.
    '''

    def _cmd(self, cmd, **kwargs):
        script = getattr(self.script, cmd, None)
        if script:
            script.trigger()

    def __init__(self, client, button_map):
        self.script = client.get_domain('script')
        self.button_map = button_map

        for cmd, script_cmd in button_map.items():
            setattr(self, cmd, functools.partialmethod(self._cmd, script_cmd))


class AppleTV(Device):
    '''
    Apple TV device controlled via both Home Assistant and a pnut Apple TV
    web service, which provides significantly better latency than the
    direct Home Assistant remote API.
    '''

    def __init__(self, client, entity_id, service):
        '''
        Initialize an Apple TV device, Provide a Home Assistant client,
        the entity id within Home Assistant, and an instance of the
        pnut ATVService.
        '''

        super().__init__(client, entity_id)
        self.service = service

    def _cmd(self, cmd, **kwargs):
        self.service.press_button(cmd)

    up = functools.partialmethod(_cmd, 'up')
    down = functools.partialmethod(_cmd, 'down')
    left = functools.partialmethod(_cmd, 'left')
    right = functools.partialmethod(_cmd, 'right')
    channel_up = functools.partialmethod(_cmd, 'channel_up')
    channel_down = functools.partialmethod(_cmd, 'channel_down')
    home = functools.partialmethod(_cmd, 'home')
    home_hold = functools.partialmethod(_cmd, 'home_hold')
    menu = functools.partialmethod(_cmd, 'menu')
    next = functools.partialmethod(_cmd, 'next')
    pause = functools.partialmethod(_cmd, 'pause')
    play = functools.partialmethod(_cmd, 'play')
    play_pause = functools.partialmethod(_cmd, 'play_pause')
    previous = functools.partialmethod(_cmd, 'previous')
    select = functools.partialmethod(_cmd, 'select')
    set_position = functools.partialmethod(_cmd, 'set_position')
    skip_forward = functools.partialmethod(_cmd, 'skip_forward')
    skip_backward = functools.partialmethod(_cmd, 'skip_backward')
    stop = functools.partialmethod(_cmd, 'stop')
    suspend = functools.partialmethod(_cmd, 'suspend')
    top_menu = functools.partialmethod(_cmd, 'top_menu')
    wakeup = functools.partialmethod(_cmd, 'wakeup')

    def launch_app(self, identifier):
        self.service.launch_app(identifier)

    def append_text(self, character):
        self.service.keyboard_enter(character)

    def clear_text(self):
        self.service.keyboard_clear()

    def volume_up(self):
        self.remote.send_command(
            entity_id=f'remote.{self.entity_id}',
            command='volume_up'
        )

    def volume_down(self):
        self.remote.send_command(
            entity_id=f'remote.{self.entity_id}',
            command='volume_down'
        )

    def power_toggle(self):
        self.service.power_toggle()


class Zidoo(Device):
    '''
    Zidoo Android media player device. Requires the Zidoo integration for
    Home Assistant to be installed and configured:

    https://github.com/wizmo2/zidoo-player
    '''

    def __init__(self, client, entity_id):
        super().__init__(client, entity_id)
        self.zidoo = self.client.get_domain('zidoo')

    def _cmd(self, cmd, **kwargs):
        self.zidoo.send_key(
            entity_id=self.entity_id,
            key=cmd
        )

    back = functools.partialmethod(_cmd, 'Key.Back')
    cancel = functools.partialmethod(_cmd, 'Key.Cancel')
    home = functools.partialmethod(_cmd, 'Key.Home')
    up = functools.partialmethod(_cmd, 'Key.Up')
    down = functools.partialmethod(_cmd, 'Key.Down')
    left = functools.partialmethod(_cmd, 'Key.Left')
    right = functools.partialmethod(_cmd, 'Key.Right')
    ok = functools.partialmethod(_cmd, 'Key.Ok')
    select = functools.partialmethod(_cmd, 'Key.Select')
    menu = functools.partialmethod(_cmd, 'Key.Menu')
    pop_menu = functools.partialmethod(_cmd, 'Key.PopMenu')
    play = functools.partialmethod(_cmd, 'Key.MediaPlay')
    stop = functools.partialmethod(_cmd, 'Key.MediaStop')
    pause = functools.partialmethod(_cmd, 'Key.MediaPause')
    next = functools.partialmethod(_cmd, 'Key.MediaNext')
    prev = functools.partialmethod(_cmd, 'Key.MediaPrev')
    on = functools.partialmethod(_cmd, 'Key.PowerOn')
    off = functools.partialmethod(_cmd, 'Key.PowerOff')
    backward = functools.partialmethod(_cmd, 'Key.MediaBackward')
    forward = functools.partialmethod(_cmd, 'Key.MediaForward')
    info = functools.partialmethod(_cmd, 'Key.Info')
    page_up = functools.partialmethod(_cmd, 'Key.PageUP')
    page_down = functools.partialmethod(_cmd, 'Key.PageDown')

    @property
    def is_playing(self):
        return self.entity.state.state == 'playing'

    def launch_app(self, app_name):
        self.media_player.select_source(
            entity_id=self.entity_id,
            source=app_name
        )


class Receiver(Device):
    '''
    An AVR (receiver) within Home Assistant. Has multiple source
    devices to control, knows which source is active, and can
    control volume.
    '''

    def __init__(self, client, entity_id, default_source='Apple TV'):
        self.default_source = default_source
        super().__init__(client, entity_id)

    @property
    def active_source(self):
        if self.entity.state.state == 'off':
            return self.default_source

        if self.entity.state.attributes['source'] == 'tv':
            self.active_source = self.default_source

        return self.entity.state.attributes['source']

    @active_source.setter
    def active_source(self, source):
        if self.entity.state.state == 'off':
            self.on()

        self.media_player.select_source(
            entity_id=self.entity_id,
            source=source
        )

    def set_active_source(self, source):
        self.active_source = source

    @property
    def volume_level(self):
        if self.entity.state.state == 'off':
            self.on()
        return self.entity.state.attributes.get('volume_level', 0)

    @accelerates
    def volume_up(self, step=0.025):
        self.media_player.volume_set(
            entity_id=self.entity_id,
            volume_level=min(self.volume_level + step, 1)
        )

    @accelerates
    def volume_down(self, step=0.025):
        self.media_player.volume_set(
            entity_id=self.entity_id,
            volume_level=max(self.volume_level - step, 0)
        )

    def mute(self):
        if self.entity.state.state == 'off':
            self.on()

        if self.volume_level:
            self._prior_level = self.volume_level
            self.media_player.volume_set(entity_id=self.entity_id, volume_level=0)
        else:
            self.media_player.volume_set(
                entity_id=self.entity_id,
                volume_level=getattr(self, '_prior_level', 0)
            )

    def on(self):
        self.media_player.turn_on(entity_id=self.entity_id)

    def off(self):
        self.media_player.turn_off(entity_id=self.entity_id)


class UniversalRemote:
    '''
    A universal remote that has controllable sources and a mapping of every
    symbolic action to actions on devices. Understands the active source
    by reading it from the specified `source_control` device, which is typically
    an AVR (Receiver) device.

    When provided to a pnut agent as the "remote," will receive notifications
    via the `press_button` method and will execute the action based upon the
    active source.
    '''

    def __init__(self, sources={}, source_control=None, source_default=None, button_map={}):
        self.sources = sources
        self.source_control = source_control
        self.source_default = source_default
        self.button_map = button_map

    @property
    def source(self):
        return self.sources.get(
            self.source_control.active_source,
            self.source_default
        )

    def press_button(self, button, **kwargs):
        button = self.button_map.get(button, {}).get(self.source)
        logging.info(f'Press [{str(button)}')

        if button:
            button(**kwargs)
