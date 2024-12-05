from typing import *

import disco.common.structures.opcodes as opcodes
from disco.common.exceptions.StackHandlingExceptions import StackSizeOverflow

class EVMStack:
    MAX_STACK_SIZE:int = 1024
    STACK_TAIL_SIZE:int = 48
    STACK_TAIL_THRESHOLD:int = 200
   
    def __init__(self, stack:List[int]=None) -> None:
        """Initialize a symbolic execution stack, for stack[-1] if the top"""
        self.stack = stack if stack is not None else []

    def __repr__(self) -> str:
        return "<{0} object {1}: {2}>".format(
            self.__class__.__name__,
            id(self),
            self.stack
        )

    def valid_stack(self) -> bool:
        if len(self.stack) > self.MAX_STACK_SIZE:
            raise StackSizeOverflow(f"stack overflow, {len(self.stack)}>{self.MAX_STACK_SIZE}")

    def copy(self):
        return type(self)(self.stack[:])

    def executeEVMOp(self, evm_op):
        # PUSH
        if evm_op.opcode == opcodes.PC:
            self.executePC(evm_op)
        elif evm_op.opcode.is_push():
            self.executePush(evm_op)
        # DUP
        elif evm_op.opcode.is_dup():
            self.executeDup(evm_op)
        # SWAP
        elif evm_op.opcode.is_swap():
            self.executeSwap(evm_op)
        # POP
        elif evm_op.opcode == opcodes.POP:
            self.executePop()
        # AND
        elif evm_op.opcode == opcodes.AND:
            self.executeAnd()
        else:
            for i in range(evm_op.opcode.pop):
                self.stack.pop()

            for i in range(evm_op.opcode.push):
                self.stack.append(None)

        self.valid_stack()

    def peek(self, idx=0) -> int:
        """Peek the value from stack"""
        return self.stack[-(idx+1)]

    def executePC(self, evm_op):
        self.stack.append(evm_op.pc)
        self.valid_stack()

    def executePush(self, evm_op):
        self.stack.append(evm_op.value)
        self.valid_stack()

    def executeDup(self, evm_op):
        self.stack.append(self.stack[-(evm_op.opcode.code - opcodes.DUP1.code + 1)])
        self.valid_stack()

    def executeSwap(self, evm_op):
        swap_idx = evm_op.opcode.code - opcodes.SWAP1.code + 1 + 1
        tmp = self.stack[-1]
        self.stack[-1] = self.stack[-swap_idx]
        self.stack[-swap_idx] = tmp
        self.valid_stack()

    def executePop(self):
        self.stack.pop()

    def executeAnd(self):
        a = self.stack.pop()
        b = self.stack.pop()
        if a is not None and b is not None:
            self.stack.append(a & b)
        else:
            self.stack.append(None)
        self.valid_stack()