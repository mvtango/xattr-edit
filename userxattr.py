from xattr import xattr
import base64

class UserXattr(xattr) :
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



