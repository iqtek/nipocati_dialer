# coding: utf-8

import __main__ as main
import os
import math
import random
import pprint
import time
import traceback
import base64
import json
from StringIO import StringIO
from copy import deepcopy
import datetime
from twisted.internet import task, protocol as p
from db import DB
from settings import *

agents_total = {}

try:
    from collections import defaultdict
except ImportError:
    from defaultdict import defaultdict

def decode(key, enc):
    dec = []
    enc = base64.urlsafe_b64decode(enc)
    for i in range(len(enc)):
        key_c = key[i % len(key)]
        dec_c = chr((256 + ord(enc[i]) - ord(key_c)) % 256)
        dec.append(dec_c)
    return "".join(dec)


class Dialer(p.Protocol):
    def __init__(self, tracker, actions):
	self.tracker = tracker
	self.actions = actions

    def doUpdateState(self):
	# Get count of calls in 'group show channels'
	def onGroupChannels(events):
		campaign = defaultdict(int)
		for event in events:
			group_chan = event.split()
			try:
				peer = group_chan[1].split('_', 1)[0]
				cpg = group_chan[1].split('_', 1)[1]
				if (group_chan[2] == 'cpg') and (peer == self._peerip):
					campaign[cpg] += 1
			except:
				pass

		for cpg, info in self._campaigns.iteritems():
			self._campaigns[cpg]["stat"]["channels_used"] = campaign[cpg]
			
		self.helper_load_numbers()

	def onCommandDisplay(events):
		return

	bNeedUpdateQueues = False
	for cpg, info in self._campaigns.iteritems():
		if (info["TP"] > 1 ):
			bNeedUpdateQueues = True
			cursor = self.mysql.query("""SELECT count(*)
			    FROM realtime_queue_member
			    WHERE queue_name = '%s_%s'""" % (self._peerip, cpg))
			row = cursor.fetchone()
			if (row[0] == 0):
				self._campaigns[cpg]["stat"]["agents"] = 0
				self._campaigns[cpg]["stat"]["agents_free"] = 0

	if bNeedUpdateQueues:
		cursor = self.mysql.query("""SELECT queue_name,
			    count(*) agents,
			    sum(case when paused = '0' then 1 else 0 end) agents_free 
			FROM realtime_queue_member
			WHERE  queue_name LIKE '%s_%s'
			GROUP BY queue_name""" % (self._peerip, '%'))
		rows = cursor.fetchall()
		for row in rows:
			try:
				cpg = row[0].split('_', 1)[1]
				self._campaigns[cpg]["stat"]["agents"] = row[1]
				self._campaigns[cpg]["stat"]["agents_free"] = row[2]
			except:
				pass
		cursor.close()
		self.tracker.ami.command('group show channels').addCallbacks( onGroupChannels, self.onAMIError )

		try:
			self.tracker.ami.command('group show channels').addCallbacks( onCommandDisplay, self.onAMIError )
			self.tracker.ami.command('agent show online').addCallbacks( onCommandDisplay, self.onAMIError )
			self.tracker.ami.command('queue show').addCallbacks( onCommandDisplay, self.onAMIError )
		except:
			pass
	return

    def connectionMade(self):
	peer = str(self.transport.getPeer()).split(',')
	peer[1] = peer[1].strip()[1:-1]
	peer[2] = peer[2].strip()[0:-1]
	self._peer = peer[1] + ':' + peer[2]
	self._peerip = peer[1]
	self._campaigns =      {}	# Campaigns
	self._agents_devices = {}	# Devices lookup array
	self._agents  =        {}	# Available agents
	self._lc = task.LoopingCall(self.doUpdateState)
	self._lc.start(5)
	self.mysql = DB()
	if self.mysql.host(mysql_host).user(mysql_user).password(mysql_pass).db(mysql_dbname).connect() == None:
		self.nipo_log("ERROR: Database connection failed")
	agents_total[self._peer] = 0

    def connectionLost(self, reason):
	del agents_total[self._peer]
	self.nipo_log('Lost connection from master')
	if self.mysql.connected():
	    self.mysql.query("DELETE FROM `realtime_queue` WHERE `name` LIKE '%s_%s'" % (self._peerip, '%') ).close()
	    self.mysql.query("DELETE FROM `realtime_queue_member` WHERE `queue_name` LIKE '%s_%s'" % (self._peerip, '%') ).close()
	    self.mysql.close()
	
	try:
	    self._lc.stop()
	except:
	    self.nipo_log("WARNING: No queue update running")
	    pass


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! #

    def get_campaign_queue(self, cn):
        return self._campaigns[cn]["queue"]

    def get_agent_cpg(self, agent):
	return self._capaigns[self._agents[agent]["CN"]]

    def asterisk_add_action(self, salt, action):
	aid = salt + '.' + str(time.time());
	self.nipo_log("Action %s generated" % aid)
	self.actions[aid] = action
	return aid

    def asterisk_del_action(self, aid):
	self.nipo_log("Action %s released" % aid)
	try:
	    del self.actions[aid]
	except:
	    pass
	return aid

