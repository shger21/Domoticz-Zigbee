
import Domoticz

from datetime import datetime
from time import time

from Modules.logging import loggingLegrand
from Modules.output import raw_APS_request, write_attribute


def pollingPhilips( self, key ):

    """
    This fonction is call if enabled to perform any Manufacturer specific polling action
    The frequency is defined in the pollingSchneider parameter (in number of seconds)
    """

    rescheduleAction = False

    return True


def callbackDeviceAwake_Philips(self, NwkId, EndPoint, cluster):

    """
    This is fonction is call when receiving a message from a Manufacturer battery based device.
    The function is called after processing the readCluster part
    """

    Domoticz.Log("callbackDeviceAwake_Legrand - Nwkid: %s, EndPoint: %s cluster: %s" \
            %(NwkId, EndPoint, cluster))

    return

