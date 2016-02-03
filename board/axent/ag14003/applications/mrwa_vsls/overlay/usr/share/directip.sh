#!/bin/sh
#
# Reconfigure the modem to directIP if applicable
#

if [ -e /dev/ttyUSB5 ]; then
	/usr/sbin/chat -t10 -f /etc/gsm/enable_directip > /dev/ttyUSB3 < /dev/ttyUSB3
fi
