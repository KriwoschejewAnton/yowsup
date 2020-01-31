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
        self._no_config = False
        super(YowArgParser, self).__init__(*args, **kwargs)
        self._profile = None

        self.add_argument("-d", "--debug",
                          action="store_true",
                          help="Show debug messages"
                          )
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

        YowsupEnv.setEnv("android")

        config_manager = ConfigManager()
        profile_name = None
        config_loaded_from_profile = True
        if self.args["config"]:
            config = config_manager.load(self.args["config"])
            if not os.path.isfile(self.args["config"]):
                profile_name = self.args["config"]
            elif not self.args["config"].startswith(StorageTools.getStorageForProfile(config.phone)):
                config_loaded_from_profile = False
        else:
            raise ValueError("Must specify --config")

        if config is None:
            config = Config()

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
