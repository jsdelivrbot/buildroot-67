#############################################################
#
# jsonrpclib
#
#############################################################

JSONRPCLIB_VERSION=e3a3cded
JSONRPCLIB_SITE=git://github.com/joshmarshall/jsonrpclib.git
JSONRPCLIB_INSTALL_TARGET=YES
JSONRPCLIB_DEPENDENCIES=python

define JSONRPCLIB_BUILD_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py build --executable=/usr/bin/python)
endef

define JSONRPCLIB_INSTALL_TARGET_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); $(HOST_DIR)/usr/bin/python setup.py install --prefix=$(TARGET_DIR)/usr)
endef

$(eval $(call generic-package))