# Данная функция запускается каждый раз при получении номеров от NIPO или появлении новых агентов (режим predictive, power)
    def asterisk_send_numbers(self):
	for name, cpg in self._campaigns.iteritems():
		for number_id, num in cpg["numbers"].iteritems():
			if (num["status"] == "NEW"):
				num["status"] = "SENT"
				if force_number == True:
					num["TN"] = force_number_value
				action = {
					"Channel": "Local/" + num["TN"] + "@" + outbound_power_context + "/n",
					"Context": queue_context,
					"Exten": "s",
					"Timeout": cpg["WT"], 
					"CalleridNum": num["CI"]}

				action_record = {"action": "dial",
					"campaign": name, 
					"echoer": self, 
					"number_id": number_id, 
					"TP": cpg["TP"], 
					"AN": "-1"}
				cpg["TC"] += 1
				aid = self.asterisk_add_action(num["TI"], action_record)
				action_variables = {
					"__ACTIONID": aid,
					"__CAMPAIGN": name,
					"__NUMBERID": num["TI"],
					"__NUMBER": num["TN"],
					"__NIPOQUEUE": cpg["queue"]
					}
				self.nipo_log("[Asterisk] Originate <--- Channel: %s" % action["Channel"])
				self.nipo_log("[Asterisk] Originate <--- Exten:   %s" % action["Exten"])
				try:
					action_variables["__INTERVIEW"] = num["II"] # Optional field
					self.nipo_log("[Asterisk] Interview ID: %s" % action_variables["__INTERVIEW"])
				except:
					pass
				self.tracker.ami.originate(action["Channel"], action["Context"], action["Exten"], "1", action["Timeout"], action["CalleridNum"], aid, None, None, action_variables, True, aid).addCallbacks( self.onAMIResult, self.onAMIError )

# Производим прямой набор номера (режим preview)
    def asterisk_send_number_direct(self, data):
	agent_phone = self._agents_devices[data["AN"]]["extension"]
	cpg = self._campaigns[self._agents[data["AN"]]["CN"]]
	if force_number == True:
		data["TN"] = force_number_value
	action = {
		"Channel": "Local/" + agent_phone + "@" + agent_context + "/n",
		"Context": outbound_context,
		"Exten": data["TN"],
		"Timeout": cpg["WT"],
		"CalleridNum": data["TN"]
		} # Instead of CI to see on agent phone dialed cid
	action_record = {"action": "dial", 
		"campaign": self._agents[data["AN"]]["CN"], 
		"echoer": self, 
		"number_id": '-1', 
		"TP": cpg["TP"], 
		"AN": data["AN"]
		}
	aid = self.asterisk_add_action(data["TN"], action_record)
	cpg["TC"] += 1
	action_variables = {
		"__AGENTCID": agent_phone, 
		"__AGENTNAME": data["AN"], 
		"__AGENTNAMESHORT": data["AN"][-1*dialer_param_extlen:],
		"__ACTIONID": aid,
		"__CAMPAIGN": cpg["CN"],
		"__NIPOIP": self._peerip
		}
	try:
		action_variables["__INTERVIEW"] = self._agents[data["AN"]]['interview_id']
		self.nipo_log("[Asterisk] Interview ID: %s" % action_variables["__INTERVIEW"])
	except:
		pass

	self.nipo_log("[Asterisk] ===== Preview ===== ")
	self.nipo_log("[Asterisk] Originate <--- Channel: %s" % action["Channel"])
	self.nipo_log("[Asterisk] Originate <--- Exten:   %s" % action["Exten"])
	self.tracker.ami.originate(action["Channel"], action["Context"], action["Exten"], "1", action["Timeout"], action["CalleridNum"], None, None, None, action_variables, True, aid).addCallbacks( self.onAMIResult, self.onAMIError )

    def dataReceived(self, data):
	functions = {
		'OC': self.nipo_open_campaign,
		'AL': self.nipo_agent_logon,
		'AA': self.nipo_agent_available,
		'SN': self.nipo_receive_number,
		'AF': self.nipo_agent_call_finished,
		'AO': self.nipo_agent_logoff,
		'CC': self.nipo_close_campaign,
		'OD': self.nipo_add_dialer,
		'AU': self.nipo_agent_unavailable,
		'RC': self.nipo_agent_result_code,
		'AD': self.nipo_agent_dial_number,
		'AH': self.nipo_agent_hangup,
		'AX': self.nipo_agent_play_file,
		'AS': self.nipo_agent_stop_playfile,
		'AP': self.nipo_agent_play_digits,
		'AR': self.nipo_agent_start_record_data,
		'AZ': self.nipo_agent_stop_record_data,
		'RP': self.nipo_agent_record_file_path,
		'SI': self.nipo_agent_set_interview_id,
		'AW': self.nipo_agent_connect_watch,
		'WE': self.nipo_agent_end_watch,
		'RL': self.nipo_agent_remote_listen,
		'EL': self.nipo_agent_end_remote_listen,
		'KA': self.nipo_agent_kill,
		'NM': self.nipo_new_master,
		'EI': self.nipo_agent_end_interview,
	}

	data = data.decode('utf-16').encode('utf-8').split('\r')
	for m in data:
		if m == '':
			continue
		self.nipo_log('<-- ' + m)
		message = {}
		message_list = m.split('!')
		message["CMD"] = message_list[0]
		for s in message_list:
			message[s[:2]] = s[2:]
		x = 'Exist'
		try:
			func = functions[message["CMD"]]
		except KeyError:
			x = None

		if self.mysql.connected() == False:
			self.nipo_send_error(message, "Database not connected")
			x = None

		if x is not None:
			func = functions[message["CMD"]]
			if (func(message) > 0):
				self.nipo_send_ack(message)
	return


