export THEOS ?= $(HOME)/theos

# sdk:deployment-target — build against iPhoneOS 9.3, target iOS 9.0.
TARGET := iphone:clang:9.3:9.0
ARCHS := armv7

include $(THEOS)/makefiles/common.mk

APPLICATION_NAME = IPadScreenH264

IPadScreenH264_FILES = main.m IPSViewController.m IPSSettingsPanel.m IPSDiscovery.m IPSCrypto.m StreamClient.m TurboDecoder.m IPSH264Renderer.m IPSRemoteControls.m
IPadScreenH264_FRAMEWORKS = UIKit CoreGraphics QuartzCore Security AVFoundation CoreMedia CoreVideo
IPadScreenH264_PRIVATE_FRAMEWORKS =

# No ARC: modern Command Line Tools don't ship `libarclite_iphoneos.a`,
# which clang requires for old deployment targets. Memory is managed by
# hand.
#
# libjpeg-turbo is prebuilt for armv7/NEON (under vendor/) and replaces
# ImageIO for decoding.
IPadScreenH264_CFLAGS = -fno-objc-arc -Wno-deprecated-declarations -O2 \
                    -Ivendor/libjpeg-turbo/include

# Recent Apple linkers emit a stub format (__picsymbolstub5, no lazy binding)
# that iOS 6's dyld doesn't understand: the app crashes at launch jumping to
# a bad address. The classic linker still produces the old format. Without
# it, the build still works but the app may not start; see the README.
LD_CLASSIC := $(shell xcrun -f ld-classic 2>/dev/null)

IPadScreenH264_LDFLAGS = -Lvendor/libjpeg-turbo/lib -ljpeg
ifneq ($(LD_CLASSIC),)
IPadScreenH264_LDFLAGS += -fuse-ld=$(LD_CLASSIC)
endif

include $(THEOS_MAKE_PATH)/application.mk

after-install::
	install.exec "uicache; killall -9 SpringBoard"
