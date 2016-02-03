#!/bin/sh
#
# Sets up the configuration database using config_template and config_settings.

TARGETDIR=$1
BR_ROOT=$PWD

# Remove unnecessary ssh helpers.
rm $TARGETDIR/usr/libexec/ssh-keysign
rm $TARGETDIR/usr/libexec/ssh-pkcs11-helper
rm $TARGETDIR/usr/bin/ssh-agent
rm $TARGETDIR/usr/bin/ssh-add
rm $TARGETDIR/usr/bin/ssh-keyscan
rm $TARGETDIR/usr/bin/sftp

rm -rf $TARGETDIR/usr/share/db 2> /dev/null
mkdir -p $TARGETDIR/usr/share/db
sqlite3 $TARGETDIR/usr/share/db/config.db < $TARGETDIR/usr/share/ax-utils/config_template
sqlite3 $TARGETDIR/usr/share/db/config.db < $BR_ROOT/board/axent/ag14003/applications/mrwa_vsls/config_settings
sqlite3 $TARGETDIR/usr/share/db/rta.db < $BR_ROOT/board/axent/ag14003/applications/mrwa_vsls/rta_config_template
sqlite3 $TARGETDIR/usr/share/db/log.db < $BR_ROOT/board/axent/ag14003/applications/mrwa_vsls/log_template
sqlite3 $TARGETDIR/usr/share/db/rta_log.db < $BR_ROOT/board/axent/ag14003/applications/mrwa_vsls/rta_log_template