########################################
# Helper functions for data exchange
    def helper_load_numbers (self ):
	nums = {}
	nums_total = 0
	for name, cpg in self._campaigns.iteritems():
		if (cpg["TP"] == 2 or cpg["CC"] == 0):
			rate = 1.0
		else:
			rate = (cpg["TC"] - cpg["stat"]['channels_used'])/float(cpg["CC"])
		real_rate = rate
		if rate > 5.0:
			real_rate = rate
			rate = 5.0

		if (cpg["CC"] == 0):
			rate_abadon = 0
		else:
			rate_abadon = round( (cpg["AC"]*1000)/float(cpg["CC"]) )
		if rate_abadon > cpg.get('AB', 0):
			rate = 1.0

		if (cpg["stat"]['agents_free'] == 0):
			numbers = 0
		else:
			numbers_float = int(cpg.get("stat", {}).get('agents_free', 0))*(rate-1.0)/2 - int(cpg["stat"]['channels_used']) + int(cpg["stat"]['agents'])
			numbers = math.floor(numbers_float)
			random.seed()
			
			if (random.randint(0,100) < int(numbers_float%1)):
				numbers = numbers + 1
			
		if (numbers > 0):
			nums[name] = numbers
			nums_total = nums_total + numbers
		if (cpg["stat"]['agents'] > 0):
			self.nipo_log("CPG:%s [Type: %d] [Lifetime Calls: %d] [Connected calls: %d] [Abadoned calls: %d] " % ( name, cpg["TP"], cpg["TC"], cpg["CC"], cpg["AC"] ))
			self.nipo_log("CPG:%s [Rate: %f] [Abadon Rate: %d/%d] [Channels Used: %d] [Agents Online: %d] [Agents Available: %d] " % ( name, rate, rate_abadon, cpg.get('AB', 0), cpg["stat"]['channels_used'], cpg["stat"]['agents'], cpg["stat"]['agents_free'] ))
			self.nipo_log("CPG:%s [Total: %d] [Numbers: %d]" % ( name, nums_total, numbers ))

	if (nums_total > dialer_call_limits):
	    rate = dialer_call_limits / (nums_total * 1.0)
	else:
	    rate = 1.0

	for name, n in nums.iteritems():
	    self.nipo_log("GENERAL [Rate:%f] [Numbers:%d/%d]" % (rate, int(n), int(math.floor(n*rate))))
	    self.nipo_get_phone_numbers( name , int(math.floor(n*rate)) )
	    self.nipo_log("+++ load numbers %d" % int(math.floor(n*rate)) )
	return

    def helper_unload_numbers (self, cpg_name ):
	if (self._campaigns[cpg_name]["TP"] > 1):
		if len(self._campaigns[cpg_name]['numbers']) > 0:
			self.nipo_log("-- unload numbers")
			for key in self._campaigns[cpg_name]['numbers'].iterkeys():
				self.nipo_send_number_back( cpg_name, key, 0 )
		del self._campaigns[cpg_name]['numbers']
	return

########################################
# Functions for send messages to NIPO
# AC!IDn!ER”Error Text”
    def nipo_send_ack(self, data, error=''):
        try:
            i = data["ID"]
        except KeyError:
            return

        if error == '':
            self.send_data("AC!ID%s" % i)
        else:
            self.send_data('AC!ID%s!ER"%s' % (i, error))
        return
# Get number (mode: power, predictive)
# GN!CNname!DL”Dialer”!NRn
    def nipo_get_phone_numbers (self, campaign, numbers ):
	self.nipo_log("call: nipo_get_phone_numbers(" + campaign + "," + str(numbers) + ")")
	self.send_data('GN!CN' + campaign + '!DL"' + default_dialer + '"!NR' + str(numbers))
	return

