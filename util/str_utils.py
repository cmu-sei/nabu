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


import hashlib
import re

import htmlentitydefs

ENTITY_PAT = re.compile(r'&#?\w+')


def check_decoding(string):
    rv = ""
    try:
        rv = string.decode("ascii")
    except UnicodeDecodeError:
        rv = string.encode("base64")
    except AttributeError:
        pass
    finally:
        return rv


def prettify_dict(dic):
    rv = ""
    for k, v in dic.items():
        k = check_decoding(k)
        if not k:
            k = "key_print_error"
        v = check_decoding(v)
        if not v:
            v = "value_print_error"
        rv += '%s="%s" ' % (k, v)
    return rv


def unescapeHTMLEntities(text):
    """
        Removes HTML or XML character references and entities from a text string.
        @param text The HTML (or XML) source text.
        @return The plain text, as a Unicode string, if necessary.
        Author: Fredrik Lundh
        Source: http://effbot.org/zone/re-sub.htm#unescape-html
    """
    def fixup(m):
        text = m.group(0)
        if text[:2] == '&#':
            # character reference
            try:
                if text[:3] == '&#x':
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    #return str(re.sub('&#?\w+;', fixup, text))
    return ENTITY_PAT.sub(fixup, text)


def get_hash(data):
    """

    :param data: Any byte or 2.X str
    :return: the MD5 hash of the data as a hexidecimal string
    :rtype: str
    """
    md5 = hashlib.md5()
    md5.update(data)
    return md5.hexdigest()


def isFlash (content):
    """
    Check for swf content in a string by searching for CWS or FWS
    in the first three characters

    :param content: String from PDF stream that needs to be checked for flash
    :type content: str
    :return: Whether or not the string starts with a valid flash signature
    :rtype: bool
    """
    content = unescapeHTMLEntities(content)
    return content.startswith("CWS") or content.startswith("FWS")


def getJavascript(content):
    """
    Given an string this method looks for typical Javscript strings and try to identify if the string contains
    Javascript code or not. If it contains JavaScript then the code is returned as as string.

    :param content: A string
    :type content: str
    :return: A string of suspected Javascript or an empty string if none.
    :rtype: str
    """
    reJSscript = '<script[^>]*?contentType\s*?=\s*?[\'"]application/x-javascript[\'"][^>]*?>(.*?)</script>'
    JSStrings = ['var ', ';', ')', '(', 'function ', '=', '{', '}', 'if ', 'else', 'return', 'while ', 'for ', ',',
                 'eval', 'unescape', '.replace']
    keyStrings = [';', '(', ')']
    stringsFound = []
    limit = 15
    minDistinctStringsFound = 5
    results = 0
    try:
        content = unescapeHTMLEntities(content)
    except UnicodeDecodeError:
        content = unescapeHTMLEntities(content.decode("latin1", errors="xmlcharrefreplace"))

    res = re.findall(reJSscript, content, re.DOTALL | re.IGNORECASE)
    if res:
        return "\n".join(res)

    for char in content:
        if (ord(char) < 32 and char not in ['\n', '\r', '\t', '\f', '\x00']) or ord(char) >= 127:
            return ''

    for string in JSStrings:
        cont = content.count(string)
        results += cont
        if cont > 0 and string not in stringsFound:
            stringsFound.append(string)
        elif cont == 0 and string in keyStrings:
            return ''

    if results > limit and len(stringsFound) >= minDistinctStringsFound:
        return content
    else:
        return ''
