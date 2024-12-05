from typing import *

import disco.common.structures.opcodes as Opcodes

from disco.common.structures.function import Function

def check_dispatcher(block) -> Tuple[bool, bool, str, str]:
    # for some vyper code, e.g., 0xa0a4a2af46af4cf37eacc495eedcae269ef2720e
    if len(block) >= 7:
        ins_1, ins_2, ins_3, ins_4, ins_5, ins_6, ins_7 = block.evm_ops[-7:]
        if ins_1.opcode.is_push() \
            and ins_2.opcode == Opcodes.PUSH1 and ins_2.value == 0x0 \
                and ins_3.opcode == Opcodes.MLOAD \
                    and ins_4.opcode in [Opcodes.EQ] \
                        and ins_5.opcode == Opcodes.ISZERO \
                            and ins_6.opcode.is_push() \
                                and ins_7.opcode == Opcodes.JUMPI:
                                    return ins_4.opcode in [Opcodes.EQ] and hex(ins_1.value) != "0x0", hex(ins_1.value), hex(ins_7.pc+1)

    if len(block) >= 6:
        ins_1, ins_2, ins_3, ins_4, ins_5, ins_6 = block.evm_ops[-6:]
        if ins_1.opcode == Opcodes.PUSH1 and ins_1.value == 4 \
            and ins_2.opcode == Opcodes.CALLDATASIZE \
                and ins_3.opcode in [Opcodes.LT] \
                    and ins_4.opcode == Opcodes.ISZERO \
                        and ins_5.opcode.is_push() \
                            and ins_6.opcode == Opcodes.JUMPI:
                                return True, "0x", hex(ins_6.pc+1)
                            
        if ins_1.opcode == Opcodes.DUP1 \
            and ins_2.opcode in [Opcodes.PUSH1, Opcodes.PUSH2, Opcodes.PUSH3, Opcodes.PUSH4] \
                and ins_3.opcode in [Opcodes.EQ]  \
                    and ins_4.opcode == Opcodes.ISZERO \
                        and ins_5.opcode.is_push() \
                            and ins_6.opcode == Opcodes.JUMPI:
                                return ins_3.opcode in [Opcodes.EQ] and hex(ins_2.value) != "0x0", hex(ins_2.value), hex(ins_6.pc+1)
        
        if ins_1.opcode in [Opcodes.PUSH1, Opcodes.PUSH2, Opcodes.PUSH3, Opcodes.PUSH4] \
                and ins_2.opcode == Opcodes.DUP2 \
                    and ins_3.opcode in [Opcodes.EQ] \
                        and ins_4.opcode == Opcodes.ISZERO \
                            and ins_5.opcode.is_push() \
                                and ins_6.opcode == Opcodes.JUMPI:
                                    return ins_3.opcode in [Opcodes.EQ] and hex(ins_1.value) != "0x0", hex(ins_1.value), hex(ins_6.pc+1)

    if len(block) >= 5:
        ins_1, ins_2, ins_3, ins_4, ins_5 = block.evm_ops[-5:]

        if ins_1.opcode == Opcodes.PUSH1 and ins_1.value == 4 \
            and ins_2.opcode == Opcodes.CALLDATASIZE \
                and ins_3.opcode in [Opcodes.LT] \
                    and ins_4.opcode.is_push() \
                        and ins_5.opcode == Opcodes.JUMPI:
                            return True, "0x", hex(ins_4.value)

        if ins_1.opcode == Opcodes.DUP1 \
            and ins_2.opcode in [Opcodes.PUSH1, Opcodes.PUSH2, Opcodes.PUSH3, Opcodes.PUSH4] \
                and ins_3.opcode in [Opcodes.EQ]  \
                    and ins_4.opcode.is_push() \
                        and ins_5.opcode == Opcodes.JUMPI:
                            return ins_3.opcode in [Opcodes.EQ] and hex(ins_2.value) != "0x0", hex(ins_2.value), hex(ins_4.value)
        
        if ins_1.opcode in [Opcodes.PUSH1, Opcodes.PUSH2, Opcodes.PUSH3, Opcodes.PUSH4] \
                and ins_2.opcode == Opcodes.DUP2 \
                    and ins_3.opcode in [Opcodes.EQ] \
                        and ins_4.opcode.is_push() \
                            and ins_5.opcode == Opcodes.JUMPI:
                                return ins_3.opcode in [Opcodes.EQ] and hex(ins_1.value) != "0x0", hex(ins_1.value), hex(ins_4.value)

    if len(block) >= 4:
        ins_1, ins_2, ins_3, ins_4 = block.evm_ops[-4:]
        if ins_1.opcode == Opcodes.CALLDATASIZE \
            and ins_2.opcode in [Opcodes.ISZERO] \
                and ins_3.opcode.is_push() \
                    and ins_4.opcode == Opcodes.JUMPI:
                        return True, "0x", hex(ins_3.value)        

    return False, "" , ""
    # is_dispatcher, sig, jumpdst
    
# \ref: https://github.com/tintinweb/ethereum-dasm/blob/a65257aa873f99ce572c7166b09b88faa6245160/ethereum_dasm/evmdasm.py#L390
def analyze_dispatchers(evm_blocks, dispatchers:dict=None) -> Tuple[str, int]:
    """Returns: the function signatures and the entry index of the body"""
    # dispatchers:Dict[block_ident, Tuple[fun_sig, jumpblock]]
    if dispatchers is None:
        dispatchers = dict()
        
    current_idx, current_sig, current_jumpblock = -1, "", ""
    for start_block_idx, block in enumerate(evm_blocks):
        if block.ident() in dispatchers:
            is_dispatcher, sig, jumpblock = dispatchers[block.ident()]
        else:
            is_dispatcher, sig, jumpblock = check_dispatcher(block)
            dispatchers[block.ident()] = (is_dispatcher, sig, jumpblock)
        if is_dispatcher:
            current_sig = sig
            current_jumpblock = jumpblock
            current_idx = start_block_idx
    
    if current_jumpblock != evm_blocks[current_idx + 1].ident():
        return "0x", current_idx + 1
    else:
        return current_sig, current_idx +1
    
def analyze_functions(tac_paths, _functions:Dict=None, _dispatcher:Dict=None, is_constructor:bool=False) -> Dict[str, Function]:
    if is_constructor:
        function = Function("", _function_name="constructor")
        for tac_path in tac_paths:
            tac_path.function = function
            function.add_path(tac_path,0)
        return {"":function}
    functions = dict() if _functions is None else _functions
    dispatchers = dict() if _dispatcher is None else _dispatcher
    for idx, tac_path in enumerate(tac_paths):
        if len(tac_path) == 0: continue
        func_sig, entry_index = analyze_dispatchers(tac_path.blocks, dispatchers)
        if func_sig != "0x":
            func_sig = "0x" + func_sig.replace("0x","").rjust(8,"0")
        
        if func_sig not in functions.keys():
            functions[func_sig] = Function(func_sig)
        functions[func_sig].add_path(tac_path, entry_index)
        tac_path.function = functions[func_sig]
        tac_path.entry_index = entry_index
        
    return functions