# Agent Connect (mode: power, predictive)
# Connect a conversation to this agent
# CO!ANname!TIn
# !TI - Telephone number ID
    def nipo_send_agent_connect (self, interface, actionid ):
	for key, value in self._agents_devices.iteritems():
		if (value["interface"] == interface):
			nipo_send_agent_connect2(key, actionid)
			return
	return

    def nipo_send_agent_connect2 (self, agent, actionid ):
	cpg = self._campaigns[self._agents[agent]["CN"]]
	cpg["CC"] += 1
	self.nipo_log("Call to %s answered. Connection rate: %.2f" % (agent, float(cpg["CC"])/cpg["TC"] * 100))
			
	if (cpg["TP"] > 1):
		self.mysql.query("UPDATE `realtime_queue_member` SET `paused`='1' WHERE `queue_name`='%s' AND `interface`='%s'" % (cpg["queue"],  self._agents_devices[agent]["interface"]))
		number_id = self.actions[actionid]["number_id"]
		self.actions[actionid]["AN"] = agent
		self._agents[agent]['number_id'] = number_id
		self._campaigns[cpg["CN"]]['numbers'][number_id]["status"] = "CONNECT"
		self.send_data('CO!AN' + agent + '!TI' + number_id)
		self.send_data('CS!AN' + agent + '!ST1')
		try:
			self._agents[agent]['interview_id'] = self._campaigns[cpg["CN"]]['numbers'][number_id]["II"]
		except:
			pass
	return


    def nipo_send_cs_ast (self, actionid, reason):
	try:
		if (self.actions[actionid]["AN"] != "-1") :
			self.send_data('CS!AN' + self.actions[actionid]["AN"] + '!ST' + reason)
	except:
		pass
	return

#0 Number not used
#1 No answer
    #2 Answer device
    #3 Busy
    #4 Infotone
    #5 Wrong Number
#28 Abandoned Call
# https://tools.ietf.org/html/rfc3398
# Number dialed, but phone syste report busy or congestion (need to map reason)
    def nipo_send_number_back_cause (self, actionid, cause, sipcause):
	self.nipo_log("===> [NIPO] Send number back (aid: %s, Q.931: %s, SIP: %s)" % (actionid, cause, sipcause) )
	campaign = self.actions[actionid]["campaign"]
	number_id = self.actions[actionid]["number_id"]
	self.nipo_log("===> [NIPO] Send number back (aid: %s, number_id: %s)" % (actionid, number_id) )

	# Convert reason
	reason = 4
	if cause == "17": # busy
		reason = 3
	if cause == "1": # incorrect number
		reason = 5
	if cause == "28": # incorrect number
		reason = 5
	if cause == "22": # incorrect number
		reason = 5
	if cause == "0": # Congestion (circuits busy)
		reason = 3 # Todo: use one more time
		self._campaigns[campaign]["TC"] -= 1

	# Remove number from buffer
	self.nipo_log("ActionID deleted [onNB]: %s" % actionid)
	self.asterisk_del_action(actionid)
	if (number_id != '-1'):
		self.nipo_send_number_back(campaign, number_id, reason)


# Number dialed, but phone syste report no answer
    def nipo_send_number_back_noanswer (self, actionid):
	self.nipo_log("===> [NIPO] Send number back (aid: %s, reason: %s)" % (actionid, ast_reason) )
	campaign = self.actions[actionid]["campaign"]
	number_id = self.actions[actionid]["number_id"]
	self.nipo_log("===> [NIPO] Send number back (aid: %s, number_id: %s)" % (actionid, number_id) )

	# Remove number from buffer
	self.nipo_log("ActionID deleted [onNB]: %s" % actionid)
	self.asterisk_del_action(actionid)
	if (number_id != '-1'):
		self.nipo_send_number_back(campaign, number_id, 1)

# Number dialed, answered, but abadoned
    def nipo_send_number_back_abadon (self, actionid):
	self.nipo_log("===> [NIPO] Send abadon number back (aid: %s)" % (actionid) )
	campaign = self.actions[actionid]["campaign"]
	number_id = self.actions[actionid]["number_id"]
	self.nipo_log("===> [NIPO] Send number back (aid: %s, number_id: %s)" % (actionid, number_id) )

	self._campaigns[campaign]["AC"] += 1
	self.nipo_log("-- Campaign %s AC increment to %d" % (campaign, self._campaigns[campaign]["AC"]))

	# Remove number from buffer
	self.nipo_log("ActionID deleted [onNB]: %s" % actionid)
	self.asterisk_del_action(actionid)
	if (number_id != '-1'):
		self.nipo_send_number_back(campaign, number_id, 28)

# NB!CNname!TIn!CSn
#!TI Telephone number ID
#!CS Reason for sending back
#Default reasons
#	0	Number not used
#	1	No answer
#	2	Answer device
#	3	Busy
#	4	Infotone
#	5	Wrong Number
#	28	Abandoned Call
#Other reasons can be configured, see setting ‘DialerResponse’
    def nipo_send_number_back (self, campaign, number_id, reason):
	if (number_id != '-1'):
		if self._campaigns[campaign]['numbers'][number_id]["status"] != "CONNECT":
			self.nipo_log("-- number unload %s" % number_id)
			self.send_data('NB!CN' + campaign + '!TI' + number_id + '!CS' + str(reason))
		del self._campaigns[campaign]['numbers'][number_id]
	return


    def nipo_complete_number (self, campaign, number_id):
	if (number_id != '-1'):
		del self._campaigns[campaign]['numbers'][number_id]
		self.nipo_log("-- number unload %s" % number_id)
	return

