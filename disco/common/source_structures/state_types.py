from enum import Enum
from typing import *

import slither.core.declarations as SD
import slither.core.solidity_types as ST

class STypes(Enum):
    # uint<M>、int<M>、address、bool、bytes<M>
    elementary_static = 1
    # string、bytes
    elementary_dynamic = 2

    # struct type
    user_define_static = 3
    user_define_dynamic = 4

    # array type
    array_type_static = 5
    array_type_dynamic = 6

    # mapping type
    mapping_type_static = 7
    mapping_type_dynamic = 8

    user_define_enum = 9
    user_define_contract = 10
    
class StateType:
    """create a class of Solidity Type"""
    def __init__(self, state_type:ST, type_name:str="") -> None:
        self.type_name = type_name
        self.state_type = state_type

        self._type:Optional[STypes.elementary_dynamic] = None

    @property
    def type(self) -> str:
        if self._type is None:
            self.typeAbstraction()
        return self._type

    @property
    def is_dynamic(self) -> bool:
        if self._type is None:
            self.typeAbstraction()
        return self._type.value in [2,4,6,8]

    @property
    def is_mapping(self) -> bool:
        if self._type is None:
            self.typeAbstraction()
        return self._type.value in [7,8]

    @property
    def is_elementary(self) -> bool:
        if self._type is None:
            self.typeAbstraction()
        return self._type.value in [1,2]

    def typeAbstraction(self):
        _type = self.state_type
        self._type = _handle_type(_type) 
    
    def __str__(self) -> str:
        if len(self.type_name) > 0:
            return "{} {}".format(self.type.name, self.type_name)
        else:
            return "{}".format(self.type.name)

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        ) 

def _handle_array(__type: ST.array_type.ArrayType):
    if __type.length is None:
        return STypes.array_type_dynamic
    else:
        type_e = _handle_type(__type.type)
        if type_e.value in [2,4,6,8]:
            return STypes.array_type_dynamic
    return STypes.array_type_static

def _handle_mapping(__type: ST.mapping_type.MappingType):
    type_e_from = _handle_type(__type._from)
    type_e_to = _handle_type(__type._to)
    if type_e_from.value in [2,4,6,8] or type_e_to.value in [2,4,6,8]:
        return STypes.mapping_type_dynamic
    return STypes.mapping_type_static

def _handle_userdefine(__type: ST.user_defined_type.UserDefinedType):
    # from slither.core.declarations.structure import Structure
    # from slither.core.declarations.enum import Enum
    # from slither.core.declarations.contract import Contract
    # structure、Enum、Contract are user defined, but the last two are static
    if isinstance(__type.type, SD.structure.Structure): 
        elems_ordered = __type.type.elems_ordered
        for elem in elems_ordered:
            type_e = _handle_type(elem.type)

            if type_e.value in [2,4,6,8]:
                return STypes.user_define_dynamic

    elif isinstance(__type.type, SD.contract.Contract):
        return STypes.user_define_contract

    elif isinstance(__type.type, SD.enum.Enum):
        return STypes.user_define_enum

    return STypes.user_define_static

def _handle_elementary(__type:ST.elementary_type.ElementaryType):
    if __type.name in ['string','bytes']:
        return STypes.elementary_dynamic
    return STypes.elementary_static

def _handle_type(__type):
    if isinstance(__type, ST.array_type.ArrayType):
        # switch to array type static/dynamic
        return _handle_array(__type)
    elif isinstance(__type, ST.mapping_type.MappingType):
        # switch to mapping type static/dynamic
        return _handle_mapping(__type)
    elif isinstance(__type, ST.user_defined_type.UserDefinedType):
        # switch to user define static/dynamic
        return _handle_userdefine(__type)
    elif isinstance(__type, ST.elementary_type.ElementaryType):
        # switch to elementary type static/dynamic
        return _handle_elementary(__type)
    else:
        assert 0
