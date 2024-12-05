from collections import defaultdict
from enum import Enum
from typing import *


class EnumType(Enum):
    elementary_static = 1
    # e.g., uint<M>、int<M>、address、bool、bytes<M>
    elementary_dynamic = 2
    # e.g., string、bytes
    
    user_define_enum = 3
    user_define_contract = 4
    # struct type

    array_type_static = 5
    array_type_dynamic = 6
    # array type

    mapping_type_static = 7
    mapping_type_dynamic = 8
    # mapping type

    other_type = 9
    # unknown type

class EVMType:
    def __init__(self, hints:Dict=None, length:Optional[int]=None, type_name:str=None) -> None:
        self.hints = defaultdict(bool) if hints is None else hints 
        self.length = -1 if length is None else length # length in bytes
        
        self.enum_type = None
        self.type_name = "" if type_name is None else type_name

    @property
    def type(self) -> str:
        if self.enum_type is None:
            self.type_inference()
        return self.enum_type
    
    @property
    def is_elementary(self) -> bool:
        if self.enum_type is None:
            self.type_inference()
        return self.enum_type.value in [1,2]
    
    @property
    def is_user_define(self) -> bool:
        if self.enum_type is None:
            self.type_inference()
        return self.enum_type.value in [3,4]

    @property
    def is_array(self) -> bool:
        if self.enum_type is None:
            self.type_inference()
        return self.enum_type.value in [5,6]

    @property
    def is_mapping(self) -> bool:
        if self.enum_type is None:
            self.type_inference()
        return self.enum_type.value in [7,8]

    @property
    def is_dynamic(self) ->bool:
        if self.enum_type is None:
            self.type_inference()
        return self.enum_type.value in [2,6,8]

    @property
    def is_contract(self) -> bool:
        return self.enum_type.value in [4]
    
    @property
    def is_other_type(self) -> bool:
        return self.enum_type.value in [9]

    def change_to_contract_type(self):
        self.enum_type = EnumType.user_define_contract
        self.type_name = "user_define_contract"

    def change_to_enum_type(self):
        self.enum_type = EnumType.user_define_enum
        self.type_name = "user_define_enum"

    def change_to_bool_type(self):
        self.enum_type = EnumType.elementary_static
        self.type_name = "bool"

    def change_to_string_type(self):
        self.enum_type = EnumType.elementary_dynamic
        self.type_name = "string"

    def change_to_computable_type(self):
        if self.is_mapping or self.is_array or self.is_dynamic: return
        self.enum_type = EnumType.elementary_static
        if self.hints['is_signed']:
            self.type_name = "int%d"%(self.length*8)
        else:
            self.type_name = "uint%d"%(self.length*8)

    def change_to_bytesM(self, M):
        self.enum_type = EnumType.elementary_static
        self.type_name = "bytes%d"%M
        self.length = M

    def type_inference(self):
        if len(self.type_name) > 0:
            if self.type_name in ['bytes','string','elementary_dynamic']:
                self.enum_type = EnumType.elementary_dynamic
            elif self.type_name in ['bool','address'] or self.type_name.startswith("uint") or self.type_name.startswith("int") or self.type_name.startswith("bytes"):
                self.enum_type = EnumType.elementary_static
                if self.type_name == "bool":
                    self.length = 1
                elif self.type_name == "address":
                    self.length = 20
                elif self.type_name.startswith("uint"):
                    self.length = int(self.type_name.replace("uint",""))//8
                elif self.type_name.startswith("int"):
                    self.length = int(self.type_name.replace("int",""))//8
                elif self.type_name.startswith("bytes"):
                    self.length = int(self.type_name.replace("bytes",""))
            elif self.type_name in ['user_define_enum']:
                self.enum_type = EnumType.user_define_enum
                self.length = 1
            elif self.type_name in ['user_define_contract']:
                self.enum_type = EnumType.user_define_contract
                self.length = 20
            elif self.type_name in ['array_type_static']:
                self.enum_type = EnumType.array_type_static
            elif self.type_name in ['array_type_dynamic']:
                self.enum_type = EnumType.array_type_dynamic
            elif self.type_name in ['mapping_type_static']:
                self.enum_type = EnumType.mapping_type_static
            elif self.type_name in ['mapping_type_dynamic']:
                self.enum_type = EnumType.mapping_type_dynamic
            else:
                self.enum_type = EnumType.other_type
        else:
            if self.hints['is_array']:
                if self.hints['is_dynamic']:
                    self.enum_type = EnumType.array_type_dynamic
                else:
                    self.enum_type = EnumType.array_type_static
            elif self.hints['is_mapping']:
                if self.hints['is_dynamic']:
                    self.enum_type = EnumType.mapping_type_dynamic
                else:
                    self.enum_type = EnumType.mapping_type_static
            else:
                if self.hints['is_dynamic']:
                    self.enum_type = EnumType.elementary_dynamic
                    if self.hints['is_bytes']:
                        self.type_name = "bytes"
                    else:
                        self.type_name = "string"
                else:
                    if not self.hints['is_higher_order']:
                        if self.hints['is_signed']:
                            self.enum_type = EnumType.elementary_static
                            self.type_name = "int%d"%(self.length*8)
                        elif self.length == 1:
                            if self.hints['is_bool']:
                                self.enum_type = EnumType.elementary_static
                                self.type_name = "bool"
                            elif self.hints['is_enum']:
                                self.enum_type = EnumType.user_define_enum
                                self.type_name = "user_define_enum"
                            else:
                                self.enum_type = EnumType.elementary_static
                                self.type_name = "uint8"
                        elif self.length == 20:
                            if self.hints['is_contract']:
                                self.enum_type = EnumType.user_define_contract
                                self.type_name = "user_define_contract"
                            elif self.hints['is_computable']:
                                self.enum_type = EnumType.elementary_static
                                self.type_name = "uint160"
                            else:
                                self.enum_type = EnumType.elementary_static
                                self.type_name = "address"
                        else:
                            self.enum_type = EnumType.elementary_static
                            self.type_name = "uint%d"%(self.length*8)
                    else:
                        self.enum_type = EnumType.elementary_static
                        self.type_name = "bytes%d"%self.length
                
    def __str__(self) -> str:
        if self.enum_type is None:
            self.type_inference()
        if len(self.type_name) > 0:
            return "{}".format(self.type_name)
        else:
            return "{}".format(self.enum_type.name)

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        ) 
    
    @classmethod
    def load(cls, data):
        _type = cls(type_name=data['type_name'])
        _type.type_inference()
        return _type
    
    def dump(self) -> Dict:
        return {"type_name":str(self)}
    
    @staticmethod
    def empty_instance():
        return EVMType()