# Error
# ER!CNname!ANname!DL”name”!ER”Error Text”
# !CN - may be missing when the campaign is not important
# !AN - may be missing when the error is not agent related
# !DL - Dialer name (optional)
# When the message specifies an agent and the agent is waiting for a new telephone number
#     the agent will be released with an error.
# When the message specifies a campaign and a dialer and the campaign is
# being opened the campaign is assumed not to be opened on the specified
# dialer.
    def nipo_send_error(self, data, error):
        e = ""
        try:
            e = e + '!CN' + data["CN"]
        except KeyError:
            pass
        try:
            e = e + '!AN' + data["AN"]
        except KeyError:
            pass
        e = '%s!DL"%s"' % (e, default_dialer)
        self.send_data('ER' + e + '!ER"' + error + '"')
        return
# ND!DL”Dailer”

    def nipo_send_new_dialer(self):
        self.send_data('ND!DL"' + default_dialer + '"')
        return
# CD!DL”Dailer”

    def nipo_send_close_dialer(self):
        self.send_data('CD!DL"' + default_dialer + '"')
        return
# Agent Record File Path
# Set the file path for the file being recorded when it is not recorded
# in the default location (or there is no default location)
# RP!ANname!FN”filepath”
# !FN pathname with which the Master can reach the file

    def nipo_agent_record_file_path(self, data):
        self._agents[data["AN"]]["filepath"] = data["FN"]
        self.nipo_log("NIPO set filepath to %s for %s" %
                      (data["FN"], data["AN"]))
        return
########################################
# Functions for hangle incoming messages
# OC!CNname!IDn!TPn!ABn!WTn!DVdev!RG”reg”!PA”par”!DL”Dialers”
#!TP	Dial type
#	0 Inbound
#	1 Preview
#	2 Power
#	3 Predictive
#!AB	Abandoned call rate (per 1000)
#!WT	Delay time before declaring a no answer (seconds)
#!DV	Device used for dialing (optional)
#!RG	Dialer registration (optional)
#!PA	Campaign parameters from survey table (optional)
#!DL	Comma separated list of dialers on which the campaign should run(optional)
    def nipo_open_campaign (self, data ):
	self._campaigns[data["CN"]] = {}
	self._campaigns[data["CN"]]["numbers"] = {}
	self._campaigns[data["CN"]]["agents"] = {}
	self._campaigns[data["CN"]]["second"] = []
	self._campaigns[data["CN"]]["stat"] = {}
	self._campaigns[data["CN"]]["stat"]["agents"] = 0
	self._campaigns[data["CN"]]["stat"]["agents_free"] = 0
	self._campaigns[data["CN"]]["stat"]["channels_used"] = 0
	
	self._campaigns[data["CN"]]["TP"] = int(data["TP"])
	self._campaigns[data["CN"]]["AB"] = int(data["AB"])
	self._campaigns[data["CN"]]["WT"] = int(data["WT"])
	self._campaigns[data["CN"]]["CN"] = data["CN"]
	self._campaigns[data["CN"]]["TC"] = 0   # Total calls
	self._campaigns[data["CN"]]["AC"] = 0   # Abadoned calls
	self._campaigns[data["CN"]]["CC"] = 0   # Completed calls

	if (self._campaigns[data["CN"]]["TP"] > 1):
		q = "%s_%s" % (self._peerip, data["CN"])
		try:
			self.mysql.query("DELETE FROM `realtime_queue` WHERE `name`='%s'" % q).close()
			self.mysql.query("DELETE FROM `realtime_queue_member` WHERE `queue_name`='%s'" % q).close()
			self.mysql.query("INSERT INTO `realtime_queue` SET `name`='%s', `strategy`='rrmemory', `ringinuse`='0', `eventwhencalled`='vars', `timeout`='1', `retry`='1'" % q).close()
		except:
			self.nipo_send_error(data, "Database not configured")
			self.mysql.close()
			pass
		self._campaigns[data["CN"]]["queue"] = q

	self.send_data('SP!CN' + data["CN"] + '!HR' + str(dialer_param_hr) +'!KA' + str(dialer_param_ka) +'!II' + str(dialer_param_ii) +'!RC' + str(dialer_param_rc))
	return 1
