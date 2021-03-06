DIRS = src 

INCLUDE=./include

include Makefile.inc

.PHONY: all $(DIRS) tests boost

all : $(DIRS)

$(DIRS) tests: boost
	$(MAKE) --directory $@

tests: src
	
boost:
	$(MAKE) --directory boost

clean : 
	rm -f build/*.o
	rm -f tests/Test_LogTest_Info
	rm -f tests/Test_LogTest_Warn
	rm -f tests/Test_LogTest_Error
	rm -f tests/Test_LogTest_OMGWTF
	rm -f tests/Test_Crosspoint
	
distclean : clean
	rm -f bin/Tarantula
	rm -f bin/libCasparTestApp
	rm -f bin/*.so
	$(MAKE) --directory boost clean

stripped : all
	strip --only-keep-debug $< -o $<.dbg
	strip $<
