#! pyenv which python3.6
import os
import copy
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

from userxattr import UserXattr

logger=logging.getLogger(__name__)


env = Environment()

env.filters["base64"]=lambda a : base64.b64encode(str(a).encode("utf-8")).decode("utf-8")


class config:

    myattrs = ('path','name')

    edit = ('datum', 'betrag', 'betreff', 'via')

    loglevel = "INFO"

    some_template=env.from_string("""
This file is an ArchieML File. ArchieML is a bit like YAML, only
simpler - a format "optimized for human writability" (and machine
readability) created at the New York Times. See http://archieml.org
for reference.

Pre-allocated field names: {{ edit | join(",") }}
{% if path %}Path used: {{ path }}{% endif %}

{% for file in items %}
{{ "{files." }}{{ file.stat.ino }}{{ "}" }}
name: {{file.path.name}}
path: {{file.path}}
--------------------------------edit-below-this-line-------
{%- for k in edit : %}
{{ k }}: {{ file.attr.get(k) }}
{%- endfor %}
--------------------------------edit-above-this-line-------

{% endfor %}
""")

    all_template=env.from_string("""
This file is an ArchieML File. ArchieML is a bit like YAML, only
simpler - a format "optimized for human writability" (and machine
readability) created at the New York Times. See http://archieml.org
for reference.

{% for file in items %}
{{ "{files." }}{{ file.stat.ino }}{{ "}" }}
name: {{file.path.name}}
path: {{file.path}}
--------------------------------edit-below-this-line-------
{%- for k,v in file.attr.items() : %}
{{ k }}: {{ v }}
{%- endfor %}
--------------------------------edit-above-this-line-------

{% endfor %}
""")

def split_pathglob(s) :
    elements=s.split(os.path.sep)
    found=None
    for a in enumerate(elements) :
        if re.search(r"[\[\?\*]",a[1]) :
            found = a[0]
            break
    if found is not None :
        return (os.path.sep.join(elements[:found]),os.path.sep.join(elements[found:]) or '*.*')
    else :
        return (s,None)

def to_pathglob(s) :
    """ returns iterable from patterns like "/var/log/**/*.log"
    """
    (prefix,rest)=split_pathglob(s)
    if rest is not None :
        return Path(prefix).glob(rest)
    else :
        return [Path(prefix)]


def render(items,edit=config.edit,**kwargs) :
    if edit :
        return config.some_template.render(items=items,edit=edit,**kwargs)
    else :
        return config.all_template.render(items=items,**kwargs)


stattuple=namedtuple("stattuple",[b[0] for b in sorted([(a[3:].lower(),getattr(stat,a)) for a in dir(stat) if a.find("ST_")==0],key=lambda a: a[1])])


class FileAttrObject(object) :

    __slots__ = ( 'path','stat','attr' )

    def __init__(self,p) :
        self.path=p
        self.stat=stattuple(*p.stat())
        self.attr=UserXattr(p)


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
        attr=UserXattr(Path(filedata["path"]))
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
                    if edit and k not in edit :
                        logging.debug(f"Ignoring deletion request for {k} - not in edit list {edit}")
                        continue
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


def run(path='',attrcopy=None,edit=config.edit,delete=False,loglevel=config.loglevel,fromfile=None) :
    """

    Tool to interactively or programmatically edit extended attributes.

    Interactive mode:

          xattr-edit.py [PATH/GLOB PATTERN]

          (edits extended attributes in place)

          xattr-edit.py --attrcopy=attributes.txt [PATH/GLOB PATTERN]

          (This version keeps a copy of the extended attributes  in a text file,
          so they can survive Dropbox, S3 or other file transfers. You can
          then read them at the other end of the file transfer using the
          --fromfile parameter, see below.)

    Dump extended attributes to file (to edit) :

          xattr-edit.py [PATH/GLOB PATTERN] >attrlist.txt

           - or (filenames from stdin) -

          find . -name '*png' | xattr-edit.py >attrlist.txt


          (then edit attrlist.txt, and then)

          xattr-edit.py --fromfile=attrlist.txt

          --fromfile=- will read from <stdin>.




    [GLOB PATTERN] supports patters from python pathlib, like './**/*gz' for
    "all .gz files in all directories below this one".

    --delete=True delete extended attributes that are listed in the --edit
      parameter, but are not present in the input data.
      Default is False (keep those attributes).

    --edit='("date","author")' will limit editing to the listed attributes,
      inserting empty values if they are not present.
      Please use a python tuple literal like the one above, and --edit='()'
      to edit all attributes.
      The default list is defined in the config module whithin this module.

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
            if attrcopy is None :
                logger.info("Interactive Edit Mode - Temporary File")
                with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",delete=False) as tf :
                    tf.write(render(items=metalist(path),edit=edit))
                    tf.close()
                    subprocess.run([os.environ.get("EDITOR",""),tf.name])
                    counter=applychanges(tf.name,delete=delete,edit=edit)
            else :
                logger.info(f"Interactive Edit Mode - Persistent file {attrcopy}")
                with open(attrcopy,mode="w",encoding="utf-8") as tf :
                    tf.write(render(items=metalist(path),edit=edit,path=path,attrfile=tf))
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

