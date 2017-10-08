# Singleton/SingletonPattern.py

from ruamel.yaml import YAML
from collections import UserDict
from tempfile import NamedTemporaryFile
import os,sys

yaml=YAML() # typ="safe")
import logging


logging.basicConfig(stream=sys.stderr,level=logging.DEBUG)

logger=logging.getLogger(__name__)

class emptystring(UserDict) :

    def get(self,key,default='') :
        if key in self :
            return self[key]
        else :
            return default

class YamlXattr():


    class __AttrStore:

        def __init__(self, filename):
            self.filename = filename
            try :
                self.store = yaml.load(open(filename))
                logger.debug("Loaded {} keys from {}".format(
                        len(list(self.store.keys())),
                        self.filename))
            except FileNotFoundError:
                self.store = dict()
                logger.debug(f"{filename} not found, creating new store")


        def get(self,filep,key=None) :
            if hasattr(filep,"as_posix") :
                fkey=filep.as_posix()
            else :
                fkey=filep
            if key is None :
                if fkey not in self.store :
                    logger.debug(f"{fkey} - no attr found, initializing")
                    self.store[fkey]=emptystring()
                return self.store[fkey]
            else :
                return self.store[fkey][key]

        def set(self,filep,key=None,val=None) :
            if hasattr(filep,"as_posix") :
                fkey=filep.as_posix()
            else :
                fkey=filep
            if  val is None and hasattr(key,'keys') :
                self.store[fkey]=key
            else :
                self.store[fkey][key]=val


        def __del__(self) :
            fdir,fname=os.path.split(self.filename)
            sfile=NamedTemporaryFile(dir=fdir,
                                    prefix="{}.".format(fname),
                                    delete=False)
            yaml.dump(self.store,sfile)
            sfile.close()
            bakfile="{}.bak".format(self.filename)
            try :
                os.remove(bakfile)
            except FileNotFoundError :
                pass
            try :
                os.rename(self.filename,bakfile)
            except FileNotFoundError :
                pass
            os.rename(sfile.name,self.filename)


    instance = None


    def __new__(self, path=None, store=None):
        if not YamlXattr.instance:
            YamlXattr.instance = YamlXattr.__AttrStore(store)
        if path is not None :
            return YamlXattr.instance.get(path)
        else :
            return None



if __name__ == '__main__' :
    pass
