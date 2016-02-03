#!/bin/sh
ifname=$1
at_device=$2
watchdog_enabled=`sqlite3 /usr/share/db/config.db "select watchdog_enabled from modem where interface='$ifname'"`
ping_ip=`sqlite3 /usr/share/db/config.db "select watchdog_ip from modem where interface='$ifname'"`

echo `pidof gprs_monitor.sh` > /var/run/gprs_monitor.$ifname.pid 2>/dev/null

sleep 300

while [ 1 ]
do
    if [ "$watchdog_enabled" == "yes" ]
    then
        received=`ping -q -I $ifname -c 3 $ping_ip 2>/dev/null | grep "transmitted" | cut -d' ' -f4`
        if [ "$received" == "0" -o "$received" == "" ]
        then
            TIME=`date '+%F %T'`
            STRING="Modem reset by ping keep-alive"
            echo $TIME: $STRING >> /tmp/modem_log
            echo "at!reset" > /dev/$at_device
        else
            echo `date '+%F %T'` > /tmp/last_modem_ping
        fi
    fi
    
    sleep 60
    
    chat -t2 '' AT OK '' < /dev/$at_device > /dev/$at_device
    RETVAL=$?
    
    if [ $RETVAL -ne 0 ]
    then
        TIME=`date '+%F %T'`
        STRING="Modem not responding to AT commands, resetting..."
        echo $STRING
        echo $TIME: $STRING >> /tmp/modem_log
        echo -n -e '\x7e\x00\x0c\x2b\x00\x00\x10\x03\x00\x00\x00\x00\x00\x00\x02\x00\x01\x7e' > /dev/ttyUSB0
    fi
    
    sleep 60
done
