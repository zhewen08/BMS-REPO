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

# REPO prototype on Neo4J


from py2neo import neo4j, cypher
from hashlib import md5

from pyndn import NDN, Name, Interest, ContentObject, SignedInfo, Key, KeyLocator
from pyndn import _pyndn
import pyndn

from repo_exceptions import AddToRepoException, NoRootException, \
        UnsupportedQueryException

import os
import pickle

LABEL_COMPONENT = "Component"
LABEL_SEGMENT = "Segment"

PROPERTY_COMPONENT = "component"
PROPERTY_DATA = "file"
PROPERTY_WRAPPED = "wrapped"

RELATION_C2C = "CONTAINS_COMPONENT"
RELATION_C2S = "CONTAINS_SEGMENT"


class Repo(object):
    # default object path
    _PATH = "/var/NDN/REPO"
    # default key
    _key = Key()
    # FIXME: will report _pyndn.NDNError: Failed to initialize keystore (-1)
    # when calling NDN().getDefaultKey()
    # _key = NDN().getDefaultKey()
    _key.generateRSA(1024)
    # _key_locator = KeyLocator(_key)

    def __init__(self, server=None, port=None, db=None, clear=False):
        if not server:
            self._server = "localhost"
        if not port:
            self._port = 7474
        if not db:
            self._db = "/db/data/"

        self._URI = "http://%s:%d%s" % (self._server, self._port, self._db)
        self.db_handler = neo4j.GraphDatabaseService(self._URI)

        if clear:
            self.db_handler.clear()

        try:
            self.check_or_create_root()
        except NoRootException as ex:
            print "Error: __init__: %s" % str(ex)

    def check_or_create_root(self):
        """
        checks or creates the root node in graph database, which is
        (:Component {component:"ndn"})
        """
        self.root = self.db_handler.get_or_create_indexed_node("root", 
                "root_name", "ndn", {"component":"ndn"})
        if not self.root:
            raise NoRootException("cannot locate root name (ndn)")

        self.root.add_labels(LABEL_COMPONENT)

    def wrap_content(self, name, content, key=None, key_locator=None):
        """
        @param name - name of the data
        @param content - data to be wrapped
        @param key - key used to sign the data
        @return the content object created
        wraps the given name and content into a content object
        """
        co = ContentObject()
        co.name = Name(name)
        co.content = content

        if not key:
            key = self._key
            # key_locator = self._key_locator

        si = SignedInfo()
        si.publisherPublicKeyDigest = key.publicKeyID
        si.type = pyndn.CONTENT_DATA
        si.freshnessSeconds = -1
        # si.keyLocator = key_locator
        co.signedInfo = si

        co.sign(key)

        return co

    def save_to_disk(self, name, data):
        """
        @param name - string representation of ndn name
        @param data - data to be stored
        @return the file name of data on disk
        writes given data to disk under the md5 digest of its name
        """
        file_name = md5(name).hexdigest()
        try:
            with open(os.path.join(self._PATH, file_name), "wb") as fd:
                # fd.write(data)
                pickle.dump(data, fd)
        except Exception as ex:
            raise AddToRepoException(ex)

        return file_name

    def name_to_path(self, name, data=None, wrapped=True):
        """
        @param name - string representation of a ndn name
        @param data - data to be stored in node
        @param wrapped - whether the data is wrapped as a co
        @return list representation of this name using nodes and relations
        interprets the given string name into a list of nodes and relations
        """
        components = name.split('/')
        components = components[1:]
        if components[0] != "ndn":
            raise AddToRepoException("wrong root component")

        path = []
        i = 0
        for comp in components:
            if comp == "ndn":
                continue
            rel = 'r%d:%s' % (i, RELATION_C2C)
            node = 'n%d:%s {%s:"%s"}' % (i, LABEL_COMPONENT, 
                    PROPERTY_COMPONENT, comp)
            path.append(rel)
            path.append(node)
            i += 1

        if data:
            # any node is supposed to have AT MOST one RELATION_C2S
            rel = 'r%d:%s' % (i, RELATION_C2S)
            node = 'n%d:%s {%s:"%s", %s:"%s"}' % (i, LABEL_SEGMENT, 
                    PROPERTY_DATA, data, PROPERTY_WRAPPED, wrapped)
            path.append(rel)
            path.append(node)

        return path

    @staticmethod
    def create_path_query(path, action):
        """
        @param path - list of path nodes and relations
        @param action - action of the query, could be "MATCH" or 
                        "CREATE UNIQUE"
        @return the query
        creates a path query starting from root ("ndn")
        """
        supported_actions = ['MATCH', 'CREATE UNIQUE']
        if action.upper() in supported_actions:
            query = 'START r=node:root(root_name = "ndn")\n' +\
                    '%s (r)' % action.upper()
        else:
            raise UnsupportedQueryException("unsupported query")

        assert(len(path) % 2 == 0)
        path_len = len(path) / 2
        items = ['-[%s]->(%s)'] * path_len
        query += ''.join(items)
        query = query % tuple(path)
        query += ' \nRETURN (%s)' % path[-1].split(':')[0]

        return query

    def add_to_graphdb(self, name, data, wrapped):
        """
        @param name - name of a given content object
        @param data - data to store under name
        adds a record describing the name and its co (on disk) to graphdb
        """
        path = self.name_to_path(name, data, wrapped)

        try:
            query = self.create_path_query(path, 'CREATE UNIQUE')
        except UnsupportedQueryException as ex:
            raise AddToRepoException(str(ex))
        results = neo4j.CypherQuery(self.db_handler, query).execute()

    def add_to_repo(self, name, content, wrapped=True):
        """
        @param name - name of the content object
        @param content - the content to be wrapped and added
        @param wrap - whether to wrap name+content into a co
        (wraps the given content into a content object and) adds it
        to the graph database under the specified name
        """
        name = str(Name(name))
        if wrapped:
            co = self.wrap_content(name, content)
            # data = _pyndn.dump_charbuf(co.ndn_data)
            data = repr(co)
        else:
            data = content
        # create a leaf node containing the path to the content object, 
        # which itself will be stored in the filesystem as a file
        # use md5 digest of name as file name
        try:
            data_ref = self.save_to_disk(name, data)
        except AddToRepoException as ex:
            print "Error: add_to_repo: %s" % str(ex)
        else:
            try:
                self.add_to_graphdb(name, data_ref, wrapped)
            except AddToRepoException as ex:
                print "Error: add_to_repo: %s" % str(ex)

    def read_from_disk(self, segment_node):
        file_name = segment_node.get_properties()[PROPERTY_DATA]
        with open(os.path.join(self._PATH, file_name)) as fd:
            # return fd.read()
            return pickle.load(fd)

    def extract_from_repo(self, interest, wired=False):
        """
        @param interest - the interest requesting a content object
        @param wired - whether to return the wired format co
        @return the requested content object in wired format. if does not 
        exist return None
        searches and returns the repo for content object to fulfill the 
        interest
        """
        name = str(interest.name)
        path = self.name_to_path(name)
        # create a cypher query to match the path
        try:
            query = self.create_path_query(path, 'MATCH')
        except UnsupportedQueryException as ex:
            print 'Error: extract_from_repo: %s' % str(ex)

        records = neo4j.CypherQuery(self.db_handler, query).execute()
        # in the name tree there should be AT MOST one match for a 
        # given name prefix
        assert(len(records.data) <= 1)
        if (len(records.data) == 0):
            return None

        last_node = records.data[0].values[0]

        # TODO: apply selectors here. AT MOST one node shall be left 


        try:
            # by design, there is AT MOST one C2S relation for each node
            rel = last_node.match(RELATION_C2S).next()
            # we found a content object under the exact given name
            segment_node = rel.end_node
            wrapped = eval(segment_node.get_properties()[PROPERTY_WRAPPED])
            data = self.read_from_disk(segment_node)
            if wrapped and not wired:
                # decode wired co to ContentObject instance
                co = eval(data)
                return co
            else:
                # return either wired format co or raw data
                return data
        except StopIteration as ex:
            pass