# AL!CNname!ANname!DVdev!TN”number”!INnr!IDn!LOloc!DL”Dialer”
# AL!CNTrain1!AN000F0000XX!DV499!IN00031109!LOOffice!ID2
    def nipo_agent_logon (self, data ):
	agents_total[self._peer] = len(self._agents) + 1
	self._campaigns[data["CN"]]["agents"][data["AN"]] = data
	self._agents[data["AN"]] = {}
	self._agents[data["AN"]] = data
	self._agents[data["AN"]]["status"] = "LOGINTRY"
	self._agents[data["AN"]]["interview_id"] = "0"
	self._agents[data["AN"]]["channels"] = {}
	self._agents_devices[data["AN"]] = {}
	self._agents_devices[data["AN"]]["extension"] = data["DV"]
	self._agents_devices[data["AN"]]["interface"] = 'Local/' + data["IN"][-1*dialer_param_extlen:] + "@nipo-call-agent"
	self._agents_devices[data["AN"]]["state_interface"] = 'Agent:' + data["IN"][-1*dialer_param_extlen:]
	return self.nipo_agent_relogin(data["AN"], data["ID"], '-1')

    def nipo_agent_relogin (self, agent, ack_id, redial_aid):
	data = self._agents[agent]
	cpg = self._campaigns[data["CN"]]
	self.nipo_log("call: nipo_agent_relogin")
	login_context = "nipo-login"
	if (cpg["TP"] > 1):
		action = {
			"Channel": "Local/" + data["DV"] + "@" + agent_context, # !!! DTMF not passed if /n used
			"Context": login_context,
			"Exten": data["IN"],
			"Timeout": cpg["WT"] 
			}
		if ack_id == '-1':
			aid = redial_aid
		else:
			action_record = {
				"action": "dialagent", 
				"campaign": data["CN"], 
				"echoer": self, 
				"number_id": '-1', 
				"TP": cpg["TP"], 
				"ID": ack_id, 
				"IN": data["IN"], 
				"AN": data["AN"]
				}
			aid = self.asterisk_add_action("agent" + data["AN"], action_record)
		action_variables = {
			"__EXTLEN": dialer_param_extlen,
			"__FULLAGENT": data["IN"],
			"__ACTIONID": aid,
			"__AGENTLANG": default_language
		}
		self.tracker.ami.originate(action["Channel"], action["Context"], action["Exten"], "1", action["Timeout"], None, aid, None, None, action_variables, True, aid).addCallbacks( self.onAMIResult, self.onAMIError )
		return -1
	return 1

    def helper_get_agentstatus (self, agent):
	return self._agents[agent]["status"]

    def helper_set_agentstatus (self, agent, status):
	self._agents[agent]["status"] = status

    def helper_set_agentchannel (self, agent, channel, chantype):
	self._agents[agent]["channels"][chantype] = channel

    def helper_get_agentchannel (self, agent, chantype):
	try:
		return self._agents[agent]["channels"][chantype]
	except:
		pass
	return None

    def helper_remove_agentchannel (self, agent, chantype):
	channel = self._agents[agent]["channels"][chantype]
	self.tracker.ami.hangup(channel).addCallbacks( self.onAMIResult, self.onAMIError )
	del self._agents[agent]["channels"][chantype]

# AA!ANname!IDn
    def nipo_agent_available (self, data ):
	try:
		self._agents[data["AN"]]["available"] = 1
	except:
		return 1
	cpg = self.get_agent_cpg(data["AN"])
	if (cpg['TP'] > 1):
		self.nipo_log("Added %s to queue:%s (dev %s)" % (data["AN"], cpg["queue"], self._agents_devices[data["AN"]]["interface"]) )
		self.mysql.query("""INSERT INTO `realtime_queue_member` 
					SET `paused`='0', `queue_name`='%s', `interface`='%s', `state_interface`='%s', `membername`='%s' 
				ON DUPLICATE KEY UPDATE 
					`paused`= VALUES(`paused`),
					`queue_name` = VALUES(`queue_name`),
					`interface` = VALUES(`interface`),
					`state_interface` = VALUES(`state_interface`),
					`membername` = VALUES(`membername`)""" % (cpg["queue"],  self._agents_devices[data["AN"]]["interface"], self._agents_devices[data["AN"]]["state_interface"], data["AN"])).close()
	return 1

################################################################

    def help_receive_number(self, data):
        try:  # optional field
            data["CI"] = data["CI"][1:-1]  # remove quotes
        except:
            data["CI"] = "Anonymous"
            pass
        data["TN"] = data["TN"][1:-1]  # remove quotes
        return data

################################################################
# SN!CNname!TN”number”!CI”number”!TIn!DL”Dialer”!II”id”
#!TN Telephone number to dial
#!CI Calling Party Id (optional)
#!TI Telephone number ID
#!DL Dialer to receive the number (optional)
#!II Interview id (optional)
    def nipo_receive_number (self, data ):
	cpg = self._campaigns[data["CN"]]
	if (cpg["TP"] <= 1):
		self.nipo_log("ERROR: Unexpected SN in preview mode! TI:%s" % data["TI"])
		return

	data = self.help_receive_number(data)
	cpg["numbers"][data["TI"]] = data
	cpg["numbers"][data["TI"]]["status"] = "NEW"
	self.asterisk_send_numbers()
	return 1

################################################################
# AD!ANname!TN”number”!CI”number”!IDn
    def nipo_agent_dial_number (self, data ):
	data = self.help_receive_number(data)
	self.asterisk_send_number_direct(data)
	return 1

################################################################
# AF!ANname!AV1!RCn!IDn
    def nipo_agent_call_finished (self, data ):
	cpg = self.get_agent_cpg(data["AN"])
	if (cpg['TP'] > 1) and (data["AV"] == "1"):
		self.nipo_complete_number(cpg["CN"], self._agents[data["AN"]]["number_id"])
		del self._agents[data["AN"]]["number_id"]
		self.mysql.query("UPDATE `realtime_queue_member` SET `paused`='0' WHERE `queue_name`='%s' AND `interface`='%s'" % (cpg["queue"],  self._agents_devices[data["AN"]]["interface"])).close()
	return 1

