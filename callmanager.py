# coding: utf-8

import pprint

from settings import *
from starpy import manager

class CallManager( ):
	def __init__(self, log, actions):
		self.actions = actions
		self.log = log

        """Handle messages from custom dialer dialplan"""
        def main( self ):
                """Main operation for the channel-tracking demo"""
    		theManager = manager.AMIFactory(ami_user, ami_secret, None, True) #, self.onAMIConnect )
	        theManager.login(ami_host, ami_port).addCallback( self.onAMIConnect )

        def onAMIConnect( self, ami ):
                """Register for AMI events"""
                self.ami = ami
                self.log.warning( 'onAMIConnect' )
                ami.registerEvent( 'UserEvent', self.onUserEvent )
                ami.registerEvent( 'Hangup', self.onHangup )
                ami.registerEvent( 'AgentConnect', self.onAgentConnect )
                ami.registerEvent( 'AgentCalled', self.onAgentCalled )
                ami.registerEvent( 'AgentComplete', self.onAgentComplete )


# Track Hangup events and get moment when agent channel hangups.
	def onHangup( self, ami, event ):
		self.log.debug( """[Hangup] %s""", event )
		try:
			aid = event["accountcode"]
			a = self.actions[aid]
		except:
			return
		chan = a["echoer"].helper_get_agentchannel(a["AN"], "agent")
		if (chan != event["channel"]):
			return
		status = a["echoer"].helper_get_agentstatus(a["AN"])
		a["echoer"].helper_queue_pause(a["AN"], 1) # Set agent on pause on logoff in dialplan (acident hangup?)
		if (status == "LOGINTRY"):
			a["echoer"].nipo_send_error({"AN": a["AN"]}, "Unable_read_name_or_pass")
			a["echoer"].nipo_send_ack({"ID": a["ID"]}, "Unable_read_name_or_pass")
			a["echoer"].asterisk_del_action(aid)
			print "!!! ActionID deleted (on LOGINTRY) [onNIPOAgentLogoff]: %s" % aid
		if (status == "LOGIN"):
			a["echoer"].asterisk_del_action(aid)
			print "!!! ActionID deleted (on LOGIN) [onNIPOAgentLogoff]: %s" % aid

	def onUserEvent( self, ami, event ):
		if event["userevent"] == "NIPODialState":
			self.onNIPODialState(ami, event)
		if event["userevent"] == "NIPOPowerDialState":
			self.onNIPOPowerDialState(ami, event)
		if event["userevent"] == "NIPOAgentLogin":
			self.onNIPOAgentLogin(ami, event)
		if event["userevent"] == "NIPOAgentFailed":
			self.onNIPOAgentFailed(ami, event)
		if event["userevent"] == "NIPOAgentChannel":
			self.onNIPOAgentChannel(ami, event)
		if event["userevent"] == "NIPOPlayChannel":
			self.onNIPOPlayChannel(ami, event)
		if event["userevent"] == "NIPOPlayAck":
			self.onNIPOPlayAck(ami, event)
		if event["userevent"] == "NIPOListenChannel":
			self.onNIPOListenChannel(ami, event)

# Send from dialplan on Local channel dial failed (preview)
	def onNIPODialState( self, ami, event ):
		self.log.debug( """[NIPODialState] %s""", event )
		aid = event["actionid"]
		if (self.actions[aid]["number_id"] == "-1"): # Only in preview mode (AD command)
			if event["state"] == "busy":
				self.actions[aid]["echoer"].nipo_send_cs_ast(aid, "4")
			if event["state"] == "congestion":
				self.actions[aid]["echoer"].nipo_send_cs_ast(aid, "5")
		if event["state"] == "hangup":
			self.actions[aid]["echoer"].nipo_send_cs_ast(aid, "0")
			self.actions[aid]["echoer"].asterisk_del_action(aid)
		if event["state"] == "answer":
			self.actions[aid]["echoer"].nipo_send_cs_ast(aid, "1")
			self.actions[aid]["channel"] = event["chanremote"]
			

# Send from dialplan on Local channel dial failed (power)
	def onNIPOPowerDialState( self, ami, event ):
		self.log.debug( """[NIPOPowerDialState] %s""", event )
		aid = event["actionid"]
		
		try: # Event can be already triggered on second leg of call
			a = self.actions[aid]
		except:
			return

		cause = "0"
		try:
			cause = event['causecode']
		except:
			return

		sipcause = "0"
		try:
			sipcause = event['sipcode']
		except:
			return

		try: # Event can be triggered after campaign close
			if event["state"] == "abadon":
				a["echoer"].nipo_send_number_back_abadon(aid)
			if event["state"] == "busy":
				a["echoer"].nipo_send_number_back_cause(aid, cause, sipcause)
			if event["state"] == "congestion":
				a["echoer"].nipo_send_number_back_cause(aid, cause, sipcause)
			if event["state"] == "noanswer":
				a["echoer"].nipo_send_number_back_noanswer(aid)
			if event["state"] == "hangup":
				self.actions[aid]["echoer"].asterisk_del_action(aid)
		except:
			pass

