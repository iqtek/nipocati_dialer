# coding: utf-8

import logging
import settings

from twisted.internet import error, reactor
from starpy import manager
from callmanager import CallManager
from dialerfactory import DialerFactory

log = logging.getLogger('channeltracker')
actions = {}

if __name__ == "__main__":
    tracker = CallManager(log, actions)
    logging.basicConfig()
    log.setLevel(logging.WARNING)
    manager.log.setLevel(logging.WARNING)
    reactor.callWhenRunning(tracker.main)
    try:
        reactor.listenTCP(settings.dialer_port,
                          DialerFactory(tracker, actions))
        reactor.run()
    except error.CannotListenError:
        print('\n--- Exitting. Unable to listen 0.0.0.0:%s' %
              settings.dialer_port)
