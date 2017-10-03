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
import re
from collections import UserDict

logger=logging.getLogger(__name__)


env = Environment()

env.filters["base64"]=lambda a : base64.b64encode(str(a).encode("utf-8")).decode("utf-8")


class config:

    myattrs = ('path','name')

    edit = ('datum', 'betrag', 'betreff', 'via')

    loglevel = "INFO"

    some_template=env.from_string("""
{% for file in items %}
{{ "{files." }}{{ file.stat.ino }}{{ "}" }}
name: {{file.path.name}}
path: {{file.path}}
--------------------------------------------------------------------------------------
{%- for k in edit : %}
{{ k }}: {{ file.attr.get(k) }}
{%- endfor %}

{% endfor %}
""")

    all_template=env.from_string("""
{% for file in items %}
{{ "{files." }}{{ file.stat.ino }}{{ "}" }}
name: {{file.path.name}}
path: {{file.path}}
--------------------------------------------------------------------------------------
{%- for k,v in file.attr.items() : %}
{{ k }}: {{ v }}
{%- endfor %}

{% endfor %}
""")


def to_pathglob(s) :
    elements=s.split(os.path.sep)
    found=None
    for a in enumerate(elements) :
        if re.search(r"[\[\?\*]",a[1]) :
            found = a[0]
            break
    if found is not None :
        return Path(os.path.sep.join(elements[:found])).glob(os.path.sep.join(elements[found:]) or '*.*')
    else :
        return [Path(s)]


def render(items,edit=config.edit) :
    if edit :
        return config.some_template.render(items=items,edit=edit)
    else :
        return config.all_template.render(items=items)


class attrwrapper(xattr) :
    """ Changes from xattr: Uses user. namespace as default
        Converts values to string, base85encodes values that
        cannot be handled as unicode strings
    """

    def get(self,item,default='') :
        if item.find("user.")==-1 :
            item=f"user.{item}"
        try :
            e=xattr.get(self,item)
        except OSError :
            e=default
        if type(e) == type(b'') :
            try :
                e=e.decode("utf-8")
            except UnicodeDecodeError :
                pass
                e=base64.b85encode(e)
        return e

    def set(self,item,value) :
        if item.find("user.")==-1 :
            item=f"user.{item}"
        test=self.get(item)
        if test[0:2]=="b'" and value[-1]=="'" :
                raise ValueError(f"Error setting {item}: Overwriting binary attribute values is currently not supported.")
                return
        if value[0:2]=="b'" and value[-1]=="'" :
            try :
                value=base64.b85decode(value[2:-1])
            except ValueError as e :
                raise ValueError(f"Base 85 decode error: {value} {e}")
            else :
                raise ValueError(f"Error setting {item}: Setting binary attribute values is currently not supported.")
                return
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


class FileAttrObject(object) :

    __slots__ = ( 'path','stat','attr' )

    def __init__(self,p) :
        self.path=p
        self.stat=stattuple(*p.stat())
        self.attr=attrwrapper(p)


def metalist(pattern) :
    if pattern != '' :
        for p in to_pathglob(pattern) :
            yield FileAttrObject(p)
    else :
        if not sys.stdin.isatty() :
            for pa in sys.stdin.readlines() :
                p=Path(pa[:-1])
                yield FileAttrObject(p)
        else :
            logger.error("Expected file list at <stdin>")

def applychanges(f,delete=False,edit=()) :
    if f=='-' :
        data=archieml.load(sys.stdin)
        logger.info("Reading file attribute data from <stdin>")
    else :
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
                if edit and k not in edit :
                    logging.debug(f"Ignoring {k} - not in edit list {edit}")
                    continue
                cv=attr.get(k,default=None)
                # if cv == v :
                #    logger.debug(f"Unchanged: {k}")
                # else :
                if cv != v and str(cv) != v:
                    if not changing :
                        changing = True
                        logger.info(f"Changing xattrs of {filedata['path']}:")
                        counter["files"]+=1
                    try :
                        attr.set(k,v)
                    except (IOError,ValueError) as e :
                        logger.error(f"{e} while trying to change attribute {k} to {v}")
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
                    if edit and k not in edit :
                        logging.debug(f"Ignoring deletion request for {k} - not in edit list {edit}")
                        continue
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


def run(path='',edit=config.edit,delete=False,loglevel=config.loglevel,fromfile=None) :
    """

    Interactive mode:

          xattr-edit.py [PATH/GLOB PATTERN]



    Dump extended attributes to file (to edit) :

          xattr-edit.py [PATH/GLOB PATTERN] >attrlist.txt

           - or (filenames from stdin) -

          find . -name '*png' | xattr-edit.py >attrlist.txt


          (then edit attrlist.txt, and then)

          xattr-edit.py --fromfile=attrlist.txt

          --fromfile=- will read from <stdin>.




    [GLOB PATTERN] supports patters from python pathlib, like './**/*gz' for "all .gz files in all directories below this one".

    --delete=True delete extended attributes that are not present in the input data. Default is False (keep them).

    --edit='("date","author")' will limit editing to the listed attributes, inserting empty values if they are not present. Please use a python tuple literal like the one above, and --edit='()' to edit all attributes. The default list is defined in the config module whithin this module.

    --loglevel=DEBUG|INFO|ERROR. Default is "INFO"

    """
    if hasattr(logging,loglevel.upper()) :
        loglevel=getattr(logging,loglevel.upper())
    else :
        loglevel=logging.INFO
    logging.basicConfig(level=loglevel,stream=sys.stderr)
    counter=False
    if sys.stdout.isatty() and sys.stdin.isatty():
        if fromfile is None:
            logger.info("Interactive Edit Mode")
            with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",delete=False) as tf :
                tf.write(render(items=metalist(path),edit=edit))
                tf.close()
                subprocess.run([os.environ.get("EDITOR",""),tf.name])
                counter=applychanges(tf.name,delete=delete,edit=edit)
    else :
        if fromfile is None :
            logger.info(f"STDIN is not a TTY - assuming newline-separated file name list from <stdin>, dumping attributes list to {sys.stdout.name}")
            sys.stdout.write(render(items=metalist(path),edit=edit))
        else :
            logger.info(f"STDIN is not a TTY, --fromfile parameter is given  - assuming attributes list from <stdin>.")
    if fromfile is not None :
        logger.info(f"Reading {fromfile} for changes")
        counter=applychanges(fromfile,delete=delete,edit=edit)
    if counter and counter.get("files",0)>0 :
        logger.info(f"{counter['files']} files changed: {counter['attribs']} attributes changed, {counter['dels']} attributes deleted")
    else :
        logger.info("no files changed")


if __name__=='__main__' :
    fire.Fire(run)

