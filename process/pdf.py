#  Copyright 2011-2015 by Carnegie Mellon University
#
#  NO WARRANTY
#
#  THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING INSTITUTE
#  MATERIAL IS FURNISHED ON AN "AS-IS" BASIS.  CARNEGIE MELLON
#  UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR
#  IMPLIED, AS TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY
#  OF FITNESS FOR PURPOSE OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS
#  OBTAINED FROM USE OF THE MATERIAL.  CARNEGIE MELLON UNIVERSITY
#  DOES NOT MAKE ANY WARRANTY OF ANY KIND WITH RESPECT TO FREEDOM
#  FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

"""
Logging with the logging module is disabled. See http://bugs.python.org/issue23278
Using sys.stderr instead, but only for errors

#import#logging
"""
import sys
import traceback
from xml.parsers.expat import ExpatError
from xml.dom import minidom
from util.str_utils import prettify_dict, check_decoding

"""
It's tempting to use cElementTree, but don't. It is not compatible with multiprocessing because it cannot be pickled.
from xml.etree.cElementTree import tostring, ElementTree
"""
from xml.etree.ElementTree import tostring, ElementTree, Element, dump

import networkx
import numpy
from scipy.stats import stats

"""
Number of features used in the NetSimile paper
"""
NUMFEATURES = 7


