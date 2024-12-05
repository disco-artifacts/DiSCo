from typing import *

from enum import Enum
from disco.common.structures.evm_variable import EVMArg, EVMProperty, EVMState, EVMVariable
from disco.common.structures.tac_tree import OpTree
from disco.common.utils.dump_load_utils import deserialize_tree, serialize_tree
from disco.common.utils.mongodb_utils import fixed_hash

class BehaviorType(Enum):
    SSTORE = 1,
    
    CREATE = 2,
    CREATE2 = 3,
    
    CALL = 4,
    CALLCODE = 5,
    DELEGATECALL = 6,
    STATICCALL = 7,
    
    SELFDESTRUCT = 8
    
    PUSH = 9 # used for dynamic array
class Behavior:
    def __init__(self, rhs:EVMVariable, lhs:List[OpTree], behavior_type:BehaviorType, behavior_pcs:List[str], block_ident:str=None, hash_encoder=None, ignore_hash:bool=True) -> None:
        self.rhs = rhs
        self.lhs = [] if lhs is None else lhs
       
        self.behavior_type = behavior_type
        self.behavior_pcs = behavior_pcs

        self.block_ident = "" if block_ident is None else block_ident
        
        self.hash_encoder = hash_encoder if not ignore_hash else None
        
        # the following two attributes only used for description generation
        self.call_returns = None
        self.depend_calls = None

    def __hash__(self) -> int:
        if self.hash_encoder is None:
            self.hash_encoder = fixed_hash(str(self))
        return hash(self.hash_encoder)
    
    def __eq__(self, __o: object) -> bool:
        return type(__o) == type(self) and hash(self) == hash(__o)
    
    def __str__(self) -> str:
        lhstr = ",".join([str(_lhs) for _lhs in self.lhs])
        return f"{self.behavior_type} {lhstr} {str(self.rhs)}"
    
    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )
    
    def pprint(self) -> str:
        print_str = ""
        if self.behavior_type == BehaviorType.SSTORE:
            print_str += f"{str(self.rhs)} = {'UNK' if len(self.lhs) == 0 else str(self.lhs[0])}"
        elif self.behavior_type in [BehaviorType.CREATE, BehaviorType.CREATE2]:
            if self.behavior_type in [BehaviorType.CREATE,]:
                print_str += f"{str(self.rhs)} = new Contract.value({'UNK' if len(self.lhs) == 0 else str(self.lhs[0])})(code={'UNK' if len(self.lhs) <= 1 else str(self.lhs[1])})"
            else:
                print_str += f"{str(self.rhs)} = new Contract.value({'UNK' if len(self.lhs) <= 0 else str(self.lhs[0])})(code={'UNK' if len(self.lhs) <= 1 else str(self.lhs[1])},salt={'UNK' if len(self.lhs) <= 2 else str(self.lhs[2])})"
        elif self.behavior_type in [BehaviorType.CALL, BehaviorType.CALLCODE, BehaviorType.DELEGATECALL, BehaviorType.STATICCALL]:
            if self.behavior_type in [BehaviorType.CALL, BehaviorType.CALLCODE]:
                if len(self.lhs) > 1:
                    args = ','.join([str(lhs) for lhs in self.lhs[1:]])
                else:
                    args = ''
                print_str += f"{str(self.rhs)}.{str(self.behavior_type.name.lower())}.value({'UNK' if len(self.lhs) <= 0 else str(self.lhs[0])})({args})"
            else:
                args = ','.join([str(lhs) for lhs in self.lhs])
                print_str += f"{str(self.rhs)}.{str(self.behavior_type.name.lower())}({args})"
        elif self.behavior_type in [BehaviorType.PUSH]:
            print_str += f"{str(self.rhs)}.push({'UNK' if len(self.lhs) <= 0 else str(self.lhs[0])})"        
        elif self.behavior_type in [BehaviorType.SELFDESTRUCT]:
            print_str += f"selfdestruct({str(str(self.rhs))})"
        
        return print_str
    
    def dump(self):
        return {
            "rhs": self.rhs.dump(),
            "lhs":[serialize_tree(tree) for tree in self.lhs],
            "behavior_type":self.behavior_type.name,
            "behavior_pcs":self.behavior_pcs,
            "hash_encoder":self.hash_encoder
        }
    
    @classmethod
    def load(cls, behavior):
        rhs_type = behavior['rhs']['variableType']
        rhs = behavior['rhs']
        if rhs_type == "EVMState":
            rhs = EVMState.load(rhs)
        elif rhs_type == "EVMProperty":
            rhs = EVMProperty.load(rhs)
        elif rhs_type == "EVMArg":
            rhs = EVMArg.load(rhs)
        else:
            raise ValueError(f"{rhs_type} is not considered")
        lhs = [deserialize_tree(arg) for arg in behavior['lhs']]
        behavior_type = getattr(BehaviorType, behavior['behavior_type'])
        behavior_pcs = [behavior['behavior_pc']] if 'behavior_pc' in behavior else behavior['behavior_pcs']
        hash_encoder = behavior.get('hash_encoder',None)
        
        return cls(
            rhs=rhs,
            lhs=lhs,
            behavior_type=behavior_type,
            behavior_pcs=behavior_pcs,
            hash_encoder=hash_encoder
        )