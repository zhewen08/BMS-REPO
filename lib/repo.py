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

from pyndn import Name
from pyndn import Exclude
from pyndn import Data
from pyndn import ContentType
from pyndn import KeyLocatorType
from pyndn import Sha256WithRsaSignature
from pyndn.security import KeyType
from pyndn.security import KeyChain
from pyndn.security.identity import IdentityManager
from pyndn.security.identity import MemoryIdentityStorage
from pyndn.security.identity import MemoryPrivateKeyStorage
from pyndn.util import Blob
from pyndn.util import SignedBlob

from default_key import DEFAULT_PUBLIC_KEY_DER
from default_key import DEFAULT_PRIVATE_KEY_DER
from repo_exceptions import AddToRepoException, NoRootException, \
        UnsupportedQueryException

import os
import base64

LABEL_COMPONENT = "Component"
LABEL_SEGMENT = "Segment"

PROPERTY_COMPONENT = "component"
PROPERTY_DATA = "data"
PROPERTY_LEAF = "leaf"
PROPERTY_WRAPPED = "wrapped"

RELATION_C2C = "CONTAINS_COMPONENT"
RELATION_C2S = "CONTAINS_SEGMENT"

MIN_SUFFIX_COMPS = 0
MAX_SUFFIX_COMPS = 63


class Repo(object):
    # default object path
    _PATH = "/var/NDN/REPO"

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

    def print_tree(self, root=None, level=0):
        """
        prints the repo content in tree style
        """
        if not root:
            root = self.root

        for lv in range(level):
            print '  ',
        try:
            print root.get_properties()
        except Exception as ex:
            print 'data: %s' % repr(root.get_properties())

        query = 'START s=node(%s)\n' % root._id +\
                'MATCH (s)-[r]->(c)\n' + \
                'RETURN c'
        records = neo4j.CypherQuery(self.db_handler, query).execute()

        nodes = [record.values[0] for record in records.data]
        for node in nodes:
            self.print_tree(node, level + 1)

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
        co = Data(Name(name))
        co.setContent(content)
        co.getMetaInfo().setFreshnessPeriod(5000)
        co.getMetaInfo().setFinalBlockID(Name("/%00%09")[0])

        identityStorage = MemoryIdentityStorage()
        privateKeyStorage = MemoryPrivateKeyStorage()
        identityManager = IdentityManager(identityStorage, privateKeyStorage)
        keyChain = KeyChain(identityManager, None)

        # Initialize the storage.
        keyName = Name("/ndn/bms/DSK-default")
        certificateName = keyName.getSubName(0, keyName.size() - 1).append(
                "KEY").append(keyName[-1]).append("ID-CERT").append("0")
        identityStorage.addKey(keyName, KeyType.RSA, Blob(DEFAULT_PUBLIC_KEY_DER))
        privateKeyStorage.setKeyPairForKeyName(keyName, DEFAULT_PUBLIC_KEY_DER, 
                DEFAULT_PRIVATE_KEY_DER)

        keyChain.sign(co, certificateName)

        _data = co.wireEncode()

        return _data.toRawStr()

    def name_to_path(self, name, wrapped=True):
        """
        @param name - string representation of a ndn name
        @param data - data to be stored in node
        @param wrapped - whether the data is wrapped as a co
        @return list representation of this name using nodes and relations
        interprets the given string name into a list of nodes and relations
        the first component in name, which is considered the start node,  will
        be omitted in returned list
        """
        components = name.split('/')
        if name[0] == '/':
            components = components[1:]
        components = components[1:]

        path = []
        i = 0
        for comp in components:
            rel = 'r%d:%s' % (i, RELATION_C2C)
            if comp == 'ANY':
                # use special symbol 'ANY' to refer to nodes with no property
                node = 'n%d:%s' % (i, LABEL_COMPONENT)
            else:
                node = 'n%d:%s {%s:"%s"}' % (i, LABEL_COMPONENT, 
                        PROPERTY_COMPONENT, comp)
            path.append(rel)
            path.append(node)
            i += 1

        return path

    @staticmethod
    def create_path_query(path, action, start=None):
        """
        @param path - list of path nodes and relations
        @param action - action of the query, could be "MATCH" or 
                        "CREATE UNIQUE"
        @param start - internal _id of start node
        @return the query
        creates a path query starting from root ("ndn")
        """
        supported_actions = ['MATCH', 'CREATE UNIQUE']
        if action.upper() in supported_actions:
            if not start:
                query = 'START r=node:root(root_name = "ndn")\n' +\
                        '%s (r)' % action.upper()
            else:
                query = 'START s=node(%s)\n' % start + \
                        '%s (s)' % action.upper()
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
        data = base64.b64encode(data)
        path = self.name_to_path(name, wrapped=wrapped)

        try:
            query = self.create_path_query(path, 'CREATE UNIQUE')
        except UnsupportedQueryException as ex:
            raise AddToRepoException(str(ex))
        records = neo4j.CypherQuery(self.db_handler, query).execute()

        leaf_node = records.data[0][0]
        query = 'START s=node(%s)\n' % leaf_node._id + \
                'MATCH (s)-[r:%s]->(c)\n' % RELATION_C2S + \
                'RETURN c'
        records = neo4j.CypherQuery(self.db_handler, query).execute()
        if not records:
            # create segment node for data
            rel = 'r:%s' % RELATION_C2S
            node = 'c:%s {%s:"%s", %s:"%s"}' % (LABEL_SEGMENT, 
                    PROPERTY_DATA, data,
                    PROPERTY_WRAPPED, wrapped)
            query = 'START s=node(%s)\n' % leaf_node._id + \
                    'CREATE (s)-[%s]->(%s)\n' % (rel, node) + \
                    'SET s.%s = "%s"\n' % (PROPERTY_LEAF, "True") + \
                    'RETURN c'
            records = neo4j.CypherQuery(self.db_handler, query).execute()
        else:
            seg_node = records.data[0][0]
            query = 'START c=node(%s)\n' % seg_node._id + \
                    'MATCH (c)\n' + \
                    'SET c.%s = "%s"\n' % (PROPERTY_DATA, data) + \
                    'RETURN c'
            records = neo4j.CypherQuery(self.db_handler, query).execute()

    # insert a content object to repo under given name
    def add_content_object_to_repo(self, name, co, wired=True):
        """
        @param name - name of the content object
        @param co - content obejct to be inserted
        @param wired - whether the co given is in wired format
        inserts a given co to the repo
        """
        name = Name(name).toUri()
        if not wired:
            data = co.wireEncode().toRawStr()
        else:
            data = co
        try:
            self.add_to_graphdb(name, data, wrapped=True)
        except AddToRepoException as ex:
            print "Error: add_content_object_to_repo: %s" % str(ex)