class PDF(object):
    """
    :type xml: xml.etree.ElementTree.Element
    """
    def __init__(self, path, name='unnamed'):
        self.name = name
        self.path = path
        self.parsed = False
        self.size = 0
        self.js = ''
        self.swf = ''
        self.xml = ''
        self.blob = ''
        self.errors = ''
        self.bytes_read = 0
        self.v = []
        self.e = []
        self.ftr_vec = []

    def set_feature_vector(self):
        verts, edges = self.get_nodes_edges()
        ftr_matrix = self.get_graph_features(verts, edges)
        self.ftr_vec = self.aggregate_ftr_matrix(ftr_matrix)

    def get_root(self):
        rootid = None
        if self.xml is not None:
            obj = self.xml.find(".//Root")
            if obj is not None and isinstance(obj, Element):
                try:
                    rootid = obj.find(".//ref").get("id")
                except AttributeError:
                    sys.stderr.write("PDF.get_root: %s\nPDF obj: %s\nRoot missing reference object: %s\n" % (
                        self.name, obj, "HOLDER"))
            else:
                """
                This output gets a bit heavy. Malicious docs often don't have a root
                sys.stderr.write("PDF Missing root node: %s\n" % self.name)
                """
                pass
        return rootid

    def get_nodes_edges(self):
        if not self.v or not self.e:
            """
            Setup the PDF start and root object. The start object is simply the start state for the graph, it is not
            actually a part of the PDF document on disk or the PDF document specifications.
            """
            self.v.append(("PDF", ["start"]))
            rootid = self.get_root()
            if not rootid:
                rootid = 'missing_root'
                self.v.append((rootid, ["root"]))
            self.e.append(("PDF", rootid))

            """
            Walk the PDF graph from the parsed XML
            """
            visited = {()}
            new_v = []
            if isinstance(self.xml, Element):
                for obj in self.xml.iterfind("object"):
                    src_id = obj.get("id")
                    while src_id in visited:
                        src_id += '_'
                    visited.add(src_id)
                    self.v.append((src_id, [item.tag for item in obj.iter()]))
                    for ref in obj.iter("ref"):
                        dst_id = ref.get("id")
                        if dst_id not in visited:
                            new_v.append(dst_id)
                        self.e.append((src_id, dst_id))
                for v in new_v:
                    if v not in visited:
                        self.v.append((v, ['missing_target']))
        return self.v, self.e

    def get_graph_features(self, v, e):
        """ Graph features based on NetSimile paper

        :param v: set of vertices (label, [attrib])
        :type v:  list
        :param e: edges in the graph (vertex, vertex)
        :type e: list
        :return: a vector of features
        :rtype: list
        """
        graph = networkx.Graph()
        for label, attrs in v:
            graph.add_node(label, contains=attrs)
        for edge in e:
            graph.add_edge(*edge)

        """
        Transforms matrix from paper, so that each row is a feature, and each col is a node
        """
        features = [[] for i in range(NUMFEATURES)]
        for node in graph.nodes_iter():
            for idx, ftr in enumerate(self.get_node_features(graph, node)):
                features[idx].append(ftr)

        return features

    def get_node_features(self, graph, node):
        """  Node features based on NetSimile paper
        :param node:
        :type node:
        :return:
        :rtype:
        """
        """
        degree of node
        cluserting coef of node
        avg number of node's two-hop away neighbors
        avg clustering coef of Neighbors(node)
        number of edges in node i's egonet
        number of outgoing edges from ego(node)
        number of neighbors(ego(node))
        """
        neighbors = graph.neighbors(node)

        degree = graph.degree(node)

        cl_coef = networkx.clustering(graph, node)

        nbrs_two_hops = 0.0
        nbrs_cl_coef = 0.0
        for neighbor in neighbors:
            nbrs_two_hops += graph.degree(neighbor)
            nbrs_cl_coef += networkx.clustering(graph, neighbor)

        try:
            avg_two_hops = nbrs_two_hops / degree
            avg_cl_coef = nbrs_cl_coef / degree
        except ZeroDivisionError:
            avg_two_hops = 0.0
            avg_cl_coef = 0.0

        egonet = networkx.ego_graph(graph, node)

        ego_size = egonet.size()

        ego_out = 0
        ego_nbrs = set()
        for ego_node in egonet:
            for nbr in graph.neighbors(ego_node):
                if nbr not in neighbors:
                    ego_out += 1
                    ego_nbrs.add(nbr)

        return [degree, cl_coef, avg_two_hops, avg_cl_coef, ego_size, ego_out, len(ego_nbrs)]

    def aggregate_ftr_matrix(self, ftr_matrix):
        sig = []
        for ftr in ftr_matrix:
            try:
                median = stats.nanmedian(ftr)
                mean = stats.nanmean(ftr)
                std = stats.nanstd(ftr)
            except AttributeError:
                median = numpy.nanmedian(ftr)
                mean = numpy.nanmean(ftr)
                std = numpy.nanstd(ftr)
            # Invalid double scalars warning appears here
            skew = stats.skew(ftr) if any(ftr) else 0.0
            kurtosis = stats.kurtosis(ftr)
            sig.extend([median, mean, std, skew, kurtosis])
        return sig

    def get_javascript(self):
        if not self.js and isinstance(self.xml, Element):
            matches = self.xml.findall(".//js")
            if matches:
                self.js = "\n".join([match.text for match in matches])
        return self.js

    def get_xml_str(self):
        try:
            rv = tostring(self.xml)
        except AttributeError as e:
            sys.stderr.write("PDF xml element object error: %s: %s\n" % (self.name, e))
            rv = ''
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            sys.stderr.write("PDF to xml string encode/decode error: %s\n" % e)
            rv = ''
        return rv

    def dump_xml(self, elem):
        """

        :param elem:
        :type elem: xml.etree.ElementTree.Element
        :return:
        """
        xml = "<dumped_pdf>"
        for o in elem.iter():
            tag, attrib, text = o.tag, o.attrib, o.text
            tag = check_decoding(tag)
            text = check_decoding(text)
            xml += "<%s %s>%s<%s>\n" % (tag, prettify_dict(attrib), text, tag)
        return xml + "</dumped_pdf>"

    def save_xml(self, fp):
        xml_str = new_xml_str = "<xml_str>pdf.save_xml initialized value. Should not see this message</xml_str>"
        try:
            xml_str = tostring(self.xml)
            new_xml_str = minidom.parseString(xml_str)
            new_xml_str = new_xml_str.toprettyxml(indent="    ")
        except AttributeError as e:
            sys.stderr.write("Save XML AttributeError, missing xml likely: %s: %s\n" % (self.name, e))
            if xml_str != new_xml_str:
                new_xml_str = xml_str
            else:
                new_xml_str = str(e)
        except IOError as e:
            sys.stderr.write("PDF save xml unable to write out xml: %s: %s\n" % (self.name, e))
            new_xml_str = str(e)
        except UnicodeEncodeError as e:
            sys.stderr.write("Unicode ENCODE error saving XML file: %s: %s\n" % (self.name, e))
            new_xml_str = str(e)
        except UnicodeDecodeError as e:
            xml_str = self.dump_xml(self.xml)
            try:
                new_xml_str = minidom.parseString(xml_str)
                new_xml_str = new_xml_str.toprettyxml(indent="    ")
            except ExpatError as e:
                new_xml_str = xml_str
        except ExpatError as e:
            new_xml_str = "%s\n%s\n%s" % (e, '-'*80, xml_str)
        except OverflowError as e:
            new_xml_str = str(e)
        except Exception as e:
            sys.stderr.write("%s\n" % traceback.format_exc())
            sys.stderr.write("PDF.save_xml: UNCAUGHT EXCEPTION: %s: %s\n" % (self.name, e))
            new_xml_str = str(e)
        finally:
            fp.write(new_xml_str)
            fp.flush()
