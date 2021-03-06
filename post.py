import os, imp, doctest, datetime, re, time
from collections import OrderedDict, namedtuple
from util import slugify, render_to
import settings

import pygments_rest

RSTError = namedtuple('RSTError', 'filename line type message text')

int_id_name = settings.get('BREEV_ID', 'post_id')
metadata_attrs = (int_id_name, 'pub_date','updated','title','tags','author','draft')

class TextPart(object):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text

    def get_rst(self, **kwargs):
        return self.text+'\n'

class DocTestPart(object):
    def __init__(self, example=None):
        self.examples = []
        if example:
            self.add(example)

    def add(self, example):
        example.source = re.split('\s*#\s*doctest\s*:',example.source)[0]
        self.examples.append(example)
    def __repr__(self):
        return '<DocTestPart>'+self.examples.__repr__()

    def get_rst(self, **kwargs):
        noclasses = kwargs.get('noclasses', True)

        code = []
        for example in self.examples:
            source = '>>> '+'\n    ... '.join(example.source.strip().split('\n'))
            code.append(source)
            if getattr(example, 'last_got', None):
                output = example.last_got
            elif example.want:
                output = example.want
            else:
                output = ''

            output = output.strip().replace('\n<BLANKLINE>\n', '\n\n').replace('\n','\n    ')

            if output:
                code.append(output)

        ret = '.. sourcecode:: pycon'
        if noclasses:
            ret += '\n    :noclasses:'
        ret += '\n\n    '+('\n    '.join(code))+'\n'

        return ret

class CodePart(object):
    def __init__(self, code):
        self.code = code

    def add(self, code):
        self.code = '\n'.join((self.code, code))
    def __str__(self):
        return self.code
    def __repr__(self):
        return '<CodePart>'+self.code

    def get_rst(self, **kwargs):
        noclasses = kwargs.get('noclasses', False)
        linenos = kwargs.get('linenos', True)

        ret = '.. sourcecode:: python'
        if noclasses:
            ret += '\n    :noclasses:'
        if linenos:
            ret += '\n    :linenos:'
        ret += '\n\n    '+self.code.replace('\n', '\n    ')+'\n'

        return ret

class Post(object):
    def __init__(self, module_path):
        self.module_path = module_path
        self.filename    = filename = os.path.basename(module_path)

        module_name = filename.split('.')[0].lstrip('_01234567890')

        imp_desc  = ('', 'r', imp.PY_SOURCE)
        with open(module_path) as module_file:
            self.module     = imp.load_module(module_name, module_file, module_path, imp_desc)
            module_file.seek(0)
            self.module_src = module_file.read()

        self.title    = self.module.title
        self.author   = self.module.author # TODO: settings.AUTHORS lookup
        self.tags     = getattr(self.module,'tags',())
        self.is_draft = getattr(self.module,'draft',False)
        self.pub_date = datetime.datetime(*self.module.pub_date)

        updated = getattr(self.module, 'updated', self.pub_date)
        self.updated  = updated or datetime.datetime(*updated)

        try:
            self.id = int(getattr(self.module, int_id_name, None))
        except ValueError:
            raise ValueError('Internal IDs should be integers.'+str(file_path))
        
        self.slug     = slugify(unicode(self.title))

        self.parts    = get_parts(self.module_src)

        self.run_examples()

    @property
    def is_pub(self):
        return (not self.is_draft) and (self.pub_date < datetime.datetime.now())

    def run_examples(self):
        from doctest import DocTest, DocTestRunner
        examples = sum([part.examples for part in self.parts if isinstance(part, DocTestPart)],[])
        dt = DocTest(examples, self.module.__dict__, self.filename, None, None, None)
        dtr = DocTestRunner()

        def tmp_out(message_to_throw_away):
            # TODO capture error messages, warn
            return

        dtr.run(dt, out=tmp_out, clear_globs=False)

    @property
    def text_parts(self):
        return [ p for p in self.parts if isinstance(p, TextPart) ]

    def get_rst(self, **kwargs):
        return '\n'.join([part.get_rst(**kwargs) for part in self.parts])

    def get_errors(self):
        self.get_html()
        return self.rst_errors
            
    def get_url(self, absolute=False, format='html'):
        if absolute:
            import settings
            prefix = settings.BLOG_URL
        else:
            prefix = '/'

        return prefix + 'posts/'+self.slug+'.'+format


    def get_html(self, body_only=True, content_only=False, noclasses=False):
        import sys
        import pygments_rest
        from docutils.core import Publisher
        from docutils.io import StringInput, StringOutput
        from cStringIO import StringIO
        
        settings = {'doctitle_xform'     : 1,
                    'pep_references'     : 1,
                    'rfc_references'     : 1,
                    'footnote_references': 'superscript',
                    'output_encoding'    : 'unicode',
                    'report_level'       : 2, # 2=show warnings, 3=show only errors, 5=off (docutils.utils
                    }

        if content_only:
            post_rst = self.get_rst(noclasses=noclasses)
        else:
            post_rst = render_to('post_single.rst', 
                                 post=self, 
                                 noclasses=noclasses)
                             
        pub = Publisher(reader=None, 
                        parser=None, 
                        writer=None, 
                        settings=None,
                        source_class=StringInput,
                        destination_class=StringOutput)

        pub.set_components(reader_name='standalone',
                           parser_name='restructuredtext',
                           writer_name='html')
        pub.process_programmatic_settings(settings_spec=None,
                                          settings_overrides=settings,
                                          config_section=None)
        pub.set_source(post_rst,source_path=self.module_path)
        pub.set_destination(None, None)

        errors_io = StringIO()
        real_stderr = sys.stderr
        sys.stderr = errors_io
        try:
            html_full = pub.publish(enable_exit_status=False)
            html_body = ''.join(pub.writer.html_body)
        finally:
            sys.stderr = real_stderr
        errors = errors_io.getvalue()
        self._process_rest_errors(errors)

        errors_io.close()

        return html_body if body_only else html_full


    def _process_rest_errors(self, docutils_errors):
        errors = []
        docutils_err_list = docutils_errors.split('\n')
        for err in docutils_err_list:
            if err.strip() == '':
                continue
            try:
                fields   = err.split(':')
                filename = fields[0].strip()
                line     = fields[1].strip()
                
                type_message = fields[2].strip().split(' ')
                err_type = type_message[0]
                message  = ' '.join(type_message[1:])
                
                text     = ':'.join(fields[3:]).strip(' .')

                errors.append(RSTError(filename, line, err_type, message, text))
            except IndexError as ie:
                pass
        self.rst_errors = errors



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