#    def add_to_repo(self, name, content, wrapped=True):
#        """
#        @param name - name of the content object
#        @param content - the content to be wrapped and added
#        @param wrap - whether to wrap name+content into a co
#        (wraps the given content into a content object and) adds it
#        to the graph database under the specified name
#        """
#        name = Name(name).toUri()
#        if wrapped:
#            data = self.wrap_content(name, content)
#        else:
#            data = content
#        try:
#            self.add_to_graphdb(name, data, wrapped)
#        except AddToRepoException as ex:
#            print "Error: add_to_repo: %s" % str(ex)

    def apply_exclude(self, last_node, exclude):
        """
        @param last_node - the node to start search from
        @param exlucde - exclude filter the interest contains
        @returns all nodes that fullfil the selector
        """
        _id = last_node._id
        query = 'START s=node(%s)\n' % _id + \
                'MATCH (s)-[:%s]->(m)\n' % (RELATION_C2C) + \
                'RETURN (m)'
        records = neo4j.CypherQuery(self.db_handler, query).execute()
        _nodes = [record.values[0] for record in records.data]

        if not exclude:
            return _nodes

        nodes = []
        for node in _nodes:
            name = Name()
            name.set(node.get_properties()[PROPERTY_COMPONENT])
            comp = name.get(0)
            if not exclude.matches(comp):
                nodes.append(node)

        return nodes

    def apply_child_selector(self, nodes, child_selector):
        """
        @param nodes - nodes to be selected from. should all come from the
        same level of components (e.g. what fullfil the exclude selector)
        @param child_selector - child selector from the interest
        @return one node if this selector exists and all nodes provided if
        this selector does not exist
        """
        if not nodes:
            return []

        nodes.sort(key=lambda x:Name('/' + \
                str(x.get_properties()[PROPERTY_COMPONENT])))
        nodes = [nodes[0]] if child_selector == 0 else [nodes[-1]]
        return nodes

    def apply_min_max_suffix_components(self, nodes, 
            min_suffix_components, max_suffix_components):
        """
        @param last_node - node from which to apply min suffix components
        @param min_suffix_components - min suffix components
        @param max_suffix_components - max suffix components
        @return a list of nodes that fulfill the selector requirement
        """
        if not min_suffix_components:
            min_suffix_components = MIN_SUFFIX_COMPS
        if not max_suffix_components:
            # virtually infinite
            max_suffix_components = MAX_SUFFIX_COMPS

        _ids = []
        for node in nodes:
            _ids.append(str(node._id))
        ids = ','.join(_ids)
        query = 'START s=node(%s)\n' % ids + \
                'MATCH (s)-[:%s*%d..%d]->(m:%s {%s:"True"})\n' % (
                RELATION_C2C, min_suffix_components, 
                max_suffix_components, LABEL_COMPONENT, PROPERTY_LEAF) + \
                'RETURN (m)'
        records = neo4j.CypherQuery(self.db_handler, query).execute()
        nodes = [record.values[0] for record in records.data]

        return nodes

    def extract_co_from_db(self, leaf_node, wired=True):
        try:
            # by design, there is AT MOST one C2S relation for each node
            query = 'START s=node(%s)\n' % leaf_node._id + \
                    'MATCH (s)-[r:%s]->(c)\n' % RELATION_C2S + \
                    'RETURN c'
            records = neo4j.CypherQuery(self.db_handler, query).execute()
            nodes = [record.values[0] for record in records.data]
            segment_node = nodes[0]

            properties = segment_node.get_properties()
            wrapped = eval(properties[PROPERTY_WRAPPED])
            _data = properties[PROPERTY_DATA]
            data = base64.b64decode(_data)
            # decode wired co to ContentObject instance
