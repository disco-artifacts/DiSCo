from typing import *

# from disco.common.utils.mongodb_utils import get_name_by_signature
# from disco.common.utils.contract_utils import get_name_by_signature

class Function:
    """Create a function by the given parameters"""
    def __init__(self, signature:str, _has_state_affected_instructions:bool=False, _function_name=None) -> None:
        """initialize a function
        
        Args:
            signature(str): the function signature of the function.
            _has_state_affected_instructions(bool): true iff the function body has state-change opcode.
        """
        self.function_signature = signature if signature is not None else ""
        self._function_name = _function_name
        """The function signature"""

        self._has_state_affected_instructions = _has_state_affected_instructions
        self.blocks = set()
        # self.evm_paths = list()
        self.tac_paths = list() # after tac
        self.semantic_units = list()
        
        self.time_fetch_function = 0
    
    def add_block(self, block):
        self.blocks.add(block)

    def add_path(self, path, entry_index:int=0):
        for block in path.blocks[entry_index:]:
            self.add_block(block)
        self._has_state_affected_instructions |= path.has_state_affected_instructions
        # self.evm_paths.append(path)
        self.tac_paths.append(path)

    @property
    def function_name(self):
        if self._function_name is None:
            self._function_name = get_name_by_signature(self.function_signature)
        return self._function_name

    def dump(self) -> dict:
        return {
            "signature":self.function_signature,
            "name":self.function_name,
            "hsai":int(self._has_state_affected_instructions),
            "n_paths":len(self.tac_paths)
        }
    
    def __len__(self) -> int:
        return len(self.tac_paths)

    def __str__(self) -> str:
        blocks = "Block: " + ','.join(b.ident() for b in self.blocks)
        paths = "Paths: \n\t" + '\n\t'.join(str(p) for p in sorted(self.tac_paths, key=lambda v:len(v)))
        return "\n".join([self.function_signature, blocks, paths])

    def __hash__(self) -> int:
        return hash(self.function_signature)

    def __eq__(self, o: object) -> bool:
        return type(self) == type(o) and self.function_signature == o.function_signature

    def __repr__(self) -> str:
        return "<{0} object {1}, {2} {3}({4})>".format(
            self.__class__.__name__,
            self.function_name,
            hex(id(self)),
            "changed" if self._has_state_affected_instructions else "unchanged",
            self.function_signature
        )
