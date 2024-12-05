import json
import os
from collections import defaultdict
from typing import *

import disco.common.structures.opcodes as opcodes
from disco.common.structures.evm_cfg import EVMBasicBlock, EVMGraph, EVMOp
from disco.common.utils.contract_utils import removeCompilationInfo
from disco.common.utils.lifting_utils import STATE_AFFECTED_INSTRUCTIONS
from disco.static_analyzer.bytecode_parse import (EVMBytecodeParser,
                                                   EVMDasmParser)


def blocks_from_ops(ops: Iterable[EVMOp]) -> Iterable[EVMBasicBlock]:
    """
    Process a sequence of EVMOps and create a sequence of EVMBasicBlocks.

    Args:
      ops: sequence of EVMOps to be put into blocks.

    Returns:
      List of BasicBlocks from the input ops, in arbitrary order.
    """
    blocks = []

    # details for block currently being processed
    entry, exit = (0, len(ops) - 1) if len(ops) > 0 \
        else (None, None)
    current = EVMBasicBlock(entry, exit)

    # Linear scan of all EVMOps to create initial EVMBasicBlocks
    for i, op in enumerate(ops):
        op.block = current
        current.evm_ops.append(op)

        if op.opcode in (opcodes.SSTORE, opcodes.CREATE, opcodes.CREATE2, opcodes.CALL, opcodes.CALLCODE, opcodes.DELEGATECALL, opcodes.STATICCALL, opcodes.SELFDESTRUCT):
            current.has_state_affected_instructions = True
            
        if op.opcode in (opcodes.INVALID,):
            current.has_invalid = True
            
        if op.opcode in (opcodes.REVERT,):
            current.has_revert = True

        # Flow-altering opcodes indicate end-of-block
        if op.opcode.alters_flow():
            new = current.split(i + 1)
            blocks.append(current)

            # Mark all JUMPs as unresolved
            if op.opcode in (opcodes.JUMP, opcodes.JUMPI):
                current.has_unresolved_jump = True
            
            # Process the next sequential block in our next iteration
            current = new

        # JUMPDESTs indicate the start of a block.
        # A JUMPDEST should be split on only if it's not already the first
        # operation in a block. In this way we avoid producing empty blocks if
        # JUMPDESTs follow flow-altering operations.
        elif op.opcode == opcodes.JUMPDEST and len(current.evm_ops) > 1:
            new = current.split(i)
            blocks.append(current)
            current = new

        # Always add last block if its last instruction does not alter flow
        elif i == len(ops) - 1:
            blocks.append(current)

    return blocks

def get_evm_ops_from_bytecode(_bytecode:str):
    bytecode = removeCompilationInfo(_bytecode)[1]
    # example:0xbd83269db320bc9f805a9e2e92e2b5c63747ff62
    if len(bytecode) % 2 != 0:
        bytecode += "0"

    evm_ops = EVMBytecodeParser(bytecode).parse()
    return evm_ops

def get_evm_ops_from_dasm(dasm_path):
    with open(dasm_path, "r") as f:
        evm_ops = EVMDasmParser(f).parse()
    return evm_ops

def build_cfg_from_ops(evm_ops: Iterable[EVMOp], loop_uncover_times:int=5):
    evm_blocks = blocks_from_ops(evm_ops)
    return build_cfg_from_blocks(evm_blocks, loop_uncover_times)

def dump_insts(evm_ops, inst_path):
    type_ops = {f"optype_{v}":0 for v in range(0x10)}
    stat = {v:0 for v in STATE_AFFECTED_INSTRUCTIONS.values()}
    stat_loc = defaultdict(list)
    for i, op in enumerate(evm_ops):
        if op.opcode.name == "MISSING" and evm_ops[i-1].opcode.name == "STOP":break # remove the last swamhashes
        type_ops[f"optype_{op.opcode.code//0x10}"] += 1

        if op.opcode.name in stat:
            stat[op.opcode.name] += 1
            
        if (op.opcode.name in list(stat.keys()) and op.opcode.name != 'MISSING') or op.opcode.name == 'JUMPI':
            if hex(op.pc) not in stat_loc[op.opcode.name]:
                stat_loc[op.opcode.name].append(hex(op.pc))
            
    instat = {
            "type":"instat",
            "status":1,
            **dict(stat, **type_ops),
            "stat_loc":stat_loc
        }
        
    with open(inst_path,"w") as f:
        json.dump(instat, f, indent='\t')

def dump_analyzed_insts(evm_paths, analyzed_inst_path:str):
    stat_loc = defaultdict(list)
    for evm_path in evm_paths:
        for evm_block in evm_path.blocks:
            if evm_block.has_state_affected_instructions:
                for evm_op in evm_block.evm_ops:
                    if (evm_op.opcode.name in list(STATE_AFFECTED_INSTRUCTIONS.values()) and evm_op.opcode.name != 'MISSING') or evm_op.opcode.name == 'JUMPI':
                        if hex(evm_op.pc) not in stat_loc[evm_op.opcode.name]:
                            stat_loc[evm_op.opcode.name].append(hex(evm_op.pc))

    with open(analyzed_inst_path,"w") as f:
        json.dump({"status":1,"stat_loc":stat_loc}, f, indent='\t')

def build_cfg_from_blocks(evm_blocks:Iterable[EVMBasicBlock], loop_uncover_times:int=5):
    """"""
    cfg = EVMGraph(evm_blocks)
    cfg.resolveStaticEdges()
    cfg.resolveDynamicEdges(loop_uncover_times=loop_uncover_times) # change 5 to 1       
    return cfg