################################################################
    def helper_queue_pause(self, agent, pause = 1):
	cpg = self.get_agent_cpg(agent)
	self.mysql.query("UPDATE `realtime_queue_member` SET `paused`='%d' WHERE `queue_name`='%s' AND `interface`='%s'" % (pause, cpg["queue"],  self._agents_devices[agent]["interface"])).close()
	return 1

################################################################
# EI!ANname
    def nipo_agent_end_interview (self, data ):
	return 1

################################################################
# AO!ANname!IDn
    def nipo_agent_logoff (self, data ):
	# 0. Remove all channels
	self.nipo_agent_hangup(data)
	
	# 1. Try to delete agent from queue
	cpg = self.get_agent_cpg(data["AN"])
	if (cpg['TP'] > 1):
		try:
			agent_copy = self._agents[data["AN"]]
		except:
			pass
		# Hangup agent channel (logoff agent channel)
		self.tracker.ami.agentLogoff(agent_copy["IN"][-1*dialer_param_extlen:], True).addCallbacks( self.onAMIResult, self.onAMIError )
		self.nipo_log("Logoff agent %s" % (agent_copy["IN"][-1*dialer_param_extlen:]))
		# Delete queue from database
		self.mysql.query("DELETE FROM `realtime_queue_member` WHERE `queue_name`='%s' AND `interface`='%s'" % (cpg["queue"],  self._agents_devices[data["AN"]]["interface"])).close()

	# 2. Remove agnet information (before 3, to not make redial) 
	try:
		del self._agents[data["AN"]]
	except:
		pass
	return 1

################################################################
# CC!CNname!DL”Dailer”!IDn
    def nipo_close_campaign (self, data ):
	# Unload all numbers
	try:
		self.helper_unload_numbers(data["CN"])
	except:
		self.nipo_log("ERROR: !!! Unable to unload unused numbers\n")
		pass
	if (self._campaigns[data["CN"]]["TP"] > 1):
		q = "%s_%s" % (self._peerip, data["CN"])
		self.mysql.query("DELETE FROM `realtime_queue` WHERE `name`='%s'" % q).close()
		self.mysql.query("DELETE FROM `realtime_queue_member` WHERE `queue_name`='%s'" % q).close()

	del self._campaigns[data["CN"]]
	return 1

################################################################
# OD!CNname!DL”Dailer”!DVdev!IDn
    def nipo_add_dialer(self, data):
        self.nipo_log(pprint.pformat(data))
        return 1

################################################################
# AU!ANname!IDn
    def nipo_agent_unavailable(self, data):
        # TODO: Set agent on pause in case of power/predictive
        return 1

################################################################
# RC!ANname!RCn
    def nipo_agent_result_code(self, data):
        return 1

################################################################
# AH!ANname

    def nipo_agent_hangup(self, data):
        try:
            agent = self._agents[data["AN"]]
        except:
            self.nipo_log("ERROR: !!! Unable to find agent for AH\n")
            return 1
        try:
            agent_channels = deepcopy(agent["channels"])
            for chantype, channel in agent_channels.iteritems():
                self.nipo_log("Hangup %s for %s (%s channel)" % (
                    agent["channels"][chantype], data["AN"], chantype))
                self.helper_remove_agentchannel(data["AN"], chantype)
        except:
            self.nipo_log(
                "ERROR: !!! Channel hangup failed for %s\n" % (agent))
            traceback.print_exc()
            pass
        return 1

# AX!ANname!FN”filename”!IDn
    def nipo_agent_play_file (self, data ):
	chan = None
	try:
		chan = self._agents[data["AN"]]['channels']['agent'].split(';')[0]
		self.nipo_log("Playback channel (agent): %s" % (chan))
	except:
		pass
	cpg = self.get_agent_cpg(data["AN"])
	pprint.pprint(self._agents_devices)

	if (chan == None):
		self.nipo_send_error(data, "Unable to find agent channel")
		return

	self.nipo_log("Playback channel selected: %s" % (chan))
	action_record = {"action": "playfile",
		"campaign": self._agents[data["AN"]]["CN"], 
		"echoer": self, 
		"TP": cpg["TP"], 
		"AN": "-1"}

	aid = self.asterisk_add_action("play" + data["ID"], action_record)
	basename = data["FN"].split("\\")[-1]
	if '.' in basename:
		playfile = "%s/%s" % ( sounds_file_path, basename.split(".")[-2] )
	else:
		playfile = "%s/%s" % ( sounds_file_path, basename )
	action = {
			"Channel": "Local/whisper@custom-nipo-dialer/n",
			"Context": "custom-nipo-dialer",
			"Exten": "playfile",
			"Timeout": "5",
			"CalleridNum": "Anonymous",
			"Variable": {
				"__PLAYFILE": playfile, 
				"__ID": data["ID"], 
				"__SPYDEVICE": chan, 
				"__AGENTNAME": data["AN"], 
				"__ACTIONID": aid 
				} 
			}
	action_record = {
		"action": "playfile", 
		"agent": data["AN"], 
		"echoer": self 
	}
	aid = self.asterisk_add_action(data["ID"], action_record)
	self.tracker.ami.originate(action["Channel"], action["Context"], action["Exten"], "1", action["Timeout"], action["CalleridNum"], None, None, None, action["Variable"], True, aid).addCallbacks( self.onAMIResult, self.onAMIError )
	return 0
