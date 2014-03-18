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
from pyndn import ContentType
from pyndn import KeyLocatorType
from pyndn import Sha256WithRsaSignature

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


def dump(*list):
    result = ""
    for element in list:
        result += (element if type(element) is str else repr(element)) + " "
    print(result)

class RepoServer(object):
    def __init__(self, keyChain, certificateName):
        self._keyChain = keyChain
        self._certificateName = certificateName
        self.repo = Repo()

    def onInterest(self, prefix, interest, transport, registeredPrefixId):
        print 'Interest received: %s' % interest.getName().toUri()

        # Make and sign a Data packet.
        encoded_data = self.repo.extract_from_repo(interest)
        if not encoded_data:
            data = Data(interest.getName())
            content = "No match found"
            data.setContent(content)
            self._keyChain.sign(data, self._certificateName)
            encoded_data = data.wireEncode().toBuffer()
        else:
            dumpData(encoded_data)
            encoded_data = encoded_data.wireEncode().toBuffer()

        transport.send(encoded_data)
        print 'sent'

    def onRegisterFailed(self, prefix):
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

    while True: 
        face.processEvents()
        # We need to sleep for a few milliseconds so we don't use 100% of the CPU.
        time.sleep(0.01)

    face.shutdown()

if __name__ == '__main__':
    main()
