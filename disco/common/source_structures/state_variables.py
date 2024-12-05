from typing import *
from disco.common.source_structures.state_types import StateType

class StateVariable:
    def __init__(self, 
                 name:str, 
                 is_public:bool, 
                 state_type:StateType, 
                 visit_params:List[str]=[], 
                 belong_contract:Optional[str]=None,
                 sload_idx:Optional[int]=None,
                 sload_offset:Optional[int]=None,
                 sload_length:Optional[int]=None) -> None:
        self.name = name
        self.is_public = is_public
        self.state_type=state_type
        self.visit_params=visit_params
        self.belong_contract=belong_contract

        self.sload_idx = sload_idx

        if state_type.is_dynamic or state_type.is_mapping or sload_length > 0x20:
            sload_offset = None
            sload_length = None

        if sload_offset is not None and sload_length is not None:
            self.sload_offset = 0x20 - sload_offset - sload_length
        else:
            self.sload_offset = None
        
        self.sload_length = sload_length

    def __str__(self) -> str:
        _type = str(self.state_type)
        visibility = "public" if self.is_public else "private"
        name = self.name

        idx = str(self.sload_idx)
        offset = self.sload_offset
        length = self.sload_length
        location = "S[%s]"%idx
        if offset is not None and length is not None:
            location += "[%d:%d]"%(offset, offset+length)

        return "{} {} {} at {}".format(_type, visibility, name, location)

    def __repr__(self) -> str:
        return "<{0} object {1} {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, __o: object) -> bool:
        return type(self) == type(__o) and hash(self) == hash(__o)

    def dump(self) -> dict:
        return {
            "name":self.name,
            "type":str(self.state_type),
            "visibility":"public" if self.is_public else "private",
            "index":str(self.sload_idx),
            "offset":self.sload_offset,
            "length":self.sload_length
        }