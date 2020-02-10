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
        #self.startInput()
        return True

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def onStateDisconnected(self,layerEvent):
        if self.disconnectAction == self.__class__.DISCONNECT_ACTION_PROMPT:
           self.connected = False
           #self.notifyInputThread()
           time.sleep(1)
           self.L()
        else:
           os._exit(os.EX_OK)

    def assertConnected(self):
        if self.connected:
            return True
        else:
            self.output("Not connected", tag = "Error", prompt = False)
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
            return self.output("Already connected, disconnect first")
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
        self.output(message)
        self.message_send(recipient, message )
        
    @ProtocolEntityCallback("chatstate")
    def onChatstate(self, entity):
        print(entity)

    @ProtocolEntityCallback("iq")
    def onIq(self, entity):
        if not isinstance(entity, ResultStatusesIqProtocolEntity):  # already printed somewhere else
            print(entity)

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        self.toLower(entity.ack())

    @ProtocolEntityCallback("ack")
    def onAck(self, entity):
        #formattedDate = datetime.datetime.fromtimestamp(self.sentCache[entity.getId()][0]).strftime('%d-%m-%Y %H:%M')
        #print("%s [%s]:%s"%(self.username, formattedDate, self.sentCache[entity.getId()][1]))
        if entity.getClass() == "message":
            self.output(entity.getId(), tag = "Sent")
            #self.notifyInputThread()

    @ProtocolEntityCallback("success")
    def onSuccess(self, entity):
        self.connected = True
        self.output("Logged in!", "Auth", prompt = False)
        self.notifyInputThread()
        self.presence_available()
        for ph in phones:
            self.presence_subscribe(ph.strip())
        self.message_send(recipient, 'reconnected')

    @ProtocolEntityCallback("failure")
    def onFailure(self, entity):
        self.connected = False
        #self.output("Login Failed, reason: %s" % entity.getReason(), prompt = False)

    @ProtocolEntityCallback("notification")
    def onNotification(self, notification):
        notificationData = notification.__str__()
        if notificationData:
            self.output(notificationData, tag = "Notification")
        else:
            self.output("From :%s, Type: %s" % (self.jidToAlias(notification.getFrom()), notification.getType()), tag = "Notification")

    @ProtocolEntityCallback("message")
    def onMessage(self, message):
        messageOut = ""
        if message.getType() == "text":
            #self.output(message.getBody(), tag = "%s [%s]"%(message.getFrom(), formattedDate))
            messageOut = self.getTextMessageBody(message)
        elif message.getType() == "media":
            messageOut = self.getMediaMessageBody(message)
        else:
            messageOut = "Unknown message type %s " % message.getType()
            print(messageOut.toProtocolTreeNode())

        formattedDate = datetime.datetime.fromtimestamp(message.getTimestamp()).strftime('%d-%m-%Y %H:%M')
        sender = message.getFrom() if not message.isGroupMessage() else "%s/%s" % (message.getParticipant(False), message.getFrom())

        output = self.__class__.MESSAGE_FORMAT % (sender, formattedDate, message.getId(), messageOut)

        self.output(output, tag = None, prompt = not self.sendReceipts)
        if self.sendReceipts:
            self.toLower(message.ack(self.sendRead))
            self.output("Sent delivered receipt"+" and Read" if self.sendRead else "", tag = "Message %s" % message.getId())

    def getTextMessageBody(self, message):
        if isinstance(message, TextMessageProtocolEntity):
            return message.conversation
        elif isinstance(message, ExtendedTextMessageProtocolEntity):
            return str(message.message_attributes.extended_text)
        else:
            raise NotImplementedError()

    def getMediaMessageBody(self, message):
        # type: (DownloadableMediaMessageProtocolEntity) -> str
        return str(message.message_attributes)

    def getDownloadableMediaMessageBody(self, message):
        return "[media_type={media_type}, length={media_size}, url={media_url}, key={media_key}]".format(
            media_type=message.media_type,
            media_size=message.file_length,
            media_url=message.url,
            media_key=base64.b64encode(message.media_key)
        )

    def doSendMedia(self, mediaType, filePath, url, to, ip = None, caption = None):
        if mediaType == RequestUploadIqProtocolEntity.MEDIA_TYPE_IMAGE:
        	entity = ImageDownloadableMediaMessageProtocolEntity.fromFilePath(filePath, url, ip, to, caption = caption)
        elif mediaType == RequestUploadIqProtocolEntity.MEDIA_TYPE_AUDIO:
        	entity = AudioDownloadableMediaMessageProtocolEntity.fromFilePath(filePath, url, ip, to)
        elif mediaType == RequestUploadIqProtocolEntity.MEDIA_TYPE_VIDEO:
        	entity = VideoDownloadableMediaMessageProtocolEntity.fromFilePath(filePath, url, ip, to, caption = caption)
        self.toLower(entity)

    def __str__(self):
        return "CLI Interface Layer"

    ########### callbacks ############

    def onRequestUploadResult(self, jid, mediaType, filePath, resultRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity, caption = None):

        if resultRequestUploadIqProtocolEntity.isDuplicate():
            self.doSendMedia(mediaType, filePath, resultRequestUploadIqProtocolEntity.getUrl(), jid,
                             resultRequestUploadIqProtocolEntity.getIp(), caption)
        else:
            successFn = lambda filePath, jid, url: self.doSendMedia(mediaType, filePath, url, jid, resultRequestUploadIqProtocolEntity.getIp(), caption)
            mediaUploader = MediaUploader(jid, self.getOwnJid(), filePath,
                                      resultRequestUploadIqProtocolEntity.getUrl(),
                                      resultRequestUploadIqProtocolEntity.getResumeOffset(),
                                      successFn, self.onUploadError, self.onUploadProgress, asynchronous=False)
            mediaUploader.start()

    def onRequestUploadError(self, jid, path, errorRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity):
        logger.error("Request upload for file %s for %s failed" % (path, jid))

    def onUploadError(self, filePath, jid, url):
        logger.error("Upload file %s to %s for %s failed!" % (filePath, url, jid))

    def onUploadProgress(self, filePath, jid, url, progress):
        sys.stdout.write("%s => %s, %d%% \r" % (os.path.basename(filePath), jid, progress))
        sys.stdout.flush()

    def onGetContactPictureResult(self, resultGetPictureIqProtocolEntiy, getPictureIqProtocolEntity):
        # do here whatever you want
        # write to a file
        # or open
        # or do nothing
        # write to file example:
        #resultGetPictureIqProtocolEntiy.writeToFile("/tmp/yowpics/%s_%s.jpg" % (getPictureIqProtocolEntity.getTo(), "preview" if resultGetPictureIqProtocolEntiy.isPreview() else "full"))
        pass

