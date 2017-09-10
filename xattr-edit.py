
import os
from pathlib import Path
from xattr import xattr
import fire
import archieml
from jinja2 import Environment
from collections import namedtuple
import stat
import base64

env = Environment()

env.filters["base64"]=lambda a : base64.b64encode(str(a).encode("utf-8")).decode("utf-8")

template=env.from_string("""
{% for file in items %}
{{ "{files." }}{{ file.stat.ino }}{{ "}" }}
path: {{file.path}}
--------------------------------------------------------------------------------------
name: {{file.path.name}}

{%- for k,v in file.attr.items() : %}
{{ k }}: {{ v }}
{%- endfor %}

{% endfor %}

""")



class attrwrapper(xattr) :

    def get(self,item) :
        if item.find("user.")==-1 :
            item=f"user.{item}"
        e=xattr.get(self,item)
        if type(e) == type(b'') :
            e=e.decode("utf-8")
        return e

    def set(self,item,value) :
        if item.find("user.")==-1 :
            item=f"user.{item}"
        if type(value) == type('') :
            value=value.encode("utf-8")
        xattr.set(self,item,value)

    def items(self) :
        for (k,v) in xattr.items(self) :
            if k.find("user.")==0 :
                k=k.split(".")[1]
            yield (k,v)

stattuple=namedtuple("stattuple",[b[0] for b in sorted([(a[3:].lower(),getattr(stat,a)) for a in dir(stat) if a.find("ST_")==0],key=lambda a: a[1])])


def metalist(pattern) :
    for p in Path(os.environ["PWD"]).glob(pattern) :
        yield dict(path=p,stat=stattuple(*p.stat()),attr=attrwrapper(p))

def test_metalist() :
    import pprint
    pprint.pprint(list(metalist("**/*")))


def test_template() :
    print(template.render(items=metalist("*")))

def test_archieml() :
    a=template.render(items=metalist("*"))
    import pprint
    pprint.pprint(archieml.loads(a))


def run(path) :
    print(template.render(items=metalist(path)))


if __name__=='__main__' :
    fire.Fire(run)


