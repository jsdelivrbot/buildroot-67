#############################################################
#
# ax-utils-ag13008
#
#############################################################

AX_UTILS_AG13008_VERSION=1.10.9
AX_UTILS_AG13008_SITE=git@git.axent.com.au:ag13008/ax_utils.git
AX_UTILS_AG13008_SITE_METHOD=git
AX_UTILS_AG13008_INSTALL_TARGET=YES
AX_UTILS_AG13008_DEPENDENCIES=host-python python host-sqlite sqlite

define AX_UTILS_AG13008_BUILD_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py build --executable=/usr/bin/python)
endef

define AX_UTILS_AG13008_INSTALL_TARGET_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py install --root=$(TARGET_DIR) --prefix=/usr --exec-prefix=/usr)
endef

$(eval $(call generic-package))
