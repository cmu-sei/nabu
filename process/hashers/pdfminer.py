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


import re
import traceback
from hasher import Hasher


class PDFMinerHasher(Hasher):

    def parse_pdf(self, pdf, err):
        parsed = False
        try:
            parsed = xml_creator.FrankenParser(pdf, self.debug)
        except Exception:
            err.append('<ParseException><pdf="%s">"%s"</ParseException>' % (str(pdf), traceback.format_exc()))
        return parsed

    def make_tree_string(self, pdf, err):
        if pdf.xml:
            return pdf.xml
        else:
            return '<TreeException>EMPTY TREE</TreeException>'

    def get_js(self, pdf, err):
        js = ''
        try:
            js_list = [ self.comment_out(js) for js in pdf.javascript ]
            js = '\n\n'.join(js_list)
        except Exception as e:
            err.append('<GetJSException>%s</GetJSException>' % traceback.format_exc())
        return js

    def get_deobf_js(self, js, pdf, err):
        de_js = ''
        try:
            if pdf.tree.startswith('TREE_ERROR'):
                err.append('<DeobfuscateJSException>%s</DeobfuscateJSException>' % pdf.tree)
        except AttributeError:
            try:
                #de_js = analyse(js, pdf.tree)
                pass
            except Exception as e:
                err.append('<DeobfuscateJSException>%s</DeobfuscateJSException>' % traceback.format_exc())
        return de_js

    def get_swf(self, pdf, err):
        swf = ''
        if pdf.swf:
            if isinstance(pdf.swf, list):
                swf = ''.join(pdf.swf)
            elif isinstance(pdf.swf, str):
                swf = pdf.swf
        return swf

    def get_pdf_size(self, pdf, err):
        return str(pdf.bytes_read)

    def get_errors(self, pdf, err):
        err.extend(pdf.errors)

    def make_graph(self, pdf, err):
        graph = ''
        try:
            graph = pdf.make_graph(pdf.tree)
            graph = '\n'.join(graph)
        except Exception as e:
            err.append('<GetJSException>%s</GetJSException>' % traceback.format_exc())
        return graph

    def comment_out(self, js):
        return re.sub("^(<)", "//", unescapeHTML(js), flags=re.M)
