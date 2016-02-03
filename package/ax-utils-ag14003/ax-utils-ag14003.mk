#############################################################
#
# ax-utils-ag14003
#
#############################################################

AX_UTILS_AG14003_VERSION=1.12.3
AX_UTILS_AG14003_SITE=git@git.axent.com.au:ag14003/ax_utils.git
AX_UTILS_AG14003_SITE_METHOD=git
AX_UTILS_AG14003_INSTALL_TARGET=YES
AX_UTILS_AG14003_DEPENDENCIES=host-python python host-sqlite sqlite

define AX_UTILS_AG14003_BUILD_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py build --executable=/usr/bin/python)
endef

define AX_UTILS_AG14003_INSTALL_TARGET_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py install --root=$(TARGET_DIR) --prefix=/usr --exec-prefix=/usr)
endef

$(eval $(call generic-package))
