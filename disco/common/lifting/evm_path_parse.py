import copy
import typing as T
from collections import defaultdict

import disco.common.structures.base.memtypes as MemT
import disco.common.structures.evm_cfg as EVMCfg
import disco.common.structures.evm_memory as EVMMemory
import disco.common.structures.opcodes as Opcodes
from disco.common.structures.evm_path import EVMPath
from disco.common.structures.tac_arg import TACArg, TACLocRef
from disco.common.structures.tac_op import TACAssignOp, TACOp
from disco.common.structures.tac_path import TACBasicBlock, TACPath

def _path_illegal(block, next_block:str):
    last_op = block.last_op
    if last_op.opcode == Opcodes.JUMPI:
        dest, cond = last_op.args
        if dest.value.is_const and cond.value.is_const:
            dest_const = dest.value.const_value
            cond_const = int(cond.value.const_value !=0)
            return cond_const != int(next_block == hex(dest_const))
    return False

def transform_from_evm_path(evm_path:EVMPath, debug:bool=False, cfg=None, code=None) -> TACPath:
    tac_path = TACPath.from_evm_path(evm_path=evm_path)
    memory_affected = False
    if tac_path is None: return None, memory_affected
    f = None

    # next update tac blocks    
    destackifier = Destackifier(debug_file=f, code=code)

    tac_blocks = []

    for i in range(len(tac_blocks),len(tac_path.blocks)):
        block_idx = i
        b = tac_path.blocks[block_idx]
        
        tac_block = destackifier.convert_block(b)
        
        tac_blocks.append(tac_block)
        if block_idx+1<len(tac_path.blocks) and _path_illegal(tac_block, tac_path.blocks[block_idx+1].ident()):
            tac_path.illegal = True
            return [], memory_affected
    tac_path.tac_blocks.extend(tac_blocks)
    tac_path.final_memory = destackifier.memory

    tac_paths = [tac_path] if not tac_path.illegal else []

    if cfg is not None: 
        if len(tac_blocks) > 0: 
            last_op = tac_blocks[-1].last_op
            if last_op.opcode in [Opcodes.JUMP, Opcodes.JUMPI] and len(last_op.args) > 0 and last_op.args[0].value.is_const:
                dest = last_op.args[0].value.const_value

                dest_block = cfg.mapping.get(hex(dest), None)
                if dest_block is not None and dest_block.evm_ops[0].opcode == Opcodes.JUMPDEST:
                    cfg.add_edge(tac_path.blocks[-1], dest_block)
                    memory_affected = True
                    tac_paths = []
                    queue = [(tac_path, destackifier, dest_block)]
                    while len(queue) > 0:
                        tac_path, destackifier, current = queue.pop()
                        tac_block = destackifier.convert_block(current)
                        tac_path.tac_blocks.append(tac_block)
                        tac_path.blocks.append(current)
                        
                        if len(current.succs) == 0 and not current.last_op.opcode.abnormal_halts():
                            tac_paths.append(tac_path)
                        else:
                            for suc in current.succs:
                                if not suc.last_op.opcode.abnormal_halts():
                                    queue.append((tac_path.copy(), copy.deepcopy(destackifier), suc))                        
                else:
                    ori_tac_op = tac_blocks[-1].last_op
                    tac_blocks[-1].tac_ops[-1] = TACOp(Opcodes.REVERT, [], ori_tac_op.pc, ori_tac_op.loc, ori_tac_op.block) 
                    evm_block = cfg.mapping.get(tac_blocks[-1].ident())
                    evm_block.has_revert = True
    if debug:
        f.close()
       
    return [tac_path for tac_path in tac_paths if not tac_path.has_revert_instructions], memory_affected