#Event: NIPOPlayAck
#Agent: <agent>
#Logintime: <logintime>
#Uniqueid: <uniqueid>
	def onNIPOPlayAck( self, ami, event ):
		"""Handle playback stop and send ACK to NIPO"""
		self.log.debug( """[NIPOPlayAck] %s""", event )
		# Find action name
		aid = event["actionid"]
		try:
			print "!!! ActionID deleted [onNIPOPlayAck]: %s" % aid
			self.actions[aid]["echoer"].nipo_send_ack({"ID": event["nipoid"]})
			self.actions[aid]["echoer"].asterisk_del_action(aid)
		except:
			pass

# Add channel to list of channels used 
	def onNIPOAgentChannel( self, ami, event ):
		self.log.debug( """[NIPOAgentChannel] %s""", event )
		self.helperChannelSet(event, "agent")

	def onNIPOPlayChannel( self, ami, event ):
		self.log.debug( """[NIPOPlayChannel] %s""", event )
		self.helperChannelSet(event, "play")

	def onNIPOListenChannel( self, ami, event ):
		self.log.debug( """[NIPOListenChannel] %s""", event )
		self.helperChannelSet(event, "listen")

# Add channel to list of channels used 
	def helperChannelSet( self, event, chantype ):
		aid = event["actionid"]
		for name, value in self.actions.iteritems():
			try:
	    			if (value["AN"] == event["agent"]):
					print "!!! Tracker put %s as %s channel for %s" % (event["channel"], chantype, value["AN"])
					self.actions[aid]["echoer"].helper_set_agentchannel(value["AN"], event["channel"], chantype)
			except:
				pass

#Event: NIPOAgentFailed
#Agent: <agent>
#Logintime: <logintime>
#Uniqueid: <uniqueid>
	def onNIPOAgentFailed( self, ami, event ):
		"""Handle agent logoff and send ACK to NIPO"""
		self.log.debug( """[NIPOAgentFailed] %s""", event )
		# Find action name
		aid = event["actionid"]
		try:
			agent_name = self.actions[aid]["AN"]
			agent_num = self.actions[aid]["IN"]
		except:
			print "!!! ActionID not in the list [onNIPOAgentFailed]: %s" % aid
			aid = ''

		if aid != '':
			print "!!! ActionID deleted [onNIPOAgentFailed]: %s" % aid
			self.actions[aid]["echoer"].nipo_send_error({"AN": agent_name}, "Agent failed")
			self.actions[aid]["echoer"].nipo_send_ack({"ID": self.actions[aid]["ID"]})
			self.actions[aid]["echoer"].asterisk_del_action(aid)
			# Mark agent as inactive and not count it as active agent (pause, remove from queue?)
			self.actions[aid]["echoer"].helper_queue_pause(agent_name, 1) # Set agent on pause on login error

#Event: NIPOAgentLogin
#Agent: <agent>
#Channel: <channel>
#Uniqueid: <uniqueid>
	def onNIPOAgentLogin( self, ami, event ):
		"""Handle agent login and send ACK to NIPO"""
		# Find actionid and send ACK back to NIPO
		self.log.debug( """[AgentLogin] %s""", event )
		try:
			aid = event["actionid"]
			if self.actions[aid]["ID"] != '-1':
				self.actions[aid]["echoer"].nipo_send_ack({"ID": self.actions[aid]["ID"]})
				self.actions[aid]["echoer"].helper_set_agentstatus(self.actions[aid]["AN"], "LOGIN")
				self.actions[aid]["echoer"].helper_queue_pause(self.actions[aid]["AN"], 0)
		except:
			pass


# Track call conneсtion to Queue member
	def onAgentConnect( self, ami, event ):
		"""Handle agent connect and send CO to NIPO"""
		self.log.debug( """[AgentConnect] %s""", event )
		aid = event["accountcode"]

		try:
			self.actions[aid]["echoer"].nipo_send_agent_connect2(event["membername"], aid);
		except:
			pass
		self.actions[aid]["echoer"].helper_set_agentchannel(self.actions[aid]["AN"], self.actions[aid]["channel"], "agent");

	def onAgentCalled( self, ami, event ):
		"""Handle agent connect and send CO to NIPO"""
		self.log.debug( """[AgentCalled] %s""", event )

	def onAgentComplete( self, ami, event ):
		"""Handle agent connect and send CO to NIPO"""
		self.log.debug( """[AgentComplete] %s""", event )
