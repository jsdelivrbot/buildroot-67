#############################################################
#
# ax-smil
#
#############################################################

AX_SMIL_VERSION=0.11
AX_SMIL_SITE=git@git.axent.com.au:axent-smil-player/axent_smil_cpp.git
AX_SMIL_SITE_METHOD=git
AX_SMIL_INSTALL_STAGING=YES
AX_SMIL_INSTALL_TARGET=YES
AX_SMIL_CONF_OPT=-DBACKEND_FBDEV=ON -DBACKEND_SDL=OFF
AX_SMIL_DEPENDENCIES=pango cairo libxml2 jpeg libglib2 libcurl libungif gstreamer

$(eval $(call cmake-package))
