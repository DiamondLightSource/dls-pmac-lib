from dls_pmaclib.dls_pmacremote import PmacEthernetInterface

pmac1 = PmacEthernetInterface(verbose=True)
pmac1.setConnectionParams("172.23.240.97", 1025)
pmac1.connect()
