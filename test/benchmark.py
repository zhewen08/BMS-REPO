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

from datetime import datetime
from sys import getsizeof

#def dump(*list):
#    result = ""
#    for element in list:
#        result += (element if type(element) is str else repr(element)) + " "
#    print(result)
#
#def dumpData(data):
#    dump("name:", data.getName().toUri())
#    if data.getContent().size() > 0:
#        # Use join to convert each byte to chr.
#        dump("content (raw):", "".join(map(chr, data.getContent().buf())))
#        dump("content (hex):", data.getContent().toHex())
#    else:
#        dump("content: <empty>")
#    if not data.getMetaInfo().getType() == ContentType.BLOB:
#        dump("metaInfo.type:",
#             "LINK" if data.getMetaInfo().getType() == ContentType.LINK
#             else "KEY" if data.getMetaInfo().getType() == ContentType.KEY
#             else "uknown")
#    dump("metaInfo.freshnessPeriod (milliseconds):",
#         data.getMetaInfo().getFreshnessPeriod()
#         if data.getMetaInfo().getFreshnessPeriod() >= 0 else "<none>")
#    dump("metaInfo.finalBlockID:",
#         data.getMetaInfo().getFinalBlockID().toEscapedString()
#         if data.getMetaInfo().getFinalBlockID().getValue().size() >= 0 
#         else "<none>")
#    signature = data.getSignature()
#    if type(signature) is Sha256WithRsaSignature:
#        dump("signature.signature:", 
#             "<none>" if signature.getSignature().size() == 0
#                      else signature.getSignature().toHex())
#        if signature.getKeyLocator().getType() != None:
#            if (signature.getKeyLocator().getType() == 
#                KeyLocatorType.KEY_LOCATOR_DIGEST):
#                dump("signature.keyLocator: KeyLocatorDigest:",
#                     signature.getKeyLocator().getKeyData().toHex())
#            elif signature.getKeyLocator().getType() == KeyLocatorType.KEYNAME:
#                dump("signature.keyLocator: KeyName:",
#                     signature.getKeyLocator().getKeyName().toUri())
#            else:
#                dump("signature.keyLocator: <unrecognized KeyLocatorType")
#        else:
#            dump("signature.keyLocator: <none>")


class BenchmarkRepo(object):

    def __init__(self, clear=False):
        self.repo = Repo(clear=clear)

    def benchmark_write(self):
        name = "/ndn/ucla.edu/bms/building:melnitz/room:1451/seg0"
        content = "melnitz.1451.seg0"
        data = self.repo.wrap_content(name, content)
        data_size = getsizeof(data)

        volume = 0
        start_time = datetime.now()
        for i in range(100):
            self.repo.add_content_object_to_repo(name, data)
            volume += data_size
        finish_time = datetime.now()
        duration = finish_time - start_time
        print duration, volume

    def benchmark_read(self):
        # the graph db is queried 2 times per read if does not 
        # apply selectors. otherwise 4 times queries are needed
        name = "/ndn/ucla.edu/bms/building:melnitz/room:1451/seg0"
        content = "melnitz.1451.seg0"
        interest = Interest(Name(name))
        data = self.repo.wrap_content(name, content)
        data_size = getsizeof(data)

        volume = 0
        start_time = datetime.now()
        for i in range(1):
            self.repo.extract_from_repo(interest)
            volume += data_size
        finish_time = datetime.now()
        duration = finish_time - start_time
        print duration, volume

    def run_benchmark(self):
#        self.benchmark_write()
        self.benchmark_read()

if __name__ == '__main__':
    benchmarker = BenchmarkRepo(clear=False)
    benchmarker.run_benchmark()
