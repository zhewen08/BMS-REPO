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

from repo import Repo
from pyndn import Name
from pyndn import Interest
from pyndn import Exclude
from pyndn import Data
from pyndn import ContentType
from pyndn import KeyLocatorType
from pyndn import Sha256WithRsaSignature

def dump(*list):
    result = ""
    for element in list:
        result += (element if type(element) is str else repr(element)) + " "
    print(result)

def dumpData(data):
    dump("name:", data.getName().toUri())
    if data.getContent().size() > 0:
        # Use join to convert each byte to chr.
        dump("content (raw):", "".join(map(chr, data.getContent().buf())))
        dump("content (hex):", data.getContent().toHex())
    else:
        dump("content: <empty>")
    if not data.getMetaInfo().getType() == ContentType.BLOB:
        dump("metaInfo.type:",
             "LINK" if data.getMetaInfo().getType() == ContentType.LINK
             else "KEY" if data.getMetaInfo().getType() == ContentType.KEY
             else "uknown")
    dump("metaInfo.freshnessPeriod (milliseconds):",
         data.getMetaInfo().getFreshnessPeriod()
         if data.getMetaInfo().getFreshnessPeriod() >= 0 else "<none>")
    dump("metaInfo.finalBlockID:",
         data.getMetaInfo().getFinalBlockID().toEscapedString()
         if data.getMetaInfo().getFinalBlockID().getValue().size() >= 0 
         else "<none>")
    signature = data.getSignature()
    if type(signature) is Sha256WithRsaSignature:
        dump("signature.signature:", 
             "<none>" if signature.getSignature().size() == 0
                      else signature.getSignature().toHex())
        if signature.getKeyLocator().getType() != None:
            if (signature.getKeyLocator().getType() == 
                KeyLocatorType.KEY_LOCATOR_DIGEST):
                dump("signature.keyLocator: KeyLocatorDigest:",
                     signature.getKeyLocator().getKeyData().toHex())
            elif signature.getKeyLocator().getType() == KeyLocatorType.KEYNAME:
                dump("signature.keyLocator: KeyName:",
                     signature.getKeyLocator().getKeyName().toUri())
            else:
                dump("signature.keyLocator: <unrecognized KeyLocatorType")
        else:
            dump("signature.keyLocator: <none>")


class TestRepo(object):

    def __init__(self, clear=False):
        self.repo = Repo(clear=clear)
#        self.repo.print_tree()
#        exit(0)

    def test_add_content_object_to_repo(self):
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
            data = self.repo.wrap_content(name, value)
            self.repo.add_content_object_to_repo(name, data)
#        self.repo.print_tree()
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
                "/ndn/ucla.edu/bms/building:melnitz/room:1451/seg1",
                ]
        values = [
                "melnitz.1451.seg0",
                "metlnitz.1451.seg0",
                "metlnitz.1451.seg1",
                ]
        for name, expected in zip(names, values):
            interest = Interest(Name(name))
            exclude = Exclude()
            exclude.appendComponent('room:1451')
            interest.setExclude(exclude)
            interest.setChildSelector(0)
            data = self.repo.extract_from_repo(interest, wired=False)
            if data:
                dumpData(data)
        print "test_extract_from_repo succeeded"

    def run_tests(self):
        self.test_add_content_object_to_repo()
        self.test_extract_from_repo()

if __name__ == '__main__':
#    tests = TestRepo(clear=True)
#    tests.run_tests()
    tests = TestRepo(clear=False)
    tests.run_tests()
