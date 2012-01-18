import os, imp, doctest, datetime
from collections import OrderedDict, namedtuple
from util import slugify
import settings

import pygments_rest

class DocTestPart(object):
    def __init__(self, example):
        self.examples = [example]
    def add(self, example):
        self.examples.append(example)
    def __repr__(self):
        return '<DocTestPart>'+self.examples.__repr__()

    def get_rest(self):
        code = []
        for example in self.examples:
            code.append('>>> '+example.source.strip())
            if example.want:
                code.append(example.want.strip().replace('\n','\n   '))
        ret = '.. sourcecode:: pycon\n\n   '+('\n   '.join(code))+'\n'
        return ret

class TextPart(object):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text

    def get_rest(self):
        return self.text+'\n'

class CodePart(str):
    def __init__(self, code):
        self.code = code

    def add(self, code):
        self.code = '\n'.join((self.code, code))
    def __str__(self):
        return self.code

    def get_rest(self):
        ret = '.. sourcecode:: python\n   :linenos:\n\n   '+self.code.replace('\n', '\n   ')+'\n'
        return ret

class Post(object):
    def __init__(self, module_path):
        file_name = os.path.basename(module_path)

        pdw_id = file_name.split('_')[0].lstrip('0')
        try:
            self.id = int(pdw_id)
        except ValueError:
            raise ValueError('PDWs should start with a unique integer representing the PDW ID.'+str(file_path))
        
        module_name = file_name.split('.')[0].lstrip('_01234567890')
        #print pdw_id, module_name

        imp_desc  = ('', 'r', imp.PY_SOURCE)
        with open(module_path) as module_file:
            self.module     = imp.load_module(module_name, module_file, module_path, imp_desc)
            module_file.seek(0)
            self.module_src = module_file.read()

        self.title    = self.module.title
        self.author   = self.module.author # TODO: settings.AUTHORS lookup
        self.tags     = getattr(self.module,'tags',())
        self.is_draft = getattr(self.module,'draft',False)
        self.date     = datetime.datetime(*self.module.date)
        self.slug     = slugify(unicode(self.title))

        self.parts    = get_parts(self.module_src)

    def get_rest(self):
        return '\n'.join([part.get_rest() for part in self.parts])
            

metadata_attrs = ('date','title','tags','author','draft')

def get_parts(string):
    ret = []
    import ast
    from ast import Expr, Str, Assign
    from doctest import DocTestParser,Example
    dtp = DocTestParser()
    lines = string.split("\n")
    m_ast = ast.parse(string)
    str_linestarts = [ x.lineno for x in m_ast.body if isinstance(x, Expr) and isinstance(x.value, Str)]
    for i, node in enumerate(m_ast.body):
        lineno = node.lineno
        if isinstance(node, Assign) and node.targets[0].id in metadata_attrs:
            continue
        elif isinstance(node, Expr) and isinstance(node.value, Str):
            for s in dtp.parse(node.value.s):
                if isinstance(s, Example):
                    if ret and isinstance(ret[-1], DocTestPart):
                        ret[-1].add(s)
                    else:
                        ret.append(DocTestPart(s))
                elif len(s.strip()) > 0:
                    ret.append(TextPart(s.strip()))
                else:
                    continue
        else:
            last_line = 0
            for subnode in ast.walk(node):
                last_line = max(getattr(subnode,'lineno',0), last_line)
            code_str = '\n'.join(lines[lineno-1:last_line]).strip()
            if ret and isinstance(ret[-1], CodePart):
                ret[-1].add(code_str)
            else:
                ret.append(CodePart(code_str))

    return ret
