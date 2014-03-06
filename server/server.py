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


import time
from pyndn import Name
from pyndn import Data
from pyndn import Face
from pyndn.security import KeyType
from pyndn.security import KeyChain
from pyndn.security.identity import IdentityManager
from pyndn.security.identity import MemoryIdentityStorage
from pyndn.security.identity import MemoryPrivateKeyStorage
from pyndn.util import Blob

from default_key import DEFAULT_PUBLIC_KEY_DER
from default_key import DEFAULT_PRIVATE_KEY_DER

from repo import Repo

def dump(*list):
    result = ""
    for element in list:
        result += (element if type(element) is str else repr(element)) + " "
    print(result)

class RepoServer(object):
    def __init__(self, keyChain, certificateName):
        self._keyChain = keyChain
        self._certificateName = certificateName
        self._responseCount = 0
        self.repo = Repo()

    def onInterest(self, prefix, interest, transport, registeredPrefixId):
        print 'Interest received: %s' % interest.getName().toUri()
        self._responseCount += 1

        # Make and sign a Data packet.
        encoded_data = self.repo.extract_from_repo(interest)
        if not encoded_data:
            data = Data(interest.getName())
            content = "No match found"
            data.setContent(content)
            self._keyChain.sign(data, self._certificateName)
            encoded_data = data.wireEncode().toBuffer()

        transport.send(encoded_data)
        print 'sent'

    def onRegisterFailed(self, prefix):
        self._responseCount += 1
        dump("Register failed for prefix", prefix.toUri())

def main():
    face = Face("localhost")

    identityStorage = MemoryIdentityStorage()
    privateKeyStorage = MemoryPrivateKeyStorage()
    keyChain = KeyChain(
      IdentityManager(identityStorage, privateKeyStorage), None)
    keyChain.setFace(face)

    # Initialize the storage.
    keyName = Name("/testname/DSK-reposerver")
    certificateName = keyName.getSubName(0, keyName.size() - 1).append(
      "KEY").append(keyName[-1]).append("ID-CERT").append("0")
    identityStorage.addKey(keyName, KeyType.RSA, Blob(DEFAULT_PUBLIC_KEY_DER))
    privateKeyStorage.setKeyPairForKeyName(
      keyName, DEFAULT_PUBLIC_KEY_DER, DEFAULT_PRIVATE_KEY_DER)

    echo = RepoServer(keyChain, certificateName)
    prefix = Name("/ndn/ucla.edu/bms")
    dump("Register prefix", prefix.toUri())
    face.registerPrefix(prefix, echo.onInterest, echo.onRegisterFailed)

    while echo._responseCount < 100:
        face.processEvents()
        # We need to sleep for a few milliseconds so we don't use 100% of the CPU.
        time.sleep(0.01)

    face.shutdown()

if __name__ == '__main__':
    main()
