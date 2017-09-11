THIS FILE IS AUTOMATICALLY GENERATED. DO NOT EDIT. EDIT Readme.md.template INSTEAD!

# xattr-edit.py

This utility makes exporting, importing and bulk editing of extended file system attributes in the "user." namespace easy, either with your favourite editor or by tools that can generate or manipulate text files. 

It needs Python 3.6 and these fine libraries, mentioned in `requirements.txt`:

```
archieml==0.3.2
cffi==1.10.0
fire==0.1.2
pycparser==2.18
six==1.10.0
xattr==0.9.2
Jinja2==2.9.6
```



## Extended Attributes

These attributes are supported by a lot of Mac and Unix filesystems, and if you take precautions, they can survive rsync, cp and tar. For details, please see https://en.wikipedia.org/wiki/Extended_file_attributes on Wikipedia.

This utility only works on the "user." namespace of the attributes

## Usage and Help from xattr-edit.py

```
Type:        function
String form: <function run at 0x7ffbd7d22268>
File:        ~/projekte/xattr-editor/xattr-edit.py
Line:        213
Docstring:   Interactive mode:

      xattr-edit.py [PATH/GLOB PATTERN]



Dump extended attributes to file (to edit) :

      xattr-edit.py [PATH/GLOB PATTERN] >attrlist.txt

       - or (filenames from stdin) -

      find . -name '*png' | xattr-edit.py >attrlist.txt


      (then edit attrlist.txt, and then)

      xattr-edit.py --fromfile=attrlist.txt

      --fromfile=- will read from <stdin>.




[GLOB PATTERN] supports patters from python pathlib, like './**/*gz' for "all .gz files in all directories below this one".

--delete=True will avoid deleting extended attributes that are present in the input data, but not in the files

--edit='("date","author")' will limit editing to the listed attributes, inserting empty values if they are not present. Please use a python tuple literal like the one above, and --edit='()' to edit all attributes. The default list is defined in the config module whithin this module.

--loglevel=DEBUG|INFO|ERROR. Default is "INFO"

Usage:       xattr-edit.py [PATH] [EDIT] [DELETE] [LOGLEVEL] [FROMFILE]
             xattr-edit.py [--path PATH] [--edit EDIT] [--delete DELETE] [--loglevel LOGLEVEL] [--fromfile FROMFILE]
```



## Thanks to

  - [ArchieML](http://archieml.org/) ;-) - the human friendly intermediate format used to edit the attributes

  - [fire](https://github.com/google/python-fire) - makes a command line utility out of every python object





