#############################################################
#
# fbc
#
#############################################################

FBC_VERSION:=d4345b73
FBC_SITE:=git://github.com/danieldyer/fbc.git

define FBC_BUILD_CMDS
	$(MAKE1) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define FBC_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 755 $(@D)/fbc $(TARGET_DIR)/usr/sbin/fbc
endef

define FBC_UNINSTALL_TARGET_CMDS
	rm -f $(TARGET_DIR)/usr/sbin/fbc
endef

define FBC_CLEAN_CMDS
	-$(MAKE) -C $(@D) clean
endef

$(eval $(generic-package))
