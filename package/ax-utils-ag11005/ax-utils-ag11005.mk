#############################################################
#
# ax-utils-ag11005
#
#############################################################

AX_UTILS_AG11005_VERSION=1.10.9
AX_UTILS_AG11005_SITE=git@git.axent.com.au:ag11005-controller/axent_utils.git
AX_UTILS_AG11005_SITE_METHOD=git
AX_UTILS_AG11005_INSTALL_TARGET=YES
AX_UTILS_AG11005_DEPENDENCIES=host-python python host-sqlite sqlite

define AX_UTILS_AG11005_BUILD_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py build --executable=/usr/bin/python)
endef

define AX_UTILS_AG11005_INSTALL_TARGET_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py install --root=$(TARGET_DIR) --prefix=/usr --exec-prefix=/usr)
endef

$(eval $(call generic-package))
