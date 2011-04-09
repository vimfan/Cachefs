#VPATH    = src include
GMOCK_PATH = ../vendors/gmock-1.5.0
GMOCK_INCLUDE = $(GMOCK_PATH)/include
GTEST_INCLUDE = $(GMOCK_PATH)/gtest/include

INCLUDE_DIR = ../include
BOOST_INCLUDE = $(INCLUDE_DIR)/boost
STD_INCLUDE = $(INCLUDE_DIR)/std

CFLAGS = -I$(BOOST_INCLUDE) -I$(STD_INCLUDE) -g
LDFLAGS = 
UT_CFLAGS = -I$(BOOST_INCLUDE) -I$(GMOCK_INCLUDE) -I$(GTEST_INCLUDE) 
UT_LDFLAGS = $(GMOCK_PATH)/lib/libgmock.a -lpthread

CC = /home/seba/clang+llvm-2.8-i686-linux/bin/clang++
BUILD_DIR = ./build
UT_DIR = $(BUILD_DIR)/test

RUN_IF_POSSIBLE = no

PRECOMPILED = -H

ifdef RUN
	RUN_IF_POSSIBLE = yes 
endif

ifeq ($(CC), g++)
	#PRECOMPILED=-H -include precompiled.hpp 
	PRECOMPILED=
endif 

SOURCES  = $(shell ls *.cpp)

param_needed:
	echo "INVOKE WITH PARAMS, LIKE: make Something.exe, where Something.cpp shall have main() defined" > /dev/null

all: $(shell ls -1 *.cpp | sed -e 's/\.cpp/\.exe/')

%.exe: %.cpp
	mkdir -p $(BUILD_DIR)
	$(CC) $(PRECOMPILED) $(CFLAGS) $(LDFLAGS) $(subst .d,.cpp, $<)  -o $(BUILD_DIR)/$@

%test: %test.cpp
	mkdir -p $(UT_DIR)
	$(CC) $(UT_CFLAGS) $< $(UT_LDFLAGS) -o $(UT_DIR)/$@

precompile: precompiled.hpp
	$(CC) $(CFLAGS) $<

#include $(subst .cpp,.d,$(SOURCES))

%.d: %.cpp
	$(CC) -M $(CPPFLAGS) $< > $@.$$$$;                      \
	sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' < $@.$$$$ > $@;     \
	rm -f $@.$$$$

clean: 
	find . -name "*.o" -o -name "*.d" -o -name "*.exe" -print0 | xargs --null rm
