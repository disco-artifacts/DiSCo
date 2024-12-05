import copy
import typing as T

import disco.common.structures.opcodes as Opcodes
from disco.common.structures.tac_arg import TACArg

import disco.common.structures.base.memtypes as MemT

class TACOp:
    """
    A Three-Address Code operation.
    Each operation consists of an opcode object defining its function,
    a list of argument variables, and the unique program counter address
    of the EVM instruction it was derived from.
    """

    def __init__(self, opcode: Opcodes.OpCode, args: T.List[TACArg],
                 pc: int, loc: int = None, block=None, print_name:bool=True, values:T.List=None, real_values:T.List=None):
        """
        Args:
          opcode: the operation being performed.
          args: Variables that are operated upon.
          pc: the program counter at the corresponding instruction in the original bytecode.
          block: the block this operation belongs to. Defaults to None.
          loc: the position of the opcode

        LOC <space> OPCODE <space> ARGS

        where
          - LOC is the global program counter
          - OPCODE is an object representing an EVM instruction code
          - ARGS are the OPERANDS of the OPCODE
          - <spaces> is a variable number of spaces
        """
        self.opcode = opcode
        self.args = args
        self.pc = pc
        self.loc = loc
        self.block = block
        self.print_name = print_name

        # * inherited from evm_op
        # * attributes from transactions

        self.values = [] if values is None else values
        self.real_values = [] if real_values is None else real_values
        # self.transaction_index = None
        # self.transaction_value = None
        # """Value of SLOAD/SSTORE"""

        # self.transaction_index = None
        # self.transaction_value = None
        # """Value of MLOAD/MSTORE"""


    def __str__(self) -> str:
        return "{}_{}_{}:{} {}".format(hex(self.pc), self.pc, self.loc, self.opcode," ".join([str(arg) for arg in self.args]))

    def __repr__(self):
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        )

    def constant_args(self) -> bool:
        """True iff each of this operations arguments is a constant value."""
        return all([arg.value.is_const for arg in self.args])

    def constrained_args(self) -> bool:
        """True iff none of this operations arguments is value-unconstrained."""
        return all([not arg.value.is_unconstrained for arg in self.args])

    def __deepcopy__(self, memodict={}):
        new_op = type(self)(self.opcode,
                            copy.deepcopy(self.args, memodict),
                            self.pc,
                            self.loc,
                            self.block)
        return new_op
    


class TACAssignOp(TACOp):
    """
    A TAC operation that additionally takes a variable to which
    this operation's result is implicitly bound.
    """
    def __init__(self, lhs: MemT.Variable, opcode: Opcodes.OpCode,
                 args: T.List[TACArg], pc: int, block=None, 
                 loc: int = None, print_name: bool = True):
        """
        Args:
          lhs: The Variable that will receive the result of this operation.
          opcode: the operation being performed.    
          pc: the program counter at the corresponding instruction in the original bytecode.
          block: the block this operation belongs to. Defaults to None.
          loc: the position of the opcode.
          print_name: Some operations (e.g. CONST) don't need to print their
                      name in order to be readable.
        """
        super().__init__(opcode, args, pc, loc, block)
        self.lhs = lhs
        self.print_name = print_name

    def __str__(self):
        arglist = ([str(self.opcode)] if self.print_name else []) \
                  + [str(arg) for arg in self.args]
        # arglist = [str(self.opcode)] \
        #           + [str(arg) for arg in self.args]
        return "{}_{}_{}: {} = {}".format(hex(self.pc), self.pc, self.loc, str(self.lhs), " ".join(arglist))        

    def __deepcopy__(self, memodict={}):
        """
        Return a copy of this TACAssignOp, deep copying the args and vars,
        but leaving block references unchanged.
        """
        new_op = type(self)(copy.deepcopy(self.lhs, memodict),
                            self.opcode,
                            copy.deepcopy(self.args, memodict),
                            self.pc,
                            self.block,
                            self.loc, 
                            self.print_name)
        return new_op
    
    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        )
