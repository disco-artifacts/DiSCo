from collections import defaultdict
from typing import *

from disco.common.structures.evm_type import EVMType

SIZE_IN_BYTES = 32

class EVMVariable:
    def __init__(self, index:int, counts:int=0) -> None:
        self.index = index
        self.counts = counts
       
    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )
    
    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, __o: object) -> bool:
        return type(self) == type(__o) and hash(self) == hash(__o)
    
    def change_to_contract_type(self):
        pass

    def change_to_bool_type(self):
        pass

    def change_to_enum_type(self):
        pass

    def change_to_computable_type(self):
        pass
    
    def change_to_bytesM(self):
        pass
    
    @classmethod
    def empty_instance(cls):
        return cls(index=-1)

class EVMLocal(EVMVariable):
    def __init__(self, name: str) -> None:
        super().__init__(index=-1)
        
        self.name = name
    
    def details(self, with_counts:bool=False, with_keys:bool=False):
        return self.name
    
    def __str__(self) -> str:
        return self.details()

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )

    def dump(self):
        return {
            "variableType":"EVMLocal",
            "name":self.name
        }
    
    @classmethod
    def load(cls, data):
        return cls(name=data['name'])
    
    @property
    def semantic(self):
        return str(self)

    @property
    def type_is_dynamic(self):
        return False
    
class EVMProperty(EVMVariable):
    def __init__(self, name: str) -> None:
        super().__init__(index=-1)
        
        self.name = name
    
    def details(self, with_counts:bool=False, with_keys:bool=False):
        return self.name
    
    def __str__(self) -> str:
        return self.details()

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )

    def dump(self):
        return {
            "variableType":"EVMProperty",
            "name":self.name
        }
    
    @classmethod
    def load(cls, data):
        return cls(name=data['name'])
    
    @property
    def semantic(self):
        return str(self)

    @property
    def type_is_dynamic(self):
        return False
        
class EVMArg(EVMVariable):
    def __init__(self, index, is_dynamic:bool=False, keys:str=None, from_load=False) -> None:
        if not from_load and (index - 4) % 0x20 == 0:
            index = (index - 4) // 0x20
        #     self.solved = True
        # else:
        #     self.solved = False
        # if is_dynamic: self.solved = True
        super().__init__(index=index)
        
        self.is_dynamic = is_dynamic
        self.keys = "" if keys is None else keys
    
    def details(self, with_counts:bool=False, with_keys:bool=True):
        # if self.solved:
        if with_keys and len(self.keys) > 0:
            return f"Arg{self.index}.{self.keys}"
        elif self.index >= 0:
            return f"Arg{self.index}"
        else:
            return "Args"
        # else:
        #     return f"CALLDATALOAD({hex(self.index)})" 
   
    def __str__(self) -> str:
        return self.details()
        
    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )

    def dump(self):
        return {
            "variableType":"EVMArg", 
            "index":self.index,
            "is_dynamic":self.is_dynamic,
            "keys":self.keys
        }
    
    @classmethod
    def load(cls, data):
        return cls(index=int(data['index']), is_dynamic=data['is_dynamic'], keys=data['keys'], from_load=True)

    @property
    def semantic(self):
        return str(self)

    @property
    def type_is_dynamic(self):
        return self.is_dynamic

