#!/usr/bin/env python
__version__ = "3.2.0"
__author__ = "Tarek Galal"

from yowsup.env import YowsupEnv
from yowsup.config.manager import ConfigManager
from yowsup.profile.profile import YowProfile

from yowsup.config.v1.config import Config
from yowsup import logger as yowlogger, formatter
from yowsup.layers.network.layer import YowNetworkLayer
from yowsup.layers.protocol_media.mediacipher import MediaCipher
from yowsup.common.tools import StorageTools

from consonance.structs.publickey import PublicKey
from consonance.structs.keypair import KeyPair
import sys, argparse, yowsup, logging, os
import base64
from google import protobuf
import consonance, dissononce, cryptography, axolotl

HELP_CONFIG = """
############# Yowsup Configuration Sample ###########
#
# ====================
# The file contains info about your WhatsApp account. This is used during registration and login.
# You can define or override all fields in the command line args as well.
#
# Country code. See http://www.ipipi.com/help/telephone-country-codes.htm. This is now required.
cc=49
#
# Your full phone number including the country code you defined in 'cc', without preceding '+' or '00'
phone=491234567890
#
# Your pushname, this name is displayed to users when they're notified with your messages.
pushname=yowsup
#
# This keypair is generated during registration.
client_static_keypair=YJa8Vd9pG0KV2tDYi5V+DMOtSvCEFzRGCzOlGZkvBHzJvBE5C3oC2Fruniw0GBGo7HHgR4TjvjI3C9AihStsVg=="
#######################################################

For the full list of configuration options run "yowsup-cli config -h"

"""

VERSIONS = """yowsup-cli  v{cliVersion}
yowsup      v{yowsupVersion}
"""
VERSIONS_VERBOSE = """yowsup-cli     v{cliVersion}
yowsup         v{yowsupVersion}
consonance     v{consonanceVersion}
dissononce     v{dissononceVersion}
python-axolotl v{axolotlVersion}
cryptography   v{cryptographyVersion}
protobuf       v{protobufVersion}
"""
CR_TEXT = """{versions}

Copyright (c) 2012-2019 Tarek Galal
http://www.openwhatsapp.org

This software is provided free of charge. Copying and redistribution is
encouraged.

If you appreciate this software and you would like to support future
development please consider donating:
http://openwhatsapp.org/yowsup/donate

"""

logger = logging.getLogger('yowsup-cli')
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)


class YowArgParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        if "no_config" in kwargs:
            self._no_config = kwargs["no_config"] is True
            del kwargs["no_config"]
        else:
            self._no_config = False
        super(YowArgParser, self).__init__(*args, **kwargs)
        self._profile = None
        self.add_argument("-v", "--version",
                          action="store_true",
                          help="Print version info and exit"
                          )

        self.add_argument("-d", "--debug",
                          action="store_true",
                          help="Show debug messages"
                          )

        self.add_argument("-E", "--env",
                          action="store",
                          help="Set the environment yowsup simulates",
                          choices=YowsupEnv.getRegisteredEnvs()
                          )
        self.add_argument("--help-config", help="Prints a config file sample", action="store_true")

        if not self._no_config:
            config_group = self.add_argument_group(
                "Configuration options",
                description="Only some of the configuration parameters are required depending on the action being "
                            "performed using yowsup"
            )
            config_group.add_argument(
                "-c", '--config',
                action="store",
                help="(optional) Path to config file, or profile name. Other configuration arguments have higher "
                     "priority if given, and will override those specified in the config file."
            )
            config_group.add_argument(
                '--config-phone', '--phone',
                action="store",
                help="Your full phone number including the country code you defined in 'cc',"
                     " without preceeding '+' or '00'"
            )
            config_group.add_argument(
                '--config-cc', '--cc',
                action="store",
                help="Country code. See http://www.ipipi.com/networkList.do."
            )
            config_group.add_argument(
                '--config-pushname',
                action="store",
                help="Push/Display name to use "
            )
            config_group.add_argument(
                '--config-id',
                action="store",
                help="Base64 encoded Identity/Recovery token, typically generated and used during registration or account "
                     "recovery."
            )
            config_group.add_argument(
                '--config-mcc', '--mcc',
                action="store",
                help="Mobile Country Code. Check your mcc here: https://en.wikipedia.org/wiki/Mobile_country_code"
            )
            config_group.add_argument(
                '--config-mnc', '--mnc',
                action="store",
                help="Mobile Network Code. Check your mnc from https://en.wikipedia.org/wiki/Mobile_country_code"
            )
            config_group.add_argument(
                '--config-sim_mcc',
                action="store",
                help="Mobile Country Code. Check your mcc here: https://en.wikipedia.org/wiki/Mobile_country_code"
            )
            config_group.add_argument(
                '--config-sim_mnc',
                action="store",
                help="Mobile Network Code. Check your mnc from https://en.wikipedia.org/wiki/Mobile_country_code"
            )
            config_group.add_argument(
                '--config-client_static_keypair',
                action="store",
                help="Base64 encoded concatenation of user keypair's private bytes and public bytes"
            )
            config_group.add_argument(
                '--config-server_static_public',
                action="store",
                help="Base64 encoded server's public key bytes"
            )
            config_group.add_argument(
                '--config-expid',
                action="store",
                help="Base64 encoded expid, typically generated and used during registration"
            )
            config_group.add_argument(
                '--config-fdid',
                action="store",
                help="Device UUID, typically generated for registration and used at login"
            )
            config_group.add_argument(
                '--config-edge_routing_info',
                action="store",
                help="Base64 encoded edge_routing_info, normally received and persisted right after a successful login"
            )
            config_group.add_argument(
                '--config-chat_dns_domain',
                action="store",
                help="Chat DNS domain, normally received and persisted right after a successful login"
            )
        self.args = {}

    def getArgs(self):
        return self.parse_args()

    def process(self):
        self.args = vars(self.parse_args())

        if self.args["debug"]:
            logger.setLevel(logging.DEBUG)
            yowlogger.setLevel(level=logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
            yowlogger.setLevel(level=logging.INFO)

        if self.args["env"]:
            YowsupEnv.setEnv(self.args["env"])

        if not self._no_config:
            config_phone = self.args["config_phone"]
            config_manager = ConfigManager()
            profile_name = None
            config_loaded_from_profile = True
            if self.args["config"]:
                config = config_manager.load(self.args["config"])
                if not os.path.isfile(self.args["config"]):
                    profile_name = self.args["config"]
                elif not self.args["config"].startswith(StorageTools.getStorageForProfile(config.phone)):
                    config_loaded_from_profile = False
            elif config_phone:
                config = config_manager.load(config_phone)
            else:
                raise ValueError("Must specify either --config or --config-phone")

            if config is None:
                config = Config()

            if config_phone is not None:
                config.phone = config_phone

            if self.args["config_cc"]:
                config.cc = self.args["config_cc"]

            if self.args["config_pushname"]:
                config.pushname = self.args["config_pushname"]

            if self.args["config_id"]:
                config.id = base64.b64decode(self.args["config_id"])

            if self.args["config_mcc"]:
                config.mcc = self.args["config_mcc"]

            if self.args["config_mnc"]:
                config.mnc = self.args["config_mnc"]

            if self.args["config_sim_mcc"]:
                config.sim_mcc = self.args["config_sim_mcc"]

            if self.args["config_sim_mnc"]:
                config.sim_mnc = self.args["config_sim_mnc"]

            if self.args["config_client_static_keypair"]:
                config.client_static_keypair = KeyPair.from_bytes(
                    base64.b64decode(self.args["config_client_static_keypair"])
                )

            if self.args["config_server_static_public"]:
                config.server_static_public = PublicKey(
                    base64.b64decode(self.args["config_server_static_public"])
                )

            if self.args["config_expid"]:
                config.expid = base64.b64decode(self.args["config_expid"])

            if self.args["config_fdid"]:
                config.fdid = self.args["config_fdid"]

            if self.args["config_edge_routing_info"]:
                config.edge_routing_info = base64.b64decode(self.args["config_edge_routing_info"])

            if self.args["config_chat_dns_domain"]:
                config.chat_dns_domain = self.args["config_chat_dns_domain"]

            if not config_loaded_from_profile:
                # config file was explicitly specified and is not that of profile,
                # load profile config and override values
                internal_config = config_manager.load(config.phone, profile_only=True)
                if internal_config is not None:
                    for property in config.keys():
                        if property != "version" and config[property] is not None:
                            internal_config[property] = config[property]
                    config = internal_config

            if self._profile is None or self._profile.config is None:
                self._profile = YowProfile(profile_name or config.phone, config)

            if self._profile.config.phone is None:
                print("Invalid config")
                sys.exit(1)

        if self.args["version"]:
            print("yowsup-cli v%s\nUsing yowsup v%s" % (__version__, yowsup.__version__))
            sys.exit(0)

        if self.args["help_config"]:
            print(HELP_CONFIG)
            sys.exit(0)

    def printInfoText(self):
        verbose = self.args["debug"]
        if verbose:
            versions = VERSIONS_VERBOSE.format(
                cliVersion=__version__, yowsupVersion=yowsup.__version__,
                consonanceVersion=consonance.__version__,
                dissononceVersion=dissononce.__version__,
                axolotlVersion=axolotl.__version__,
                cryptographyVersion=cryptography.__version__,
                protobufVersion=protobuf.__version__
            )
        else:
            versions = VERSIONS.format(cliVersion=__version__, yowsupVersion=yowsup.__version__)
        print(CR_TEXT.format(versions=versions))

class DemosArgParser(YowArgParser):

    LAYER_NETWORK_DISPATCHERS_MAP = {
        "socket": YowNetworkLayer.DISPATCHER_SOCKET,
        "asyncore": YowNetworkLayer.DISPATCHER_ASYNCORE
    }

    def __init__(self, *args, **kwargs):
        super(DemosArgParser, self).__init__(*args, **kwargs)
        self.description = "Run a yowsup demo"

        net_layer_opts = self.add_argument_group("Network layer props")
        net_layer_opts.add_argument(
            '--layer-network-dispatcher', action="store", choices=("asyncore", "socket"),
            help="Specify which connection dispatcher to use"
        )

        cmdopts = self.add_argument_group("Command line interface demo")
        cmdopts.add_argument('-y', '--yowsup', action="store_true", help="Start the Yowsup command line client")

        echoOpts = self.add_argument_group("Echo client demo")
        echoOpts.add_argument('-e', '--echo', action="store_true", help="Start the Yowsup Echo client")

        sendOpts = self.add_argument_group("Send client demo")
        sendOpts.add_argument('-s', '--send', action="store", help="Send a message to specified phone number, "
                                                                   "wait for server receipt and exit",
                              metavar=("phone", "message"), nargs=2)
        syncContacts = self.add_argument_group("Sync contacts")
        syncContacts.add_argument('-S', '--sync', action="store", help="Sync ( check valid ) whatsapp contacts",
                                  metavar=("contacts"))

        mediasinkOpts = self.add_argument_group("Media sink demo")
        mediasinkOpts.add_argument('-m', '--mediasink', action="store_true",
                                   help="Start the Media Sink client")
        mediasinkOpts.add_argument('--media-store-dir', action="store", required=False,
                                   help="Specify where to download incoming media files, if not set "
                                        "will download to a temporary directory.")

        logging = self.add_argument_group("Logging options")
        logging.add_argument("--log-dissononce", action="store_true", help="Configure logging for dissononce/noise")
        logging.add_argument("--log-consonance", action="store_true", help="Configure logging for consonance")

        self._layer_network_dispatcher = None

    def process(self):
        super(DemosArgParser, self).process()

        if self.args["log_dissononce"]:
            from dissononce import logger as dissononce_logger, ch as dissononce_ch
            dissononce_logger.setLevel(logger.level)
            dissononce_ch.setFormatter(formatter)
        if self.args["log_consonance"]:
            from consonance import logger as consonance_logger, ch as consonance_ch
            consonance_logger.setLevel(logger.level)
            consonance_ch.setFormatter(formatter)

        if self.args["layer_network_dispatcher"] is not None:
            self._layer_network_dispatcher = self.LAYER_NETWORK_DISPATCHERS_MAP[
                self.args["layer_network_dispatcher"]
            ]
        self.startCmdline()
        return True

    def _ensure_config_props(self):
        if self._profile.config.client_static_keypair is None:
            print("Specified config does not have client_static_keypair, aborting")
            sys.exit(1)

    def startCmdline(self):
        self._ensure_config_props()
        logger.debug("starting cmd")
        from yowsup.demos import cli
        self.printInfoText()
        stack = cli.YowsupCliStack(self._profile)
        if self._layer_network_dispatcher is not None:
            stack.set_prop(YowNetworkLayer.PROP_DISPATCHER, self._layer_network_dispatcher)
        stack.start()


if __name__ == "__main__":
    args = sys.argv
    if (len(args) > 1):
        del args[0]

    parser = DemosArgParser()
    if not parser.process():
        parser.print_help()
