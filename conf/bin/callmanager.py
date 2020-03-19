#!/usr/bin/python
# coding: utf-8

import os, logging
import pprint
import re
import math
import time
import traceback, sys

from twisted.internet import error, reactor, task, protocol as p
from starpy import manager
from basicproperty import propertied
from datetime import datetime

ami_host = '127.0.0.1'
ami_port = 5038
ami_user = 'AMINIPO'
ami_secret = '3JRoNA2R3O9t'

dialplan = {}

class DialplanMod ( propertied.Propertied ):
#	def __init__(self):
#		self.dialplan = {}

        """Handle messages from custom dialer dialplan"""
        def main( self ):
                """Main operation for the channel-tracking demo"""
    		theManager = manager.AMIFactory(ami_user, ami_secret, None, True)
		theManager.login(ami_host, ami_port).addCallback( self.onAMIConnect )

        def onAMIConnect( self, ami ):
                """Register for AMI events"""
		ami.registerEvent( 'ListDialplan', self.onListDialplan )
		dialplan['outbound-allroutes'] = {}
		dialplan['macro-dialout-trunk'] = {}
		ami.showDialPlan('outbound-allroutes').addCallbacks( self.onActionComplete )
                ami.showDialPlan('macro-dialout-trunk').addCallbacks( self.onActionComplete )
		time.sleep(10)
		return ami.logoff()

	def onActionComplete( self, event ):
		return

	def onListDialplan( self, ami, event ):
		# Case of includecontext
		try:
		    if event["context"] == 'outbound-allroutes':
			if event["includecontext"] != 'outbound-allroutes-custom':
			    dialplan[event["includecontext"]] = {}
			    ami.showDialPlan(event["includecontext"]).addCallbacks( self.onActionComplete )
			return
		except: 
#		    traceback.print_exc(file=sys.stdout)
		    pass

		# Case of regular extension
		try:
		    dialplan[event["context"]]["%s,%s" % (event["extension"], event["priority"])] = "%s(%s)"  % (event["application"], event["appdata"])
		    #pprint.pprint(dialplan)
		except:
#		    traceback.print_exc(file=sys.stdout)
		    pass

if __name__ == "__main__":
    logging.basicConfig()
    tracker = DialplanMod()
    reactor.callWhenRunning( tracker.main )
    reactor.run()
    time.sleep(10)
    pprint.pprint(dialplan)
		
