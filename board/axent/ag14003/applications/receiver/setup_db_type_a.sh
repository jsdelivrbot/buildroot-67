#!/bin/sh
#
# Sets up the configuration database using config_template and config_settings.

TARGETDIR=$1
BR_ROOT=$PWD

# Remove unnecessary ssh helpers.
rm -rf $TARGETDIR/usr/libexec/ssh-keysign
rm -rf $TARGETDIR/usr/libexec/ssh-pkcs11-helper

rm -rf $TARGETDIR/usr/share/db 2> /dev/null
mkdir -p $TARGETDIR/usr/share/db
sqlite3 $TARGETDIR/usr/share/db/config.db < $TARGETDIR/usr/share/ax-utils/config_template
sqlite3 $TARGETDIR/usr/share/db/config.db < $BR_ROOT/board/axent/ag14003/applications/receiver/config_settings_type_a
