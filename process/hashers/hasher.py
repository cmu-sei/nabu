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


class Hasher(multiprocessing.Process):
    """
    Hashers generally make hashes of things
    """

    def __init__(self, qin, qout, counter, debug):
        multiprocessing.Process.__init__(self)
        self.qin = qin
        self.qout = qout
        self.counter = counter
        self.debug = debug

    '''
    This loop is the main process of the hasher. It is automatically called
    when you call multiprocessing.Process.start()

    All variables should be local to the loop, and returned as strings
    suitable for inserting into the database.
    '''

    def run(self):
        while True:
            pdf = self.qin.get()
            if not pdf:
                '''
                This terminates the process by receiving a poison sentinel, None.
                '''
                self.qout.put(None)
                # self.qin.task_done()
                return 0

            '''
            Reset the values on each pdf.
            '''
            err = []
            urls = ''
            t_hash = ''
            t_str = ''
            graph = ''
            obf_js = ''
            de_js = ''
            obf_js_sdhash = ''
            de_js_sdhash = ''
            swf_sdhash = ''
            swf = ''
            fsize = ''
            pdfsize = ''
            bin_blob = ''
            malformed = {}

            '''
            Arguments are validated when Jobber adds them to the queue based
            on the Validators valid() return value. We can assume these will
            succeed. However, this process must reach the task_done() call,
            and so we try/catch everything
            '''
            try:
                pdf_name = pdf.rstrip(os.path.sep).rpartition(os.path.sep)[2]
            except Exception as e:
                err.append('UNEXPECTED OS ERROR:\n%s' % traceback.format_exc())
                pdf_name = pdf
            write('H\t#%d\t(%d / %d)\t%s\n' % (self.pid, self.counter.value(), self.counter.ceil(), pdf_name))
            '''
            The parse_pdf call will return a value that evaluates to false if it
            did not succeed. Error messages will appended to the err list.
            '''
            parsed_pdf = self.parse_pdf(pdf, err)

            if parsed_pdf:
                try:
                    fsize = self.get_file_size(pdf)
                    pdfsize = self.get_pdf_size(parsed_pdf, err)
                    graph = self.make_graph(parsed_pdf, err)
                    t_str = self.make_tree_string(parsed_pdf, err)
                    t_hash = self.make_tree_hash(graph, err)
                    obf_js = self.get_js(parsed_pdf, err)
                    de_js = self.get_deobf_js(obf_js, parsed_pdf, err)
                    obf_js_sdhash = make_sdhash(obf_js, err)
                    de_js_sdhash = make_sdhash(de_js, err)
                    urls = self.get_urls(obf_js, err)
                    urls += self.get_urls(de_js, err)
                    swf = self.get_swf(parsed_pdf, err)
                    swf_sdhash = make_sdhash(swf, err)
                    bin_blob = parsed_pdf.bin_blob
                    malformed = parsed_pdf.getmalformed()
                    self.get_errors(parsed_pdf, err)
                except Exception as e:
                    err.append('UNCAUGHT PARSING EXCEPTION:\n%s' % traceback.format_exc())

            err = 'Error: '.join(err)
            malformed['skipkeys'] = False
            try:
                json_malformed = json.dumps(malformed)
            except (TypeError, ValueError):
                malformed['skipkeys'] = True
                json_malformed = json.dumps(malformed, skipkeys=True)

            self.qout.put({'fsize': fsize,
                           'pdf_md5': pdf_name,
                           'tree_md5': t_hash,
                           'tree': t_str,
                           'obf_js': obf_js,
                           'de_js': de_js,
                           'swf': swf,
                           'graph': graph,
                           'pdfsize': pdfsize,
                           'urls': urls,
                           'bin_blob': bin_blob,
                           'obf_js_sdhash': obf_js_sdhash,
                           'de_js_sdhash': de_js_sdhash,
                           'swf_sdhash': swf_sdhash,
                           'malformed': json_malformed,
                           'errors': err})
            self.counter.inc()
            # self.qin.task_done()

    def parse_pdf(self, pdf, err=''):
        return None, 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def get_file_size(self, pdf):
        try:
            size = os.path.getsize(pdf)
        except OSError:
            '''
            This should never actually happen if we were able to parse it
            '''
            size = 0
        return str(size)

    def get_pdf_size(self, pdf):
        return 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def make_graph(self, pdf, err=''):
        return 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def make_tree_string(self, pdf, err=''):
        return 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def make_tree_hash(self, t_str, err=''):
        t_hash = ''
        m = hashlib.md5()
        try:
            m.update(t_str)
            t_hash = m.hexdigest()
        except TypeError:
            err.append('<HashException>%s</HashException>' % traceback.format_exc())
        return t_hash

    def get_js(self, pdf, err=''):
        return 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def get_debof_js(self, js, pdf, err=''):
        return 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def get_swf(self, pdf, err=''):
        return 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def get_errors(self, pdf, err=''):
        return 'Hasher: Unimplemented method, %s' % sys._getframe().f_code.co_name

    def get_urls(self, haystack, err='', needle=''):
        urls = ''
        if not needle:
            for needle in huntterp.Test.tests:
                urls = huntterp.find_in_hex(needle, haystack)
                urls += huntterp.find_unicode(needle, haystack)
        else:
            urls = huntterp.find_in_hex(needle, haystack)
            urls += huntterp.find_unicode(haystack)
        return '\n'.join([u[1] for u in urls])
