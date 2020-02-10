from yowsup.layers.interface import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers import YowLayerEvent, EventCallback
from yowsup.layers.network import YowNetworkLayer
import sys
from yowsup.common import YowConstants
import datetime
import time
import os
import logging
import threading
import base64
from yowsup.layers.protocol_groups.protocolentities      import *
from yowsup.layers.protocol_presence.protocolentities    import *
from yowsup.layers.protocol_messages.protocolentities    import *
from yowsup.layers.protocol_ib.protocolentities          import *
from yowsup.layers.protocol_iq.protocolentities          import *
from yowsup.layers.protocol_contacts.protocolentities    import *
from yowsup.layers.protocol_chatstate.protocolentities   import *
from yowsup.layers.protocol_privacy.protocolentities     import *
from yowsup.layers.protocol_media.protocolentities       import *
from yowsup.layers.protocol_media.mediauploader import MediaUploader
from yowsup.layers.protocol_profiles.protocolentities    import *
from yowsup.common.tools import Jid
from yowsup.common.optionalmodules import PILOptionalModule
from yowsup.layers.axolotl.protocolentities.iq_key_get import GetKeysIqProtocolEntity

f = open('phones.txt', 'r')
phones = f.readlines()
f.close()

fr = open('recipient.txt', 'r')
recipient = fr.readline().strip()
fr.close()

logger = logging.getLogger(__name__)
class YowsupCliLayer(YowInterfaceLayer):
    PROP_RECEIPT_AUTO       = "org.openwhatsapp.yowsup.prop.cli.autoreceipt"
    PROP_RECEIPT_KEEPALIVE  = "org.openwhatsapp.yowsup.prop.cli.keepalive"
    PROP_CONTACT_JID        = "org.openwhatsapp.yowsup.prop.cli.contact.jid"
    EVENT_LOGIN             = "org.openwhatsapp.yowsup.event.cli.login"
    EVENT_START             = "org.openwhatsapp.yowsup.event.cli.start"
    EVENT_SENDANDEXIT       = "org.openwhatsapp.yowsup.event.cli.sendandexit"

    MESSAGE_FORMAT          = "[%s(%s)]:[%s]\t %s"

    FAIL_OPT_PILLOW         = "No PIL library installed, try install pillow"
    FAIL_OPT_AXOLOTL        = "axolotl is not installed, try install python-axolotl"

    DISCONNECT_ACTION_PROMPT = 0
    DISCONNECT_ACTION_EXIT   = 1

    ACCOUNT_DEL_WARNINGS = 4

    def __init__(self):
        super(YowsupCliLayer, self).__init__()
        YowInterfaceLayer.__init__(self)
        self.accountDelWarnings = 0
        self.connected = False
        self.username = None
        self.sendReceipts = True
        self.sendRead = True
        self.disconnectAction = self.__class__.DISCONNECT_ACTION_PROMPT

        #add aliases to make it user to use commands. for example you can then do:
        # /message send foobar "HI"
        # and then it will get automaticlaly mapped to foobar's jid
        self.jidAliases = {
            # "NAME": "PHONE@s.whatsapp.net"
        }

    def aliasToJid(self, calias):
        for alias, ajid in self.jidAliases.items():
            if calias.lower() == alias.lower():
                return Jid.normalize(ajid)

        return Jid.normalize(calias)

    def jidToAlias(self, jid):
        for alias, ajid in self.jidAliases.items():
            if ajid == jid:
                return alias
        return jid

    @EventCallback(EVENT_START)
    def onStart(self, layerEvent):
        self.L()
        return True

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def onStateDisconnected(self,layerEvent):
        if self.disconnectAction == self.__class__.DISCONNECT_ACTION_PROMPT:
           self.connected = False
           time.sleep(5)
           self.L()
        else:
           os._exit(os.EX_OK)

    def assertConnected(self):
        if self.connected:
            return True
        else:
            return False

    ########## PRESENCE ###############

    def presence_available(self):
        if self.assertConnected():
            entity = AvailablePresenceProtocolEntity()
            self.toLower(entity)

    def presence_subscribe(self, contact):
        if self.assertConnected():
            entity = SubscribePresenceProtocolEntity(self.aliasToJid(contact))
            self.toLower(entity)


    ########### END PRESENCE #############

    def message_send(self, number, content):
        if self.assertConnected():
            outgoingMessage = TextMessageProtocolEntity(content, to=self.aliasToJid(number))
            self.toLower(outgoingMessage)

    def disconnect(self):
        if self.assertConnected():
            self.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))

    def L(self):
        if self.connected:
            return True
        threading.Thread(target=lambda: self.getLayerInterface(YowNetworkLayer).connect()).start()
        return True

    ######## receive #########
    
    @ProtocolEntityCallback("presence")
    def onPresenceChange(self, entity):
        status="offline"
        if entity.getType() is None:
            status="online"     
        ##raw fix for iphone lastseen deny output
        lastseen = entity.getLast()
        if status is "offline" and lastseen is "deny":
            lastseen = time.time()
        ##
        message = "%s %s %s" % (entity.getFrom(), status, lastseen)
        self.message_send(recipient, message )
        print(message)
        

    @ProtocolEntityCallback("success")
    def onSuccess(self, entity):
        self.connected = True
        self.presence_available()
        for ph in phones:
            self.presence_subscribe(ph.strip())
        self.message_send(recipient, 'reconnected')
        print('connected')

    @ProtocolEntityCallback("failure")
    def onFailure(self, entity):
        print('failure')
        self.connected = False

    def __str__(self):
        return "CLI Interface Layer"


