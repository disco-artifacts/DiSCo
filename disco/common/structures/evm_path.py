from collections import defaultdict
from typing import *

import disco.common.structures.evm_stack as Stack

class EVMPath:
    SEP = "->"

    def __init__(self, blocks=None, stacks:List[Stack.EVMStack]=None, edge_count=None, from_transaction:bool=False, entry_index:int=0) -> None:
        self.blocks = blocks if blocks is not None else []
        self.stacks = stacks if stacks is not None else []

        self.edge_count = edge_count if edge_count is not None else defaultdict(int)
        self.from_transaction = from_transaction
        
        self.function = None
        """the function pointor which the path belong to"""        
        
        self.entry_index = entry_index
        """the entry index is the first block of function body"""

        self.transaction_hash:str=""
        """for debug the path"""

    def add_element(self, block, stack=None, repeat_max:int=3) -> bool:
        if len(self.blocks) > 0:
            if self.edge_count[(self.blocks[-1].ident(), block.ident())] + 1 > repeat_max:
                return False
            self.edge_count[(self.blocks[-1].ident(), block.ident())] += 1
        self.blocks.append(block)
        if stack:
            self.stacks.append(stack)

        return True
    
    def copy(self):
        return EVMPath(blocks=self.blocks[:], 
                       stacks=self.stacks[:], 
                       edge_count=self.edge_count.copy(),
                       from_transaction=self.from_transaction,
                       entry_index=self.entry_index)

    def __iter__(self):
        for block in self.blocks:
            yield block

    def __len__(self) -> int:
        return len(self.blocks)

    def __str__(self) -> str:
        return "\n".join(str(b) for b in self.blocks)

    def __repr__(self) -> str:
        evm_blocks = self.SEP.join(b.ident() for b in self.blocks)
        return "<{0} object {1}: {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            evm_blocks
        )

    def __hash__(self) -> int:
        return hash("".join(b.ident() for b in self.blocks))

    def __eq__(self, o) -> bool:
        return type(o) == type(self) and hash(o) == hash(self)
    
    @property
    def has_state_affected_instructions(self) -> bool:
        """True iff any block in this cfg contains an instruction may affect the state of the chain"""
        return any(b.has_state_affected_instructions for b in self.blocks)

    @property
    def has_revert_instructions(self) -> bool:
        """True iff any block in this cfg contains an instruction may affect the state of the chain"""
        return any(b.has_revert for b in self.blocks)

    @property
    def has_invalid_instructions(self) -> bool:
        """True iff any block in this cfg contains an instruction may affect the state of the chain"""
        return any(b.has_invalid for b in self.blocks)