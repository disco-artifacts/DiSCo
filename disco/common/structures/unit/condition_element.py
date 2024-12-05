import copy
from disco.common.structures.tac_tree import OpTree
from disco.common.utils.dump_load_utils import deserialize_tree, serialize_tree
from disco.common.utils.mongodb_utils import fixed_hash

class Condition:
    def __init__(self, optree:OpTree, condition_pc:str, dst_var=None, cond_var=None, cstates=None, block=None, block_ident:str=None, hash_encoder=None, ignore_hash:bool=True) -> None:
        self.optree = optree
        self.condition_pc = condition_pc
        self.dst_var = dst_var
        self.cond_var = cond_var
        
        self.block = None if block is None else block
        self.block_ident = "" if block_ident is None else block_ident
        self.cstates = dict() if cstates is None else cstates
        
        self.hash_encoder = hash_encoder if not ignore_hash else None
        
        # the following two attributes only used for description generation
        self.depend_calls = None
    
    def set_cstates(self, cstates):
        self.cstates.update(cstates)    
    
    def set_cstate(self, cstate, value:bool=True):
        self.cstates[cstate] = value
    
    def get_cstate(self, cstate) -> bool:
        return self.cstates.get(cstate, False)
    
    def __deepcopy__(self, memodict={}):
        return type(self)(
            optree=deserialize_tree(serialize_tree(self.optree)),
            cstates=copy.deepcopy(self.cstates, memodict)
        )
    
    def __hash__(self) -> int:
        if self.hash_encoder is None:
            self.hash_encoder = fixed_hash(str(self))
        return hash(self.hash_encoder)
    
    def __eq__(self, __o: object) -> bool:
        return type(__o) == type(self) and hash(self) == hash(__o)
    
    def __str__(self) -> str:
        return f"{str(self.optree)}"
    
    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )
    
    def pprint(self) -> str:
        print_str = f"if{str(self.optree)}"
        
        return print_str
    
    def dump(self) -> dict:
        return {
            "optree": serialize_tree(self.optree),
            "condition_pc": self.condition_pc,
            "cstates":self.cstates,
            "hash_encoder":self.hash_encoder
        }
    
    @classmethod
    def load(cls, condition):
        optree = deserialize_tree(condition['optree'])
        condition_pc = condition['condition_pc']
        cstates = condition['cstates']
        hash_encoder = condition.get('hash_encoder',None)
        return cls(
            optree=optree,
            condition_pc=condition_pc,
            cstates=cstates,
            hash_encoder=hash_encoder
        )