# AS!ANname
    def nipo_agent_stop_playfile (self, data ):
	try:
		self.helper_remove_agentchannel(data["AN"], "play")
	except:
		pass
	return 1
# AP!ANname!DI”digits”!IDn

    def nipo_agent_play_digits(self, data):
        try:
            self.tracker.ami.playDTMF(self._agents[data["AN"]]["channel"], data["DI"]).addCallbacks(
                self.onAMIResult, self.onAMIError)
        except KeyError:
            pass
        return 1
# AR!ANname!FN”filename”!IDn

    def nipo_agent_start_record_data(self, data):
        try:
            self.tracker.ami.monitor(self._agents[data["AN"]["channel"]], data["FN"].split(
                ".")[-1], "wav", 1).addCallbacks(self.onAMIResult, self.onAMIError)
        except KeyError:
            pass
        return 1
# AZ!ANname!Idn 1

    def nipo_agent_stop_record_data(self, data):
        try:
            self.tracker.ami.stopMonitor(self._agents[data["AN"]["channel"]]).addCallbacks(
                self.onAMIResult, self.onAMIError)
        except KeyError:
            pass
        return 1
# SI!ANname!II”id”

    def nipo_agent_set_interview_id(self, data):
        self._agents[data["AN"]]["interview_id"] = data["II"]
        return 1

# AW!ANname!DVdev!IDn
    def nipo_agent_connect_watch(self, data):
        data["TN"] = data["DV"]
        self.nipo_agent_remote_listen(data)
        return 1

# WE!ANname!IDn
    def nipo_agent_end_watch(self, data):
        self.nipo_agent_end_remote_listen(data)
        return 1

# RL!ANname!TN”number”!IDn
    def nipo_agent_remote_listen (self, data ):
	try:
		chan = self._agents[data["AN"]]['channels']['agent'].split(';')[0]
	except:
		pass
	cpg = self.get_agent_cpg(data["AN"])

	listen_outbound_context =  outbound_context
	try:
		if (data["DV"] == data["TN"]):
			listen_outbound_context = "from-queue-exten-only"
	except:
		pass
	try:
		action = {
			"Channel": "Local/" + data["TN"] + "@" + listen_outbound_context + "/n", 
			"Context": "custom-nipo-dialer",
			"Exten": "listen",
			"Timeout": "5",
			"CalleridNum": "Anonymous",
			"Variable": {
				"__SPYDEVICE": chan,
				"__AGENTNAME": data["AN"] 
				} 
			}
		action_record = { 
			"action": "listen",  
			"agent": data["AN"], 
			"echoer": self 
			}
		aid = self.asterisk_add_action(data["ID"], action_record)
		self.tracker.ami.originate(action["Channel"], action["Context"], action["Exten"], "1", action["Timeout"], action["CalleridNum"], None, None, None, action["Variable"], True, aid).addCallbacks( self.onAMIResult, self.onAMIError )
	except:
		pass
	return 1

# EL!ANname!IDn
    def nipo_agent_end_remote_listen(self, data):
        try:
            self.helper_remove_agentchannel(data["AN"], "listen")
        except KeyError:
            pass
        return 1

# Kill Agent
#     This should log the agent off without checking the agent state,
#        so when the agent is in a conversation the connection will be dropped.
#     When no ACK is received within 2 minutes an error will be generated,
#        but the agent is assumed to have logged off
# KA!ANname!IDn
    def nipo_agent_kill(self, data):
        self.nipo_agent_logoff(data)
        try:
            del self._agents[data["AN"]]
            del self._agents_devices[data["AN"]]
        except KeyError:
            pass
        return 1

# NM!MNname
    def nipo_new_master(self, data):
        self.nipo_log(pprint.pformat(data))
        return 1

########################################
# Helper functions

    def onAMIResult(self, result):
        return None

    def onAMIError(self, reason):
        return None

    def nipo_log(self, data):
        now = datetime.datetime.now()
        date_usec = now.strftime("%Y-%m-%d %H:%M:%S.") + \
            ('%06d' % now.microsecond)[:-3]
        log_line = '[' + date_usec + '][' + self._peer + '] ' + data
        print log_line
        if log_to_file:
            f = None
            try:
                f = open(log_file_path + '/messages', 'a')
                f.write(log_line + '\n')
            finally:
                if f is not None:
                    f.close()
        return

    def send_data(self, data):
        self.nipo_log('--> %s' % data)
        data = data + '\r'
        data = data.decode('utf-8').encode('utf-16')[2:]
        self.transport.getHandle().sendall(data)
        return
