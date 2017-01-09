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

# Remove logging support to workaround issue23278
# import logging


import gzip
import numpy
import os
import re
import pickle
import signal
import sys
"""
It's tempting to use cElementTree, but don't. It is not compatible with multiprocessing because it cannot be pickled.
from xml.etree.cElementTree import tostring, ElementTree
"""
from xml.etree.ElementTree import TreeBuilder, tostring, dump

from lib.parse.pdfminer import pdftypes
from lib.parse.pdfminer.pdfdocument import PDFDocument
from lib.parse.pdfminer.pdfparser import PDFParser
from lib.parse.pdfminer.psparser import PSKeyword, PSLiteral, PSEOF, PSException

from process.pdf import PDF
from util.str_utils import getJavascript, isFlash


numpy.seterr(all='ignore')


ESC_PAT = re.compile(r'[\000-\037&<>()"\042\047\134\177-\377]')
ENC = 'base64'


# Used only for saving XML, which is currently a disabled feature.
OUTPUTDIR = 'xml-output'


def sigint_handler(signal, frame):
    """

    Avoid issue 8296.
    :param signal:
    :param frame:
    :return: Does not.
    """
    sys.stderr.write("%d Caught SIGINT\n" % os.getpid())
    sys.exit(0)


def pdf_error_xml(pdfpath, err):
    tb = TreeBuilder()
    tb.start("pdf", {"path": pdfpath, "type": "error"})
    tb.data("%s" % err)
    return tb.end("pdf")

def check_pdf_retval(pdf):
    """
    Certain PDFs will be unpickleable, which means they cannot be sent back through the multiprocessing.Pool for
    handling in the main function. If you try they will raise a MaybeEncodingError, and there is currently no
    good way to recover from these exceptions and continue processing the rest of the samples. So, the check is done
    here.
    """
    try:
        if len(pickle.dumps(pdf)) >= pow(2, 31) - 1:
            pdf = PDF(pdf.path, pdf.name)
            pdf.xml = pdf_error_xml(pdf.path, "Parsed PDF size overlows 32 bit int result capacity")
    except Exception as e:
        sys.stderr.write("PDF cannot be returned to main process for storage in database: %s: %s\n" % (pdf.name, e))
        pdf = PDF(pdf.path, pdf.name)
        pdf.xml = pdf_error_xml(pdf.path, str(e))
    return pdf


def parse_and_hash(pdfpath):
    signal.signal(signal.SIGINT, sigint_handler)
    parser = PDFMinerParser()
    pdf = PDF(pdfpath, os.path.basename(pdfpath))

    try:
        parser.parse(pdf)
    except PSException as e:
        sys.stderr.write("PDFMiner failed to parse: %s\n" % pdf.name)
    except Exception as e:
        sys.stderr.write("PDFMiner uncaught error: %s: %s\n" % (pdf.name, e))

    if pdf.parsed and pdf.xml != '':
        try:
            pdf.set_feature_vector()
        except AttributeError as e:
            sys.stderr.write("Attribute Error: %s\n" % e)
        fout = os.path.join(OUTPUTDIR, "%s.xml.zip" % pdf.name)
        try:
            gzfp = gzip.open(fout, "wb", compresslevel=4)
        except IOError as e:
            # logging.error("Parse and hash error opening xml output file: %s\n\t%s" % (fout, e))
            sys.stderr.write("Parse and hash error opening xml output file: %s\n\t%s\n" % (fout, e))
        else:
            pdf.save_xml(gzfp)
            gzfp.close()

    return check_pdf_retval(pdf)


