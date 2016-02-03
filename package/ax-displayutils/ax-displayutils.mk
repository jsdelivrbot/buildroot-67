#############################################################
#
# ax-displayutils
#
#############################################################

AX_DISPLAYUTILS_VERSION=1.2.1
AX_DISPLAYUTILS_SITE=git@git.axent.com.au:ag14003/axent_displayutils.git
AX_DISPLAYUTILS_SITE_METHOD=git
AX_DISPLAYUTILS_DEPENDENCIES=host-python python host-sqlite sqlite

define AX_DISPLAYUTILS_BUILD_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py build --executable=/usr/bin/python)
endef

define AX_DISPLAYUTILS_INSTALL_TARGET_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py install --root=$(TARGET_DIR) --prefix=/usr --exec-prefix=/usr)
endef

$(eval $(call generic-package))
