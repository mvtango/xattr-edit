
import os
from pathlib import Path
from xattr import xattr
import fire
import attrdict
from jinja2 import Environment, PackageLoader, select_autoescape
from collections import namedtuple
import stat


env = Environment()


template=env.from_string("""
{% for file in items %}
path: {{file.path}}
name: {{file.path.name}}
dir: {{file.path.parent}}
inode: {{file.stat.ino}}

{%- for k,v in file.attr.items() : %}
{{ k }}: {{ v }}
{%- endfor %}

{% endfor %}

""")



class attrwrapper(xattr) :

    def get(self,item) :
        e=xattr.get(self,item)
        print(f"get of {item}")
        if type(e) == type(b'') :
            e=e.decode("utf-8")
        return e



stattuple=namedtuple("stattuple",[b[0] for b in sorted([(a[3:].lower(),getattr(stat,a)) for a in dir(stat) if a.find("ST_")==0],key=lambda a: a[1])])


def metalist(pattern) :
    for p in Path(os.environ["PWD"]).glob(pattern) :
        yield dict(path=p,stat=stattuple(*p.stat()),attr=attrwrapper(p))

def test_metalist() :
    import pprint
    pprint.pprint(list(metalist("**/*")))


def test_template() :
    print(template.render(items=metalist("*")))


