#!/usr/bin/python

# Copyright (c) 2014 University of California, Los Angeles
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation;
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# Author: Zhe Wen <wenzhe@cs.ucla.edu>

# REPO server

import os
import sys
sys.path.append(os.path.abspath('..'))

import unittest

from lib.repo import Repo
from pyndn import NDN, Name, ContentObject, Face

class RepoServer(object):

    def __init__(self, base_name=Name('/ndn/ucla.edu'), clear=False):
        self.face = Face()
        self.face.setInterestFilter(base_name, self.on_interest)
        self.repo = Repo(clear=clear)

    def on_interest(self, interest):
        """
        supports insertion to, extraction from, and deletion from repo
        """
        # TODO: determine expected operation by interest name
        # extraction
        co = self.repo.extract_from_repo(interest)
        if not type(co) == ContentObject:
            # wrap the co here
        self.face.put(co)


class Client(object):

    def __init__(self):
        self.face = Face()
        self.express_interest('/ndn/ucla.edu/building:melnitz/room:1451/seg0')

    def express_interest(self, name):
        self.expressInterest(name, self.on_data, self.on_timeout)

    def on_data(self, interest, data):
        print data

    def on_timeout(self, interest):
        print "Timed out: %s" % repr(interest)

    def set_event_loop(self, event_loop):
        self.event_loop = event_loop

class Test(unittest.TestCase):
    def test_request_from_repo(self):
        server = RepoServer()
        client = Client()

        event_loop = 

