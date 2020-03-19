# coding: utf-8

from twisted.internet import protocol as p
from dialer import Dialer


class DialerFactory(p.Factory):
    def __init__(self, ami_object_reference, actions):
        self.echoers = []
        self.AMIObject = ami_object_reference
        self.actions = actions

    def buildProtocol(self, addr):
        print 'Connection by', addr
        return Dialer(self.AMIObject, self.actions)
