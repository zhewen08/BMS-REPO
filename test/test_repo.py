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

# REPO prototype on Neo4J unit tests

import os
import sys
sys.path.append(os.path.abspath('..'))


from lib.repo import Repo
from pyndn import Name, Interest

class TestRepo(object):

    def __init__(self, clear=False):
        self.repo = Repo(clear=clear)

    def test_add_to_repo(self):
        names = [
                "/ndn/ucla.edu/bms/building:melnitz/room:1451/seg0",
                "/ndn/ucla.edu/bms/building:melnitz/room:1451/seg1",
                "/ndn/ucla.edu/bms/building:strathmore/room:1221/seg0",
                "/ndn/ucla.edu/bms/building:melnitz/room:1453/seg0",
                ]
        values = [
                "melnitz.1451.seg0",
                "metlnitz.1451.seg1",
                "melnitz.1453.seg0",
                "strathmore.1221.seg0",
                ]
        for name, value in zip(names, values):
            try:
                self.repo.add_to_repo(name, value)
            except Exception as ex:
                print "test_add_to_repo failed: %s" % str(ex)
                return
        print "test_add_to_repo succeeded"

    def test_extract_from_repo(self):
#        names = [
#                "/ndn/ucla.edu/bms/building:melnitz/room:1451/seg0",
#                "/ndn/ucla.edu/bms/building:melnitz/room:1451/seg1",
#                "/ndn/ucla.edu/bms/building:strathmore/room:1221/seg0",
#                "/ndn/ucla.edu/bms/building:melnitz/room:1453/seg0",
#                ]
#        values = [
#                "melnitz.1451.seg0",
#                "metlnitz.1451.seg1",
#                "melnitz.1453.seg0",
#                "strathmore.1221.seg0",
#                ]
        names = [
                "/ndn/ucla.edu/bms/building:melnitz",
                "/ndn/ucla.edu/bms/building:melnitz/room:1451",
                ]
        values = [
                "melnitz.1451.seg0",
                "metlnitz.1451.seg1",
                ]
        for name, expected in zip(names, values):
            try:
                interest = Interest(Name(name))
                co = self.repo.extract_from_repo(interest)
            except Exception as ex:
                print "test_extract_from_repo failed: %s" % str(ex)
                return
            else:
#                if co.content != expected:
#                    print "test_extract_from_repo failed: wrong content"
#                    return
        print "test_extract_from_repo succeeded"

    def run_tests(self):
        self.test_add_to_repo()
        self.test_extract_from_repo()

if __name__ == '__main__':
    tests = TestRepo()
    tests.run_tests()
