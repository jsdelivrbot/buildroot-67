#!/bin/sh

LOG_IP=0
LOG_NOIP=0
LOG_CONNECT=0
LOG_DISCONNECT=0

while [ 1 ]
do
    if [ "`ifconfig -a | grep 'wwan0' | cut -d' ' -f1`" = "" ]
    then
    	if [ $LOG_DISCONNECT -eq 0 ]
    	then
    		LOG_CONNECT=0
    		LOG_DISCONNECT=1
			TIME=`date '+%F %T'`
			STRING="Modem Disconnected"
			echo $TIME: $STRING >> /tmp/modem_log      		
    	fi
    else
     	if [ $LOG_CONNECT -eq 0 ]
    	then
    		LOG_CONNECT=1
    		LOG_DISCONNECT=0
			TIME=`date '+%F %T'`
			STRING="Modem Connected"
			echo $TIME: $STRING >> /tmp/modem_log      		
    	fi
    fi

    if [ $LOG_DISCONNECT -ne 1 ]
    then
        if [ "`ifconfig wwan0 2>/dev/null | grep 'inet addr:' | grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`" = "" ]
        then
            ifdown wwan0 >/dev/null
            ifup wwan0 >/dev/null
        	if [ $LOG_NOIP -eq 0 ]
        	then
        		LOG_IP=0
        		LOG_NOIP=1
			    TIME=`date '+%F %T'`
			    STRING="Modem IP Lost"
			    echo $TIME: $STRING >> /tmp/modem_log     		
        	fi
        else
        	if [ $LOG_IP -eq 0 ]
        	then
        		LOG_IP=1
        		LOG_NOIP=0
			    TIME=`date '+%F %T'`
			    IP=`ifconfig wwan0 | grep 'inet addr:' | grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`
			    STRING="Modem IP set to $IP"
			    echo $TIME: $STRING >> /tmp/modem_log     		
        	fi
        fi

        if [ -c /dev/ttyUSB0 ]
        then
            if ! [ -c /dev/ttyUSB1 ] && ! [ -c /dev/ttyUSB2 ] && ! [ -c /dev/ttyUSB3 ] 
            then
                TIME=`date '+%F %T'`
                STRING="Modem in firmware update mode, resetting..."
                echo $TIME: $STRING >> /tmp/modem_log
                echo -n -e '\x7e\x00\x00\x04\x00\x7e' > /dev/ttyUSB0
            elif ! [ -c /dev/ttyUSB1 ] || ! [ -c /dev/ttyUSB2 ] || ! [ -c /dev/ttyUSB3 ]
            then
                TIME=`date '+%F %T'`
                STRING="Modem in invalid mode, resetting..."
                echo $TIME: $STRING >> /tmp/modem_log
                echo -n -e '\x7e\x00\x0c\x2b\x00\x00\x10\x03\x00\x00\x00\x00\x00\x00\x02\x00\x01\x7e' > /dev/ttyUSB0
                rm /dev/ttyUSB*
            fi
        fi
    fi
	
    sleep 10
done
