#############################################################
#
# ax-smil-python
#
#############################################################

AX_SMIL_PYTHON_VERSION=1.2.19
AX_SMIL_PYTHON_SITE=git@git.axent.com.au:axent-smil-player/axent_smil_python.git
AX_SMIL_PYTHON_SITE_METHOD=git
AX_SMIL_PYTHON_INSTALL_TARGET=YES
AX_SMIL_PYTHON_DEPENDENCIES=python pycairo pil

define AX_SMIL_PYTHON_BUILD_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py build --executable=/usr/bin/python)
endef

define AX_SMIL_PYTHON_INSTALL_TARGET_CMDS
    (cd $(@D); export STAGING_DIR=$(STAGING_DIR); \
     $(HOST_DIR)/usr/bin/python setup.py install --prefix=$(TARGET_DIR)/usr)
endef

$(eval $(generic-package))