#            if not wired:
            co = Data()
            co.wireDecode(Blob.fromRawStr(data))
            return co
#            else:
#                return data
        except StopIteration as ex:
            return None


    def apply_key_locator(self, nodes, key_locator):
        """
        @param nodes - nodes to be checked
        @param key_locator - key locator given by the interest
        checks the given nodes for key locator
        """
        if not key_locator:
            return None

        _nodes = []
        for node in nodes:
            co = self.extract_co_from_db(node, wired=False)
            kl = co.getKeyLocator()

    def locate_last_node(self, name):
        """
        @param interest - the interest that contains the name prefix
        @return the node found according to the prefix
        """
        name = name.toUri()
        path = self.name_to_path(name)
        # create a cypher query to match the path
        try:
            query = self.create_path_query(path, 'MATCH')
        except UnsupportedQueryException as ex:
            print 'Error: extract_from_repo: %s' % str(ex)

        records = neo4j.CypherQuery(self.db_handler, query).execute()
        if not records:
            return None
        # in the name tree there should be AT MOST one match for a 
        # given name prefix
        assert(len(records.data) == 1)
        assert(len(records.data[0].values) == 1)
        last_node = records.data[0].values[0]

        return last_node

    def apply_selectors(self, last_node, interest):
        """
        @param last_node - starting node to apply the selectors
        @param interest - interest that contains the selectors
        @return all nodes that fulfill the selectors
        """
        exclude = interest.getExclude()
        child_selector = interest.getChildSelector()
        if exclude or child_selector:
            # Exclude
            nodes = self.apply_exclude(last_node, exclude)
            # ChildSelector
            nodes = self.apply_child_selector(nodes, child_selector)
        else:
            nodes = [last_node]

        if not nodes:
            return None

        # MinSuffixComponents
        nodes = self.apply_min_max_suffix_components(nodes, 
                interest.getMinSuffixComponents(), 
                interest.getMaxSuffixComponents())
        if not nodes:
            return None

        nodes.sort(
                key=lambda x:Name('/' + \
                str(x.get_properties()[PROPERTY_COMPONENT])))

        return nodes

    def extract_from_repo(self, interest, wired=True):
        """
        @param interest - the interest requesting a content object
        @param wired - whether to return the wired format co
        @return the requested content object in wired format. if does not 
        exist return None
        """
        # find last node according to given name prefix
        last_node = self.locate_last_node(interest.getName())
        if not last_node:
            return None

        # apply selectors here. AT MOST one node shall be left 
        nodes = self.apply_selectors(last_node, interest)
        if not nodes:
            return None

        # by default, return the first(by name) co
        final_node = nodes[0]

        co = self.extract_co_from_db(final_node, wired)
        return co

#    @staticmethod
#    def parse_co_name(cmd_interest_name):
#        """
#        @param cmd_interest_name - name contained in the command interest
#        @return Name() instance of the co's name
#        parses the command interest name for the name prefix of the co
#        """
#        _name = str(cmd_interest_name)
#        assert('delete' in _name)
#        try:
#            _co_name = _name.split('delete')[2]
#        except Exception as ex:
#            print 'parse_co_name: %s' % str(ex)
#        assert(_co_name)
#        co_name = Name(_co_name)
#        return co_name

    def delete_from_repo(self, interest):
        """
        @param interest - command interest that requests deletion
        deletes content objects either by precise name, or by prefix plus
        selectors
        """
#        co_name = self.parse_co_name(interest.getName())

        # by name prefix
        # by interest
        # find last node according to given name prefix
        last_node = self.locate_last_node(interest.getName())
        if not last_node:
            return None

        # apply selectors here. AT MOST one node shall be left 
        nodes = self.apply_selectors(last_node, interest)
        if not nodes:
            return None

        _ids = []
        for node in nodes:
            node.isolate()
            node.delete()
#            _ids.append(str(node._id))
#        ids = ','.join(_ids)
#
#        query = 'START s=node(%s)\n' % ids + \
#                'MATCH (s)-[r]->()\n' + \
#                'DELETE r\n' + \
#                'DELETE s'
#        print query
#        records = neo4j.CypherQuery(self.db_handler, query).execute()
