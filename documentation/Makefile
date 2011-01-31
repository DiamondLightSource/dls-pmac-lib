# this is the doxygen output dir
DOCDIR := doxygen

# this is the doxygen executable
DOXYGEN := /dls_sw/work/tools/RHEL5/bin/doxygen

# add the documentation files to the install target
all install: $(DOCDIR)

# rule for documentation
$(DOCDIR): config.cfg manual.src
	mkdir -p $(DOCDIR)
	$(DOXYGEN) config.cfg

# Remove entire documentation/doxygen dir on clean
clean:
	rm -rf $(DOCDIR
