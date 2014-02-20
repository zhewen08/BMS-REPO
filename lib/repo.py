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

from pyndn import NDN, Name, Interest, ContentObject, SignedInfo, Key, \
        KeyLocator
from pyndn import _pyndn
import pyndn

from repo_exceptions import AddToRepoException, NoRootException, \
        UnsupportedQueryException

import os
import pickle
import base64

LABEL_COMPONENT = "Component"
LABEL_SEGMENT = "Segment"

PROPERTY_COMPONENT = "component"
PROPERTY_DATA = "file"
PROPERTY_WRAPPED = "wrapped"

RELATION_C2C = "CONTAINS_COMPONENT"
RELATION_C2S = "CONTAINS_SEGMENT"

MIN_SUFFIX_COMPS = 0
MAX_SUFFIX_COMPS = 63

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

        if data:
            # any node is supposed to have AT MOST one RELATION_C2S
            rel = 'r%d:%s' % (i, RELATION_C2S)
            node = 'n%d:%s {%s:"%s", %s:"%s"}' % (i, LABEL_SEGMENT, 
                    PROPERTY_DATA, data, PROPERTY_WRAPPED, wrapped)
            path.append(rel)
            path.append(node)

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
                query = 'START s=node({%s})\n' % start + \
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
        path = self.name_to_path(name, data, wrapped)

        try:
            query = self.create_path_query(path, 'CREATE UNIQUE')
        except UnsupportedQueryException as ex:
            raise AddToRepoException(str(ex))
        results = neo4j.CypherQuery(self.db_handler, query).execute()

    # TODO: simpler version of add_to_repo
    # insert a content object to repo under given name
    def add_content_object_to_repo(self, name, co):
        """
        @param name - name of the content object
        @param co - wire format content object to be inserted
        encodes the given wire format content object and add it to the graph
        database
        """
        name = str(Name(name))
        data = base64.b64encode(co)
        try:
            self.add_to_graphdb(name, data, wrapped=True)
        except AddToRepoException as ex:
            print "Error: add_content_object_to_repo: %s" % str(ex)



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
            binary_data = _pyndn.dump_charbuf(co.ndn_data)
            data = base64.b64encode(binary_data)
        else:
            data = content