class PDFMinerParser(object):

    def __init__(self):
        self.treebuild = TreeBuilder()

    @staticmethod
    def esc(s):
        return ESC_PAT.sub(lambda m: '&#%d;' % ord(m.group(0)), s)

    def add_xml_node(self, tag, attrs, data):
        if not attrs:
            attrs = {}
        if data is None:
            data = "MISSING"
        self.treebuild.start(tag, attrs)
        self.treebuild.data(data)
        self.treebuild.end(tag)

    def dump(self, obj):
        try:
            obj_attrs = {"size": str(len(obj))}
        except TypeError:
            obj_attrs = {}

        if obj is None:
            self.add_xml_node("null", {}, '')

        elif isinstance(obj, dict):
            self.treebuild.start("dict", obj_attrs)
            for key, val in obj.iteritems():
                # Replace non word characters in key
                key = re.sub(r'\W+', '', key)
                if key.isdigit() or not key:
                    key = 'KEYERROR'
                self.treebuild.start(key, {})
                try:
                    self.dump(val)
                except Exception as e:
                    sys.stderr.write("DUMP excpetion: %s\n" % e)
                self.treebuild.end(key)
            self.treebuild.end("dict")

        elif isinstance(obj, list):
            self.treebuild.start("list", obj_attrs)
            for listobj in obj:
                try:
                    self.dump(listobj)
                except Exception as e:
                    sys.stderr.write("DUMP excpetion: %s\n" % e)
            self.treebuild.end("list")

        elif isinstance(obj, str):
            self.add_xml_node("string", obj_attrs.update({"enc": ENC}), self.esc(obj).encode(ENC))

        elif isinstance(obj, pdftypes.PDFStream):
            self.treebuild.start("stream", obj_attrs)

            self.treebuild.start("props", {})
            try:
                self.dump(obj.attrs)
            except Exception as e:
                sys.stderr.write("DUMP excpetion: %s\n" % e)
            self.treebuild.end("props")

            try:
                data = obj.get_data()
            except pdftypes.PDFNotImplementedError as e:
                self.add_xml_node("error", {"type": "PDFNotImplementedError"}, e.message)
            except pdftypes.PDFException as e:
                self.add_xml_node("error", {"type": "PDFException"}, e.message)
            except Exception as e:
                self.add_xml_node("error", {"type": "Uncaught"}, str(e))
            else:
                js = getJavascript(str(data))
                if js:
                    self.add_xml_node("js", {"enc": ENC, "size": str(len(js))}, js)
                else:
                    self.add_xml_node("data", {"enc": ENC, "size": str(len(data))}, self.esc(data).encode(ENC))

            self.treebuild.end("stream")

        elif isinstance(obj, pdftypes.PDFObjRef):
            self.add_xml_node("ref", {"id": str(obj.objid)}, '')

        elif isinstance(obj, PSKeyword):
            self.add_xml_node("keyword", {}, obj.name)

        elif isinstance(obj, PSLiteral):
            self.add_xml_node("literal", {}, obj.name)

        elif isinstance(obj, (int, long, float)):
            self.add_xml_node("number", {}, str(obj))

        else:
            raise TypeError(obj)

    def get_obj_loc(self, xref, objid):
        loc = "UNKNOWN"
        try:
            loc = xref.get_pos(objid)[1]
        except KeyError:
            loc = "FREE"
        finally:
            return loc

    def read_pdf_block(self, parser, pos, length=512):
        obj_data = "UNKNOWN"
        try:
            obj_data = parser.read_n_from(pos, length)
        except TypeError:
            obj_data = "ERROR: Could not read PDF data from pos: %s for %s bytes" % (pos, length)
        finally:
            return obj_data

    def end_xml_node(self, tag):
        try:
            self.treebuild.end(tag)
        except AssertionError as e:
            if 'mismatch' in e.message:
                expected_tag = e.message.partition("(expected ")[2]
                expected_tag = expected_tag.partition(",")[0]
                if expected_tag:
                    self.end_xml_node(expected_tag)

    def parse(self, pdf):
        try:
            fp = open(pdf.path, 'rb')
        except IOError as e:
            # logging.error("PDFMinerParser.parse unable to open PDF: %s" % e)
            sys.stderr.write("PDFMinerParser.parse unable to open PDF: %s\n" % e)
            return

        visited = set()
        self.treebuild.start("pdf", {"path": pdf.path})

        try:
            parser = PDFParser(fp)
            doc = PDFDocument(parser)
        except PSEOF:
            self.add_xml_node("PSException", {}, "Unexpected end of PDF")
            self.treebuild.end("pdf")
            pdf.parsed = True
            return

        if doc.found_eof and doc.eof_distance > 3:
            pdf.blob = parser.read_from_end(doc.eof_distance).encode("base64")

        for xref in doc.xrefs:
            for objid in xref.get_objids():

                if objid in visited:
                    continue

                visited.add(objid)

                obj_attrs = {"id": str(objid), "type": "normal"}
                obj_data = ''
                obj_xml = self.treebuild.start("object", obj_attrs)
                obj_loc = self.get_obj_loc(xref, objid)
                obj_xml.set("location", str(obj_loc))

                try:
                    self.dump(doc.getobj(objid))
                except pdftypes.PDFObjectNotFound as e:
                    obj_xml.set("type", "malformed")
                    obj_data = self.read_pdf_block(parser, obj_loc, 4096).replace("<", "0x3C")
                except TypeError:
                    obj_xml.set("type", "unknown")
                    obj_data = self.read_pdf_block(parser, obj_loc).replace("<", "0x3C")
                except Exception as e:
                    obj_xml.set("type", "exception")
                    obj_data = self.read_pdf_block(parser, obj_loc).replace("<", "0x3C")
                    self.add_xml_node("exception", {}, str(e))

                try:
                    obj_data.decode("ascii")
                except UnicodeDecodeError:
                    obj_data = obj_data.encode("base64")

                self.treebuild.data(obj_data)

                #self.end_xml_node("object")
                try:
                    self.treebuild.end("object")
                except (AssertionError, TypeError):
                    return

            self.treebuild.start("trailer", {})
            self.dump(xref.trailer)
            self.treebuild.end("trailer")

        self.treebuild.end("pdf")

        pdf.xml = self.treebuild.close()

        pdf.errors = doc.errors
        pdf.bytes_read = parser.BYTES
        pdf.parsed = True
        fp.close()
