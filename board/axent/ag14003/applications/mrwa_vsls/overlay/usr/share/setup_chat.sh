#!/bin/sh
INTERFACE=$1
APN=`sqlite3 /usr/share/db/config.db "select apn from modem where interface='$INTERFACE'"`
AUTH_MODE=`sqlite3 /usr/share/db/config.db "select auth_mode from modem where interface='$INTERFACE'"`
AUTH_USER=`sqlite3 /usr/share/db/config.db "select auth_user from modem where interface='$INTERFACE'"`
AUTH_PASS=`sqlite3 /usr/share/db/config.db "select auth_pass from modem where interface='$INTERFACE'"`

echo "ABORT 'NO DIAL TONE' ABORT 'NO ANSWER' ABORT 'NO CARRIER' ABORT DELAYED" > /etc/gsm/mc879x
echo "" >> /etc/gsm/mc879x
echo "'' AT" >> /etc/gsm/mc879x
echo "OK 'AT+CGDCONT=1,\"IP\",\"$APN\"'" >> /etc/gsm/mc879x
if [ "$AUTH_MODE" == "pap" ]
then
    echo "OK 'AT\$QCPDPP=1,1,\"$AUTH_USER\",\"$AUTH_PASS\"'" >> /etc/gsm/mc879x
elif [ "$AUTH_MODE" == "chap" ]
then
    echo "OK 'AT\$QCPDPP=2,$AUTH,\"$AUTH_USER\",\"$AUTH_PASS\"'" >> /etc/gsm/mc879x
else
    echo "OK 'AT\$QCPDPP=1,$AUTH'" >> /etc/gsm/mc879x
fi
echo "OK 'AT!SCACT=1,1'" >> /etc/gsm/mc879x
echo "OK ''" >> /etc/gsm/mc879x
