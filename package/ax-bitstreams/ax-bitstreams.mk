#############################################################
#
# ax-bitstreams
#
#############################################################

AX_BITSTREAMS_VERSION=1.31
AX_BITSTREAMS_SITE=git@git.axent.com.au:ag11005-controller/ax-bitstreams.git
AX_BITSTREAMS_SITE_METHOD=git
AX_BITSTREAMS_INSTALL_TARGET=YES

AX_BITSTREAMS_TARGET_DIR = $(TARGET_DIR)/lib/firmware

define AX_BITSTREAMS_INSTALL_TARGET_CMDS
	mkdir -p $(AX_BITSTREAMS_TARGET_DIR)
	$(INSTALL) -m 644 $(@D)/*.bit $(AX_BITSTREAMS_TARGET_DIR)
endef

define AX_BITSTREAMS_CLEAN_CMDS
	rm -rf $(AX_BITSTREAMS_TARGET_DIR)
endef

$(eval $(generic-package))