class Destackifier:
    """Converts EVMBasicBlocks into corresponding TACBasicBlocks.

    Most instructions get mapped over directly, except:
        POP: generates no TAC op, but pops the symbolic stack;
        PUSH: generates a CONST TAC assignment operation;
        DUP, SWAP: these simply permute the symbolic stack, generate no ops;
        LOG0 ... LOG4: all translated to a generic LOG instruction

    Additionally, there is a NOP TAC instruction that does nothing, to represent
    a block containing EVM instructions with no corresponding TAC code.
    """

    def __init__(self, ops=None, stack=None, memory=None, stack_vars=0, block_entry=None, debug_file=None, code=None):
        self.n_ops = 0
        
        # A sequence of three-address operations
        self.ops = ops if ops is not None else []

        # The symbolic variable stack we'll be operating on.
        self.stack = stack if stack is not None else MemT.VariableStack()

        # The memory we'll be opearing on
        self.memory = memory if memory is not None else EVMMemory.EVMMemory()

        # Entry address of the current block being converted
        self.block_entry = block_entry

        # The number of TAC variables we've assigned,
        # in order to produce unique identifiers. Typically the same as
        # the number of items pushed to the stack.
        # We increment it so that variable names will be globally unique.
        self.stack_vars = stack_vars
        
        self.ext_calls = 0
        
        self.debug_file = debug_file
        self.code = code

    def __fresh_init(self, evm_block: EVMCfg.EVMBasicBlock) -> None:
        """Reinitialise all structures in preparation for converting a block."""
        self.ops = []
        self.block_entry = evm_block.evm_ops[0].pc \
            if len(evm_block.evm_ops) > 0 else None

    def __new_var(self, pc) -> MemT.Variable:
        """Construct and return a new variable with the next free identifier."""

        # Generate the new variable, numbering it by the implicit stack location
        # it came from.
        var = MemT.Variable(name="V{}@{}@{}".format(self.stack_vars, hex(pc), hex(self.block_entry)),
                               def_sites=[TACLocRef(None, self.block_entry)])
        self.stack_vars += 1
        return var

    # Add the last block's stack into the following one
    def convert_block(self, evm_block: EVMCfg.EVMBasicBlock) -> TACBasicBlock:
        """
        Given a EVMBasicBlock, produce an equivalent three-address code sequence and return the resulting TACBasicBlock.
        """
        self.__fresh_init(evm_block)

        for op in evm_block.evm_ops:
            self.__handle_evm_op(op)

        entry = evm_block.evm_ops[0].pc if len(evm_block.evm_ops) > 0 else None
        exit = evm_block.evm_ops[-1].pc + evm_block.evm_ops[-1].opcode.push_len() \
            if len(evm_block.evm_ops) > 0 else None

        # If the block is empty, append a NOP before continuing.
        if len(self.ops) == 0:
            self.ops.append(TACOp(Opcodes.NOP, [], entry))

        new_block = TACBasicBlock(entry, exit, self.ops, evm_block.evm_ops,
                                  self.stack)
        new_block.fallto_invalid = evm_block.fallto_invalid
        new_block.fallto_revert = evm_block.fallto_revert

        new_block.reset_block_refs()

        return new_block

    def __handle_evm_op(self, op: EVMCfg.EVMOp) -> None:
        """
        Produce from an EVM line its corresponding TAC instruction, if there is one,
        appending it to the current TAC sequence.
        """
        if op.opcode.is_swap():
            self.stack.swap(op.opcode.pop)
        elif op.opcode.is_dup():
            self.stack.dup(op.opcode.pop)
        elif op.opcode == Opcodes.POP:
            self.stack.pop()
        else:
            # When generating TAC operation from evm opcode, making use of value and value_extra generated from geth
            self.__gen_instruction(op)

    def __gen_instruction(self, op: EVMCfg.EVMOp) -> None:
        """
        Given a line, generate its corresponding TAC operation,
        append it to the op sequence, and push any generated
        variables to the stack.
        """
        inst = None
        new_var = self.__new_var(op.pc) if op.opcode.push == 1 else None

        # Set this variable's def site
        if new_var is not None:
            for site in new_var.def_sites:
                site.pc = op.pc

        # Generate the appropriate TAC operation.
        # Special cases first, followed by the fallback to generic instructions.
        # Although the opcode is PUSH, vandal still marks it as CONST to do arithemetic operations.

        # constant fold
        if op.opcode.is_push():
            args = TACArg(var=MemT.Variable(value=op.value, name="C"))
            inst = TACAssignOp(new_var, Opcodes.CONST, [args], op.pc, print_name=False)
            inst.lhs.value = args.value.value

        elif op.opcode.is_missing():
            args = [TACArg(var=MemT.Variable(value=op.value, name="C"))]
            inst = TACOp(op.opcode, args, op.pc)

        elif op.opcode.is_log():
            args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
            inst = TACOp(Opcodes.LOG, args, op.pc)

        # CALL code will also update memory
        elif op.opcode == Opcodes.MLOAD:
            offset_arg = self.stack.pop()
            offset = TACArg.from_var(offset_arg)
            inst = TACAssignOp(new_var, op.opcode, [offset], op.pc)

            value = self.memory.mload(offset.value)[0]

            if value is not None:
                if not value.is_const:
                    inst.lhs.value = value
                else:
                    args = value
                    inst.lhs.value = args.value

        elif op.opcode == Opcodes.MSTORE:
            offset_arg = self.stack.pop()
            offset = TACArg.from_var(offset_arg)
            value_arg = self.stack.pop()
            value = TACArg.from_var(value_arg)
            inst = TACOp(op.opcode, [offset, value], op.pc)
            
            self.memory.mstore(offset=offset.value, value=value.value)

            inst.values = [offset, value]

        elif op.opcode == Opcodes.MSTORE8:
            offset_arg = self.stack.pop()
            offset = TACArg.from_var(offset_arg)
            value_arg = self.stack.pop()
            value = TACArg.from_var(value_arg)
            inst = TACOp(op.opcode, [offset,value], op.pc)

            self.memory.mstore(offset=offset.value, value=value.value, length=1)

            inst.values = [offset, value]

        elif op.opcode == Opcodes.CALLDATACOPY:
            dstoffset_arg = self.stack.pop()
            dstoffset = TACArg.from_var(dstoffset_arg)
            offset_arg = self.stack.pop()
            offset = TACArg.from_var(offset_arg)
            length = self.stack.pop()
            length = TACArg.from_var(length)
            inst = TACOp(op.opcode, [dstoffset,offset,length], op.pc)

            self.memory.mstore(offset=dstoffset.value, value=EVMMemory.DynamicVariable(MemT.Variable(name=f"CALLDATACOPY@{hex(op.pc)}"), offset=offset.value, length=length.value), length=length.value)

            pass
        
        elif op.opcode == Opcodes.CODECOPY:
            dstoffset_arg = self.stack.pop()
            dstoffset = TACArg.from_var(dstoffset_arg)
            offset_arg = self.stack.pop()
            offset = TACArg.from_var(offset_arg)
            length = self.stack.pop()
            length = TACArg.from_var(length)
            inst = TACOp(op.opcode, [dstoffset,offset,length], op.pc)

            if self.code is not None and offset.value.is_const and length.value.is_const:
                if self.code.startswith("0x"):
                    self.code = self.code[2:]
                value = self.code[offset.value.const_value*2:offset.value.const_value*2+length.value.const_value*2]
                for i in range(length.value.const_value//32):
                    o = MemT.Variable(value=dstoffset.value.const_value+i*32, name="C")
                    self.memory.mstore(offset=o, value=MemT.Variable(value=int(value[i*64:i*64+64], 16), name="C"))
                # self.memory.mstore(offset=dstoffset.value, value=MemT.Variable(value=value, name="C"), length=length.value)
            else:
                self.memory.mstore(offset=dstoffset.value, value=EVMMemory.DynamicVariable(MemT.Variable(name=f"CODECOPY@{hex(op.pc)}"), offset=offset.value, length=length.value), length=length.value)

        elif op.opcode == Opcodes.EXTCODECOPY:
            addr_arg = self.stack.pop()
            addr = TACArg.from_var(addr_arg)
            dstoffset_arg = self.stack.pop()
            dstoffset = TACArg.from_var(dstoffset_arg)
            offset_arg = self.stack.pop()
            offset = TACArg.from_var(offset_arg)
            length = self.stack.pop()
            length = TACArg.from_var(length)
            inst = TACOp(op.opcode, [addr, dstoffset,offset,length], op.pc)

            self.memory.mstore(offset=dstoffset.value, value=EVMMemory.DynamicVariable(MemT.Variable(name=f"EXTCODECOPY@{hex(op.pc)}"), offset=offset.value, length=length.value), length=length.value)
        
        elif op.opcode == Opcodes.RETURNDATACOPY:
            dstoffset_arg = self.stack.pop()
            dstoffset = TACArg.from_var(dstoffset_arg)
            offset_arg = self.stack.pop()
            offset = TACArg.from_var(offset_arg)
            length = self.stack.pop()
            length = TACArg.from_var(length)
            inst = TACOp(op.opcode, [dstoffset,offset,length], op.pc)

            self.memory.mstore(offset=dstoffset.value, value=EVMMemory.DynamicVariable(MemT.Variable(name=f"RETURNDATACOPY@{hex(op.pc)}"), offset=offset.value, length=length.value), length=length.value)
        
        elif op.opcode in (Opcodes.CALL, Opcodes.CALLCODE, Opcodes.DELEGATECALL, Opcodes.STATICCALL):
            args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
            inst = TACAssignOp(new_var, op.opcode, args, op.pc)

            if len(args) == 7:
                gas, addr, value, argsOffset, argsLength, retOffset, retLength = args
                inst.values = [gas, addr, value, argsOffset, argsLength]
            else:
                gas, addr, argsOffset, argsLength, retOffset, retLength = args
                inst.values = [gas, addr, argsOffset, argsLength]
            call_args = self.memory.mload(offset=argsOffset.value, length=argsLength.value)
            self.memory.mstore(offset=retOffset.value, value=EVMMemory.DynamicVariable(MemT.Variable(name=f"{op.opcode.name}RETURN@{hex(op.pc)}"), offset=argsOffset.value, length=argsLength.value), length=retLength.value)

            if len(call_args) > 0:
                inst.values += [TACArg.from_var(var) for var in call_args]

            self.ext_calls += 1

        elif op.opcode in (Opcodes.RETURNDATASIZE, ):
            args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
            inst = TACAssignOp(new_var, op.opcode, args, op.pc)
            
            if self.ext_calls == 0:
                inst.lhs.value = 0

        elif op.opcode in (Opcodes.CREATE, Opcodes.CREATE2):
            args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
            inst = TACAssignOp(new_var, op.opcode, args, op.pc)

            inst.values.extend(args)
            call_args = self.memory.mload(offset=args[1].value, length=args[2].value)
            if len(call_args) > 0:
                inst.values += [TACArg.from_var(var) for var in call_args]

        elif op.opcode in (Opcodes.SELFDESTRUCT, ):
            addr = self.stack.pop()
            args = [TACArg.from_var(addr)]
            inst = TACOp(op.opcode, args, op.pc)
            
            inst.values.extend(args)
        
        # Storage operations
        elif op.opcode == Opcodes.SLOAD:
            index_arg = self.stack.pop()
            args = [TACArg.from_var(index_arg)]
            inst = TACAssignOp(new_var, op.opcode, args, op.pc)

        elif op.opcode == Opcodes.SSTORE:
            index_arg = self.stack.pop()
            value_arg = self.stack.pop()
            args = [TACArg.from_var(index_arg),TACArg.from_var(value_arg)]
            inst = TACOp(op.opcode, args, op.pc)

        elif op.opcode == Opcodes.SHA3:
            #TO Check;
            offset = TACArg.from_var(self.stack.pop())
            length = TACArg.from_var(self.stack.pop())
            inst = TACAssignOp(new_var, op.opcode, args=[offset, length], pc=op.pc)

            # the value is a list
            sha3key = self.memory.mload(offset=offset.value, length=length.value)
            inst.values = [offset, length] + [TACArg.from_var(var) for var in sha3key]

        # e.g., 0x64d56f087d87cdaeac8119c69c48d0d440d560a7
        elif op.opcode == Opcodes.PC:
            # pass
            inst = TACAssignOp(new_var, op.opcode, [], op.pc)
            inst.lhs.value = op.pc

        elif new_var is not None:
            args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
            inst = TACAssignOp(new_var, op.opcode, args, op.pc)

        else:
            args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
            inst = TACOp(op.opcode, args, op.pc)
        
        if isinstance(inst, TACAssignOp) and len(inst.args) == 0 and inst.lhs.value is None:
            inst.lhs.value = inst.opcode.name
        
        if op.opcode.is_arithmetic():
            if inst.constant_args():
                rhs = [arg.value for arg in inst.args]
                inst.lhs.value = MemT.Variable.arith_op(op.opcode.name, rhs).value

        # * propagate values from transactions
        if len(op.values) > 0:
            inst.real_values = op.values

        # This var must only be pushed after the operation is performed.
        if new_var is not None:
            self.stack.push(new_var)

        if inst is not None:
            inst.loc = self.n_ops
            self.n_ops += 1
            if self.debug_file is not None:
                self.debug_file.write(str(inst) + "\n")
                self.debug_file.flush()

            self.ops.append(inst)

            for arg in inst.args:
                var = arg.value
                if var.use_sites is None:
                    var.use_sites = [TACLocRef(None, op.pc)]
                else:
                    var.use_sites.append(TACLocRef(None, op.pc))

    def __deepcopy__(self, memodict={}):
        return type(self)(ops=self.ops[:], 
                          stack=copy.deepcopy(self.stack), 
                          memory=copy.deepcopy(self.memory), 
                          block_entry=self.block_entry, 
                          stack_vars=self.stack_vars)
