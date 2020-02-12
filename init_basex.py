# -*- coding: utf-8 -*-
# This example shows how new documents can be added.
#
# Documentation: http://docs.basex.org/wiki/Clients
#
# (C) BaseX Team 2005-12, BSD License

from BaseXClient import BaseXClient

# create session
session = BaseXClient.Session('localhost', 1984, 'admin', 'admin')

f = open('phones.txt', 'r')
phones = f.readlines()
f.close()

fr = open('recipient.txt', 'r')
recipient = fr.readline().strip()
fr.close()

ph = ""

try:
    # create empty database
    session.execute("create db yowsup_log")
    print(session.info())

    for p in phones:
        ph += "<phone type='presence'>%s</phone>\n" % p.strip()

    ph += "<phone type='recipient'>%s</phone>\n" % recipient
    # add document
    session.add("/phones.xml", "<phones>\n%s</phones>\n" % ph )
    print(session.info())

    # run query on database
    print("\n" + session.execute("xquery collection('yowsup_log')"))

finally:
    # close session
    if session:
        session.close()