class EVMState(EVMVariable):
    def __init__(self, index, offset, length, type:EVMType, is_public:bool=False, signature:bool="", name:str=None, inferred_name:str=None, counts:int=0, counts_mapping:Dict[str,int]=None, keys=None, from_load:bool=False) -> None:
        super().__init__(index=index)
        
        self.type = type
        if from_load:
            self.offset = offset
            self.length = length
        else:
            if self.type is not None and self.type.is_elementary and not self.type.is_dynamic:
                if offset is not None and length is not None:
                    self.offset = SIZE_IN_BYTES - (offset + length)
                else:
                    self.offset = None # None
                if self.offset is None:
                    self.length = None
                else:
                    self.length = length
            else:
                self.offset = None
                self.length = None

        self.is_public = is_public
        self.signature = signature
        
        # hot fix for signature 0x18160ddd
        if name == "voting_var":
            name = "totalSupply"
        
        self.name = name
        self.inferred_name = inferred_name

        # counts and keys are path sensitive
        self.counts_mapping = defaultdict(list) if counts_mapping is None else defaultdict(lambda:list(), counts_mapping.copy())
        self.keys = [] if keys is None else keys
        self.counts = counts
        
    def __str__(self) -> str:
        return self.details()

    def details(self, with_counts:bool=True, with_keys:bool=True) -> str:
        __keys_str = ""
        for v in self.keys:
            __keys_str += "[%s]"%(str(v))
    
        if with_keys:
            keys_str = __keys_str
        else:
            keys_str = ""
        ret = ""
        if self.name is not None and len(self.name) > 0:
            ret += "%s%s"%(self.name,keys_str)
        elif self.inferred_name is not None:
            ret += "%s%s"%(self.inferred_name,keys_str)
        elif self.offset is not None and self.length is not None:
            if self.offset == 0 and self.length == SIZE_IN_BYTES:
                ret += "S(%d)%s"%(self.index, keys_str)
            else:
                ret += "S(%d)(%d:%d)%s"%(self.index, self.offset, self.offset+self.length, keys_str)
        else:
            ret += "S(%d)%s"%(self.index, keys_str)

        if with_counts:
            ret += "_%d"%(self.counts)
        return ret
    
    @property
    def type_is_dynamic(self):
        return self.type.is_dynamic
    
    def change_to_contract_type(self):
        self.type.change_to_contract_type()
    
    def change_to_string_type(self):
        self.type.change_to_string_type()
    
    def change_to_bool_type(self):
        self.type.change_to_bool_type()
        
    def change_to_enum_type(self):
        self.type.change_to_enum_type()

    def change_to_computable_type(self):
        self.type.change_to_computable_type()
    
    def change_to_bytesM(self, M:int=32):
        self.type.change_to_bytesM(M)

    @property
    def semantic(self) -> str:
        if self.name is not None:
            return self.name
        elif self.inferred_name is not None:
            return "_%s_"%(self.inferred_name)
        else:
            return str(self.type)+"_"+self.details(with_counts=False, with_keys=False)

    def __hash__(self) -> int:
        return hash("%d_%d_%d"%(hash(self.index), hash(self.offset), hash(self.length)))

    def __lt__(self, __o: object) -> bool:
        if type(__o) == type(self):
            if self.index < __o.index:
                return True

            elif self.index == __o.index:
                return self.offset > __o.offset if __o.offset is not None and self.offset is not None else False
        return False

    def clear(self):
        self.counts_mapping.clear()
        self.keys.clear()

    def test_dump(self) -> dict:
        return {
            "index": self.index,
            "offset": self.offset,
            "length": self.length,
            "type": self.type.dump()
        }

    def dump(self) -> dict:
        from disco.common.utils.dump_load_utils import serialize_tree
        dumped_keys = []
        for key in self.keys:
            dumped_keys.append(serialize_tree(key))
        return {
            "variableType": "EVMState",
            "index": self.index,
            "offset": self.offset,
            "length": self.length,
            "type": self.type.dump(),
            "is_public": self.is_public,
            "signature": self.signature,
            "counts":self.counts,
            "counts_mapping": self.counts_mapping,
            "name": self.name,
            "inferred_name": self.inferred_name,
            "keys": dumped_keys,
        }
    
    def copy(self):
        return self.load(self.dump())
    
    def __deepcopy__(self, memodict={}):
        return self.load(self.dump())
    
    @classmethod
    def load(cls, data):
        from disco.common.utils.dump_load_utils import deserialize_tree
        loaded_keys = []
        for key in data["keys"]:
            loaded_keys.append(deserialize_tree(key))
                
        return cls(
            index=int(data['index']),
            offset=data['offset'],
            length=data['length'],
            type=EVMType.load(data['type']),
            is_public=data['is_public'],
            signature=data['signature'],
            name=data['name'],
            counts=data.get('counts',0),
            counts_mapping=data['counts_mapping'],
            inferred_name=data['inferred_name'],
            keys=loaded_keys,
            from_load=True
        )
