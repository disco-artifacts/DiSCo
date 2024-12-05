import typing as T

import disco.common.structures.evm_cfg as EVMCfg
import disco.common.structures.evm_path as EVMPath
import disco.common.structures.base.memtypes as MemT

from disco.common.structures.tac_op import TACOp, TACAssignOp

class TACBasicBlock(EVMCfg.EVMBasicBlock):
    """
    A basic block containing both three-address code, and its
    equivalent EVM code, along with information about the transformation
    applied to the stack as a consequence of its execution.
    """
    def __init__(self, entry_pc: int, exit_pc: int,
                 tac_ops: T.List[TACOp],
                 evm_ops: T.List[EVMCfg.EVMOp],
                 delta_stack: MemT.VariableStack):
        """
        Args:
          entry_pc: The pc of the first byte in the source EVM block
          exit_pc: The pc of the last byte in the source EVM block
          tac_ops: A sequence of TACOps whose execution is equivalent to the source
                   EVM code.
          evm_ops: the source EVM code.
          delta_stack: A stack describing the change in the stack state as a result
                       of running this block.
                       This stack contains the new items inhabiting the top of
                       stack after execution, along with the number of items
                       removed from the stack.
          cfg: The TACGraph to which this block belongs.

          Entry and exit variables should span the entire range of values enclosed
          in this block, taking care to note that the exit address may not be an
          instruction, but an argument of a PUSH.
          The range of pc values spanned by all blocks in a CFG should be a
          continuous range from 0 to the maximum value with no gaps between blocks.

          If the input stack state is known, obtain the exit stack state by
          popping off delta_stack.empty_pops items and add the delta_stack items
          to the top.
        """

        super().__init__(entry_pc, exit_pc, evm_ops)

        self.tac_ops = tac_ops
        """A sequence of TACOps whose execution is equivalent to the source EVM
           code"""

        self.delta_stack = delta_stack
        """
        A stack describing the stack state changes caused by running this block.
        MetaVariables named Sn symbolically denote the variable that was n places
        from the top of the stack at entry to this block.
        """
        
        self.condition_stay = False
        """True iff the condition is stay through the path"""

    @property
    def last_op(self) -> TACOp:
        return self.tac_ops[-1]

    def __str__(self):
        return "\n".join(str(tac_op) for tac_op in self.tac_ops)

    def _print_len(self) ->int:
        return len([tac_op for tac_op in self.tac_ops if tac_op.print_name])
    
    def reset_block_refs(self) -> None:
        """Update all operations and new def sites to refer to this block."""
        for op in self.tac_ops:
            op.block = self
            if isinstance(op, TACAssignOp) and isinstance(op.lhs, MemT.Variable):
                for site in op.lhs.def_sites:
                    site.block = self
            for arg in op.args:
                if isinstance(arg.value, MemT.Variable):
                    for site in arg.value.use_sites:
                        if site.block is None:
                            site.block = self

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.ident()
        )

class TACPath(EVMPath.EVMPath):
    SEP = "->"

    def __init__(self, blocks=None, from_transaction:bool=False, tx_hash:str="", entry_index:int=0, tac_blocks=None, function=None) -> None:
        super().__init__(blocks=blocks, from_transaction=from_transaction, entry_index=entry_index)

        self.tac_blocks:T.List[TACBasicBlock] = [] if tac_blocks is None else tac_blocks

        self.illegal:bool = False
        """true iff the path is infeasible"""

        self.function = function
        if self.function is not None:
            self.function.tac_paths.append(self)
       
        self.final_memory = None
        """Memory after executing the last operation, saved for state variable analysis"""
        
        self.transaction_hash:str=tx_hash
        """for debug the path"""

    def __iter__(self) -> TACBasicBlock:
        for block in self.tac_blocks:
            yield block

    def __str__(self) -> str:
        tac_str = "\n".join(block.ident()+":\n"+str(block) for block in self.tac_blocks)

        return tac_str

    def __repr__(self) -> str:
        tac_str = "->".join(block.ident() for block in self.tac_blocks)
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            tac_str
        )
        
    def __hash__(self) -> int:
        return hash("".join(b.ident() for b in self.tac_blocks))

    def __eq__(self, o) -> bool:
        return type(o) == type(self) and hash(o) == hash(self)

    def copy(self):
        tac_path = TACPath(blocks=self.blocks[:], tac_blocks=self.tac_blocks[:], from_transaction=self.from_transaction, tx_hash=self.transaction_hash, entry_index=self.entry_index, function=self.function)
        return tac_path
    
    @classmethod
    def from_evm_path(cls, evm_path: EVMPath.EVMPath):
        tac_path = cls(blocks=evm_path.blocks, from_transaction=evm_path.from_transaction, tx_hash=evm_path.transaction_hash, entry_index=evm_path.entry_index, function=evm_path.function)
        if tac_path.illegal:
            return None
        else:
            return tac_path