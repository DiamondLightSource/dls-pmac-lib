# DLS environment settings
PREFIX = /dls_sw/prod/tools/RHEL5
PYTHON = $(PREFIX)/bin/python2.6
INSTALL_DIR = /dls_sw/work/common/python/test/packages
SCRIPT_DIR = /dls_sw/work/common/python/test/scripts
PYUIC=$(PREFIX)/bin/pyuic4

## Mac OS X settings.
#PYTHON = python2.6
#INSTALL_DIR = /Users/ulrik/python/install/packages
#SCRIPT_DIR = /Users/ulrik/python/install/scripts

## Ubuntu settings
#PYTHON = python
#INSTALL_DIR = /home/ulrik/python/install/packages
#SCRIPT_DIR = /home/ulrik/python/install/scripts

MODULEVER = 1.4

# Override with any release info
-include Makefile.private

# This is run when we type make
# It can depend on other targets e.g. the .py files produced by pyuic4 
dist: setup.py $(wildcard dls_pmaclib/*.py)
	MODULEVER=$(MODULEVER) $(PYTHON) setup.py bdist_egg
	touch dist
	$(MAKE) -C documentation 

# Clean the module
clean:
	$(PYTHON) setup.py clean
	-rm -rf build dist *egg-info installed.files
	-find -name '*.pyc' -exec rm {} \;
	$(MAKE) -C documentation clean

# Install the built egg and keep track of what was installed
install: dist
	$(PYTHON) setup.py easy_install -m \
		--record=installed.files \
		--install-dir=$(INSTALL_DIR) \
		--script-dir=$(SCRIPT_DIR) dist/*.egg        
