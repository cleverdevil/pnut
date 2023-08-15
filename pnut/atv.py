'''
Web service to control an Apple TV, including a client for consumers.
'''

import asyncio
import json

from aiohttp import WSMsgType, web
from pyatv.const import Protocol, PowerState

import requests
import pyatv


#
# helper for controlling the Apple TV with this web service
#

class ATVService:
    '''
    Client for controlling an Apple TV via a web service.
    '''

    def __init__(self, host, port):
        self.BASE_URL = f'http://{host}:{port}'

    def launch_app(self, identifier):
        response = requests.get(f'{self.BASE_URL}/launch_app/{identifier}')
        return True if response else False

    def press_button(self, cmd):
        response = requests.get(f'{self.BASE_URL}/remote_control/{cmd}')
        return True if response else False


    def power_toggle(self):
        response = requests.get(f'{self.BASE_URL}/power_toggle')
        return True if response else False


    def keyboard_enter(self, character):
        response = requests.post(
            f'{self.BASE_URL}/keyboard_enter',
            data={'character': character}
        )
        return True if response else False


    def keyboard_clear(self):
        response = requests.get(f'{self.BASE_URL}/keyboard_clear')
        return True if response else False


#
# create the web service for controlling an Apple TV via pyatv
#

ATV_DEVICE = None
def set_device_config(device):
    global ATV_DEVICE
    ATV_DEVICE = device

routes = web.RouteTableDef()

async def connect():
    '''
    Connect to the specified Apple TV.
    '''

    loop = asyncio.get_event_loop()
    confs = await pyatv.scan(loop, identifier=set(
        ATV_DEVICE['identifiers']
    ))

    if not confs:
        print('Device could not be found', file=sys.stderr)
        return

    conf = confs[0]
    for protocol, credentials in ATV_DEVICE['credentials'].items():
        conf.set_credentials(getattr(Protocol, protocol), credentials)

    return await pyatv.connect(conf, loop)


def web_command(method):
    '''
    Decorate a web request handler, providing an active connection
    to the configured Apple TV.
    '''

    async def _handler(request):
        atv = request.app['atv'].get('client')
        if not atv:
            atv = await connect()
            request.app['atv']['client'] = atv
        return await method(request, atv)

    return _handler


@routes.get('/launch_app/{app}')
@web_command
async def launch_app(request, atv):
    '''
    Launch the specified app on the Apple TV, using its bundle id.
    '''

    try:
        await atv.apps.launch_app(request.match_info['app'])
    except Exception as ex:
        return web.Response(status=500, text=f'Command failed: {ex}')
    return web.Response(text='OK')


@routes.get('/remote_control/{command}')
@web_command
async def remote_control(request, atv):
    '''
    Handle a "remote control" request, one of: up, down, left, right,
    channel_up, channel_down, home, home_hold, menu, next, pause, play,
    play_pause, previous, select, skip_forward, skip_backward, stop,
    suspend, top_menu, wakeup.
    '''

    try:
        await getattr(atv.remote_control, request.match_info['command'])()
    except Exception as ex:
        return web.Response(status=500, text=f'Remote control command failed: {ex}')
    return web.Response(text='OK')


@routes.get('/power_toggle')
@web_command
async def power_toggle(request, atv):
    '''
    Toggle power on the Apple TV.
    '''

    try:
        if atv.power.power_state == PowerState.On:
            await atv.power.turn_off()
        else:
            await atv.power.turn_on()
    except:
        del request.app['atv']['client']
        return web.Response(status=500, text='Failed to toggle power')
    return web.Response(text='OK')


@routes.post('/keyboard_enter')
@web_command
async def keyboard_enter(request, atv):
    '''
    Append text via virtual keyboard.
    '''
    try:
        data = await request.post()
        await atv.keyboard.text_append(data['character'])
    except:
        del request.app['atv']['client']
        return web.Response(status=500, text='Failed to send text')
    return web.Response(text='OK')


@routes.get('/keyboard_clear')
@web_command
async def keyboard_clear(request, atv):
    '''
    Clear text in the virtual keyboard.
    '''

    try:
        await atv.keyboard.text_clear()
    except:
        del request.app['atv']['client']
        return web.Response(status=500, text='Failed to clear keyboard')
    return web.Response(text='OK')


async def on_shutdown(app: web.Application) -> None:
    '''
    Call when application is shutting down to clean up connections.
    '''

    atv = app['atv'].get('client')
    if atv:
        atv.close()


def main():
    '''
    Start the web service on the specified host/port.
    '''

    app = web.Application()
    app['atv'] = {}
    app.add_routes(routes)
    app.on_shutdown.append(on_shutdown)
    web.run_app(
        app,
        host=ATV_DEVICE['service']['host'],
        port=int(ATV_DEVICE['service']['port'])
    )


if __name__ == "__main__":
    main()
