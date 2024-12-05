from typing import *

from disco.common.structures.unit.behavior_element import Behavior
from disco.common.structures.unit.condition_element import Condition
from disco.common.utils.mongodb_utils import encode_set

class SemanticUnit:
    def __init__(self, conditions:List[Condition], behavior:Behavior, belong_functions:List[str]=None, hash_encoder=None, ignore_hash:bool=True) -> None:
        self.conditions = conditions
        self.behavior = behavior
        
        self.belong_functions = set() if belong_functions is None else set(belong_functions)

        self.hash_encoder = hash_encoder if not ignore_hash else None

    def __str__(self) -> str:
        return self.pprint(print_loc=False)    
    
    def pprint(self, print_loc:bool=True) -> str:
        nested = 0
        conditions_str, behavior_str = "", ""
        for condition in self.conditions:
            if print_loc: conditions_str += f"[{condition.condition_pc}@{condition.block_ident}]".ljust(20," ")
            conditions_str += " "*(nested * 4) + condition.pprint() + "\n"
            nested += 1
        
        if print_loc: behavior_str += f"[{'-'.join(self.behavior.behavior_pcs)}@{self.behavior.block_ident}]".ljust(20," ")
        behavior_str += " "*(nested * 4) + self.behavior.pprint()
        
        return f"{conditions_str}{behavior_str}"
    
    def __hash__(self) -> int:
        if self.hash_encoder is None:
            self.hash_encoder = hash(f"{hash(self.behavior)}{encode_set(self.conditions)}{encode_set(self.belong_functions)}")
        return hash(self.hash_encoder)
    
    def __eq__(self, __o: object) -> bool:
        return type(self) == type(__o) and len(self.conditions) == len(__o.conditions) and self.behavior.behavior_type == __o.behavior.behavior_type and hash(self) == hash(__o)
        
    def dump(self) -> dict:
        return {
            "conditions":[condition.dump() for condition in self.conditions],
            "behavior":self.behavior.dump(),
            "belong_functions":list(self.belong_functions),
            "hash_encoder":self.hash_encoder
        }
    
    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            repr(self.behavior)
        )
    
    @classmethod
    def load(cls, semantic_unit):
        conditions = [Condition.load(condition) for condition in semantic_unit['conditions']]
        behavior = Behavior.load(semantic_unit['behavior'])
        belong_functions = semantic_unit['belong_functions']
        hash_encoder = semantic_unit.get('hash_encoder',None)
        return cls(conditions, behavior, belong_functions, hash_encoder)