#        # create a leaf node containing the path to the content object, 
#        # which itself will be stored in the filesystem as a file
#        # use md5 digest of name as file name
#        try:
#            data_ref = self.save_to_disk(name, data)
#        except AddToRepoException as ex:
#            print "Error: add_to_repo: %s" % str(ex)
#        else:
#            try:
#                self.add_to_graphdb(name, data_ref, wrapped)
#            except AddToRepoException as ex:
#                print "Error: add_to_repo: %s" % str(ex)
        try:
            self.add_to_graphdb(name, data, wrapped)
        except AddToRepoException as ex:
            print "Error: add_to_repo: %s" % str(ex)


    def read_from_disk(self, segment_node):
        """
        @param segment_node - the node contains (a reference) to the segment
        @return data the node contains (either from property or reference disk)
        reads the segment (co or raw data) from node
        """
        file_name = segment_node.get_properties()[PROPERTY_DATA]
        with open(os.path.join(self._PATH, file_name)) as fd:
            # return fd.read()
            return pickle.load(fd)

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

        leading_any = exclude[1] if exclude[0] == 'Any' else None
        trailing_any = exclude[-2] if exclude[-1] == 'Any' else None
        for i in range(1, len(exclude) - 1):
            if exclude[i] == 'Any':
                inbetween_any.append(exclude[i-1], exclude[i+1])

        def should_exclude(node, exclude=exclude, leading=leading_any, 
                trailing=trailing_any, inbetween=inbetween_any):
            comp = Name(node.get_properties()[PROPERTY_COMPONENT])
            # assert @exclude is a list of Name objects
            if comp in exclude:
                return True
            if leading and comp <= leading:
                return True
            if trailing and  comp >= trailing:
                return True
            for pair in inbetween:
                if comp >= pair[0] and comp <= pair[1]:
                    return True
            return False

        nodes = []
        for node in _nodes:
            if not should_exclude(node):
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
            return None
        if len(nodes) == 1:
            return nodes[0]
        if not child_selector:
            return nodes
        nodes_sorted = sorted(nodes, 
                key=lambda x:Name('/' + \
                str(x.get_properties()[PROPERTY_COMPONENT])))
        return [nodes_sorted[0]] if child_selector == 0 else [nodes_sorted[-1]]

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
                'MATCH (s)-[:%s*%d..%d]->(m)\n' % (RELATION_C2C, 
                        min_suffix_components, max_suffix_components) + \
                'WHERE has(m.%s)' % PROPERTY_COMPONENT + \
                'RETURN (m)'
        records = neo4j.CypherQuery(self.db_handler, query).execute()
        nodes = [record.values[0] for record in records.data]

        return nodes

    def locate_last_node(self, name):
        """
        @param interest - the interest that contains the name prefix
        @return the node found according to the prefix
        """
        name = str(name)
        path = self.name_to_path(name)
        # create a cypher query to match the path
        try:
            query = self.create_path_query(path, 'MATCH')
        except UnsupportedQueryException as ex:
            print 'Error: extract_from_repo: %s' % str(ex)

        records = neo4j.CypherQuery(self.db_handler, query).execute()
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
        # Exclude
        # FIXME: assume interest.exclude is a list of components
        # FIXME: need to test
        nodes_exclude = self.apply_exclude(last_node, interest.exclude)
        if not nodes_exclude:
            # no match found
            return None

        # ChildSelector
        # FIXME: can be applied for the immediate next component following
        # the given prefix only? or until find a co?
        # FIXME: need to comply with other selectors? e.g. leftmost child is
        # a co (interest asks for leftmost child), but the interest also asks
        # for min_suffix_components = 1
        nodes_child = self.apply_child_selector(nodes_exclude, 
                interest.childSelector)
        if not nodes_child:
            # no match found
            return None

        # MinSuffixComponents
        nodes_suffix = self.apply_min_max_suffix_components(nodes_child, 
                interest.minSuffixComponents, interest.maxSuffixComponents)
        if not nodes_suffix:
            # no match found
            return None

        # MustBeFresh - test against a co
        # ignored in REPO

        # PublisherPublicKeyLocator - test against a co
        # compares KeyLocator in interest against that in co
        # FIXME: need PyNDN2
        # TODO: select from nodes_suffix

        # TODO: need a default way to select if cannot decide with the selectors

        nodes_suffix.sort(
                key=lambda x:Name('/' + \
                str(x.get_properties()[PROPERTY_COMPONENT])))

        return nodes_suffix

    def extract_from_repo(self, interest, wired=False):
        """
        @param interest - the interest requesting a content object
        @param wired - whether to return the wired format co
        @return the requested content object in wired format. if does not 
        exist return None
        """
        # find last node according to given name prefix
        last_node = self.locate_last_node(interest.name)

        # apply selectors here. AT MOST one node shall be left 
        nodes = self.apply_selectors(last_node, interest)
        final_node = nodes[0]

        try:
            # by design, there is AT MOST one C2S relation for each node
            rel = final_node.match(RELATION_C2S).next()
            # we found a content object under the exact given name
            segment_node = rel.end_node
            wrapped = eval(segment_node.get_properties()[PROPERTY_WRAPPED])
#            data = self.read_from_disk(segment_node)
            data = segment_node.get_properties()[PROPERTY_DATA]
            if wrapped and not wired:
                # decode wired co to ContentObject instance
                co = base64.b64decode(data)
                return co
            else:
                # return either wired format co or raw data
                return data
        except StopIteration as ex:
            pass

    @staticmethod
    def parse_co_name(cmd_interest_name):
        """
        @param cmd_interest_name - name contained in the command interest
        @return Name() instance of the co's name
        parses the command interest name for the name prefix of the co
        """
        _name = str(cmd_interest_name)
        assert('delete' in _name)
        try:
            _co_name = _name.split('delete')[2]
        except Exception as ex:
            print 'parse_co_name: %s' % str(ex)
        assert(_co_name)
        co_name = Name(_co_name)
        return co_name

    def delete_from_repo(self, interest)
        """
        @param interest - command interest that requests deletion
        deletes content objects either by precise name, or by prefix plus
        selectors
        """
        # TODO: test this function
        co_name = self.parse_co_name(interest.name)

        # by name prefix
        # by interest
        # find last node according to given name prefix
        last_node = self.locate_last_node(co_name)

        # apply selectors here. AT MOST one node shall be left 
        nodes = self.apply_selectors(last_node, interest)

        if nodes:
            _ids = []
            for node in nodes:
                _ids.append(str(node._id))
            ids = ','.join(_ids)
            query = 'START s=node(%s)\n' % ids + \
                    'MATCH (s)-[r]->()\n' + \
                    'DELETE s, r'
            records = neo4j.CypherQuery(self.db_handler, query).execute()
