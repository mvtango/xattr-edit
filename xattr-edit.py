#! pyenv which python3.6
import os
from pathlib import Path
from xattr import xattr
import fire
import archieml
from jinja2 import Environment
from collections import namedtuple
import stat
import base64
import sys
import tempfile
import subprocess
import logging

logger=logging.getLogger(__name__)



env = Environment()

env.filters["base64"]=lambda a : base64.b64encode(str(a).encode("utf-8")).decode("utf-8")


class config:

    myattrs = ('path','name')

    force = ('datum', 'betrag', 'betreff', 'via')

    loglevel = logging.INFO


    template=env.from_string("""
{% for file in items %}
{{ "{files." }}{{ file.stat.ino }}{{ "}" }}
path: {{file.path}}
--------------------------------------------------------------------------------------
name: {{file.path.name}}
{%- for k in force : %}
{{ k }}: {{ file.attr.get(k) }}
{%- endfor %}
{%- for k,v in file.attr.items() : %}{%- if k not in force :%}
{{ k }}: {{ v }}
{%- endif %}{%- endfor %}

{% endfor %}

""")




def render(items,force=config.force) :
    return config.template.render(items=items,force=force)


class attrwrapper(xattr) :

    def get(self,item,default='') :
        if item.find("user.")==-1 :
            item=f"user.{item}"
        try :
            e=xattr.get(self,item)
        except OSError :
            e=default
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

    def keys(self) :
        for k in xattr.keys(self) :
            if k.find("user.")==0 :
                k=k.split(".")[1]
            yield k


    def __delitem__(self,item) :
        if item.find("user.")==-1 :
            item=f"user.{item}"
        xattr.__delitem__(self,item)



stattuple=namedtuple("stattuple",[b[0] for b in sorted([(a[3:].lower(),getattr(stat,a)) for a in dir(stat) if a.find("ST_")==0],key=lambda a: a[1])])


def metalist(pattern) :
    if pattern != '' :
        for p in Path(os.environ["PWD"]).glob(pattern) :
            yield dict(path=p,stat=stattuple(*p.stat()),attr=attrwrapper(p))
    else :
        if not sys.stdin.isatty() :
            for pa in sys.stdin.readlines() :
                p=Path(pa[:-1])
                yield dict(path=p,stat=stattuple(*p.stat()),attr=attrwrapper(p))
        else :
            logger.error("Expected file list at <stdin>")

def applychanges(f,delete=False) :
    data=archieml.load(open(f))
    counter=dict(files=0,attribs=0,dels=0)
    if "files" not in data :
        logger.error(f"No 'files' list found in edited file {f}")
        return {}
    for filedata in data["files"].values() :
        attr=attrwrapper(Path(filedata["path"]))
        if not os.path.exists(filedata["path"]) :
            logger.error(f"File not found: {filedata['path']}")
        else :
            logging.debug(f"checking {filedata['path']}")
            changing=False
            for (k,v) in filedata.items() :
                if k in config.myattrs :
                    logging.debug(f"ignoring attribute {k}, in exlusion list {config.myattrs}")
                    continue
                cv=attr.get(k,default=None)
                # if cv == v :
                #    logger.debug(f"Unchanged: {k}")
                # else :
                if cv != v :
                    if not changing :
                        changing = True
                        logger.info(f"Changing xattrs of {filedata['path']}:")
                        counter["files"]+=1
                    try :
                        attr.set(k,v)
                    except IOError :
                        logger.error(f"  - Error changing attribute {k} to {v}")
                    else :
                        counter["attribs"]+=1
                        logger.info(f"  - set {k} to '{v}' (old value: '{cv}')")
                else :
                    logger.debug(f"  - attribute {k} unchanged")
            if delete :
                deleted=set(attr.keys())-(set(filedata.keys())-set(config.myattrs))
                for k in deleted :
                    if not changing :
                        changing = True
                        logger.info(f"Changing xattrs of {filedata['path']}:")
                        counter["files"]+=1
                    v=attr[k]
                    del attr[k]
                    logger.info(f"  - deleted attribute {k} value '{v}'")
                    counter["dels"]+=1
    return counter


def test_metalist() :
    import pprint
    pprint.pprint(list(metalist("**/*")))


def test_template() :
    print(render(items=metalist("*")))

def test_archieml() :
    a=render(items=metalist("*"))
    import pprint
    pprint.pprint(archieml.loads(a))


def run(path='',force=config.force,delete=True,loglevel=config.loglevel,fromfile=None) :
    """

    Interactive mode:

          xattr-editor [PATH/GLOB PATTERN]



    Dump extended attributes to file (to edit) :

          xattr-editor [PATH/GLOB PATTERN] >attrlist.txt

           - or (filenames from stdin) -

          find . -name '*png' | xattr-editor >attrlist.txt


          (then edit attrlist.txt, and then)

          xattr-editor --fromfile=attrlist.txt




    [GLOB PATTERN] supports patters from python pathlib, like './**/*gz' for "all .gz files in all directories below this one".

    --delete=False will avoid deleting extended attributes that are present in the input data, but not in the files

    --force='("date","author")' will insert empty attributes with the names listed (date and author) for every file, like a blank form to be filled in. Please use a python tuple literal like the one above, e.g. --force='()' for en empty list. The default list is defined in the config module whithin this module.

    --loglevel=10 will set logging to "DEBUG", --loglevel=40 to "ERROR". Default is 20 ("INFO")

    """
    logging.basicConfig(level=loglevel,stream=sys.stderr)
    counter=False
    if sys.stdout.isatty() and sys.stdin.isatty():
        if fromfile is None:
            logger.info("Interactive Edit Mode")
            with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",delete=False) as tf :
                tf.write(render(items=metalist(path),force=force))
                tf.close()
                subprocess.run([os.environ.get("EDITOR",""),tf.name])
                counter=applychanges(tf.name,delete=delete)
    else :
        logger.info(f"STDIN is not a TTY - assuming file name list as input, dumping attributes list to {sys.stdout.name}")
        sys.stdout.write(render(items=metalist(path),force=force))
    if fromfile is not None :
        logger.info(f"Reading {fromfile} for changes")
        counter=applychanges(fromfile,delete=delete)
    if counter and counter.get("files",0)>0 :
        logger.info(f"{counter['files']} files changed: {counter['attribs']} attributes changed, {counter['dels']} attributes deleted")
    else :
        logger.info("no files changed")


if __name__=='__main__' :
    fire.Fire(run)


