'''
Daemon that monitors for TiVo Slider remote commands issued via the
USB RF dongle. Uses the HID system to connect to the dongle and
receive commands. Raw commands are mapped to symbolic text commands
and then dispatched to an instance of pnut.remote.UniversalRemote.

Supports standard actions and "repeating" actions that are sent until
the button is released.
'''

import sys
import threading
import queue
import time
import signal
import logging

import hid

from . import keymap


REMOTE = None
def set_remote(remote):
    '''
    Set the instance of pnut.remote.UniversalRemote to control.
    '''

    global REMOTE
    REMOTE = remote


logging.basicConfig(filename='logs/dispatcher.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)


_exit = threading.Event()
_key_release = threading.Event()


class TiVoRemoteDispatcher(threading.Thread):
    '''
    Dispatcher thread which connects to the HID device and spawns actions
    to be processed by the scheduler.
    '''

    vid = 0x150a
    pid = 0x1203

    def __init__(self, scheduler):
        # attempt to connect to the USB dongle via HID
        try:
            self.dev = hid.device()
            self.dev.open(self.vid, self.pid)
        except IOError as ex:
            logging.info(str(ex))
            sys.exit(1)

        # use the specified scheduler to schedule actions for
        # sequential execution
        self.scheduler = scheduler

        super().__init__(daemon=True)


    def _create_action(self, match, target):
        '''
        Create an action to dispatch with the specified match and target.
        Returns a RepeatingAction or Action depending on the mapped match.
        '''

        if match['repeat']:
            return RepeatingAction(target, accelerates=match.get('accelerates'))
        return Action(target)


    def run(self):
        while not _exit.is_set():
            # read from the USB device (blocking)
            data = self.dev.read(64)

            # once data has been read, clear the key release lock
            _key_release.clear()

            # match the raw button press to a symbolic command
            match = keymap.map(data)

            if match is None:
                logging.info(f'Unmatched button press {str(data)}')
                continue

            # if we receive a key release command, clear the key
            # release lock
            if match['value'] == 'KEY_RELEASE':
                _key_release.set()
                continue

            # create a target callable for the match
            def target(**kwargs):
                REMOTE.press_button(match['value'], **kwargs)

            # create and schedule our action
            action = self._create_action(match, target)
            self.scheduler.schedule(action)

        # clean up HID connection
        self.dev.close()


class ActionScheduler(threading.Thread):
    '''
    Scheduler for executing a queue of actions sequentially.
    '''

    def __init__(self):
        self.queue = queue.Queue()
        super().__init__(daemon=True)

    def schedule(self, action):
        self.queue.put(action)

    def run(self):
        while not _exit.is_set():
            try:
                try:
                    action = self.queue.get(timeout=3600)
                except queue.Empty:
                    REMOTE.remote.keep_alive()
                    continue
                else:
                    action.execute(self)
            except:
                logging.info('Encountered exception in scheduler.')


class Action:
    '''
    An action to be executed by a scheduler.
    '''

    def __init__(self, target=None):
        def _target(*args, **kw):
            try:
                target(*args, **kw)
            except:
                logging.info('Action failed')

        self.target = _target

    def execute(self, scheduler):
        self.target()


class ExitAction(Action):
    '''
    An action specifying that the daemon should terminate.
    '''

    def execute(self, scheduler):
        _exit.set()


class RepeatingAction(Action):
    '''
    An action that repeatedly executes, including support
    for "acceleration."
    '''

    def __init__(self, target=None, accelerates=False):
        self.accelerates = accelerates
        super().__init__(target)

    def execute(self, scheduler):
        step = 0.025
        sleep_duration = 0.25
        while not _key_release.is_set():
            if self.accelerates:
                self.target(step=step)
                step += 0.025
            else:
                self.target()
            time.sleep(sleep_duration)
            sleep_duration = 0.05


def main():
    '''
    Start the daemon, including both a dispatcher and scheduler,
    and begin capturing and executing commands.
    '''

    try:
        scheduler = ActionScheduler()
        scheduler.start()

        dispatcher = TiVoRemoteDispatcher(scheduler)
        dispatcher.start()

        _exit.wait()
    except KeyboardInterrupt:
        _exit.set()
