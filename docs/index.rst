dls_pmaclib
===========================

dls_pmacremote
--------------

The dls_pmacremote.py module provides a mechanism for accessing a Delta-Tau PMAC or Geobrick over the ethernet or through a terminal server.

dls_pmcpreprocessor
-------------------

The dls_pmcpreprocessor.py module provides a class that pre-processes Delta-Tau 'pmc' files.

Installation
------------

This section describes how to install the module so you can try it out.
For Python modules this often looks like this::

    pip install dls_pmaclib

Use make and the python setuptools or distribute packages to produce a python egg.

To build and install simply type make && make install. Optionally modify the Makefile INSTALL_DIR and SCRIPT_DIR variables to define custom output directories. See comments in the Makefile.
