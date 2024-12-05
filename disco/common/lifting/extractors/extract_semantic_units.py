from collections import defaultdict
from typing import *

import disco.common.structures.opcodes as Opcodes
from disco.common.lifting.variables_analyzer import EVMVariableAnalyzer
from disco.common.structures.evm_variable import EVMArg, EVMProperty, EVMState, EVMLocal
from disco.common.structures.tac_path import TACPath
from disco.common.structures.tac_tree import (OpTree, expanded_condition_tree,
                                               tree_from_variable)
from disco.common.structures.unit.behavior_element import (Behavior,
                                                            BehaviorType)
from disco.common.structures.unit.condition_element import Condition
from disco.common.structures.unit.semantic_unit import SemanticUnit
from disco.solver.checker import PathChecker
from disco.common.utils.extractor_utils import post_semantic_unit_processing_v2 as post_semantic_unit_processing

def update_conditions(condition_list:List[Condition], current_block, exit_blocks):
    if len(condition_list) > 0:
        n_topop = 0
        exist = False
        # if block.ident() == exit_blocks.get(block.ident(), ""): 
        #     continue
        
        for i, condition in enumerate(condition_list):
        # for condition in reversed(condition_list):
            last_condition_block = condition.block.ident()
            # if not last_condition_block.condition_stay and last_condition_block.exit_block is not None and last_condition_block.exit_block.ident() == current_block.ident():
            #     n_topop += 1
            # else:
            #     break
            if exit_blocks.get(last_condition_block, "") == current_block.ident() or exit_blocks.get(last_condition_block, "") == last_condition_block:
                n_topop = len(condition_list) - i
                exist = True
                break
        
        if exist:    
            for _ in range(n_topop):
                condition_list.pop()
    
def extract_semantic_units(evm_analyzer:EVMVariableAnalyzer, tac_path:TACPath, check_feasibility:bool=True, debug:bool=False, exit_blocks:dict=None):
    """Analysis and extract semantic units from the path"""
    
    if exit_blocks is None:
        exit_blocks = dict()
    check_feasibility = False if tac_path.from_transaction else check_feasibility
    
    if check_feasibility:
        if evm_analyzer.checker is None:
            evm_analyzer.checker = PathChecker()
        checker = evm_analyzer.checker
        current_path_idents = ""
    
    conditions_list:List[Condition] = []    
    semantic_units:List[SemanticUnit] = []
    
    var_conditions_dep:Dict[str, Set[Condition]] = dict()
    # with_optimized = False
    sha3_optimized = False
    sstore_optimized = False
    with_ext_call = False

    for block_idx, block in enumerate(tac_path.tac_blocks[tac_path.entry_index:]):
        update_conditions(conditions_list, block, exit_blocks)        

        for tac_op in block.tac_ops:
            # update var condition dependency
            if hasattr(tac_op, 'lhs') and tac_op.lhs is not None:
                # if tac_op.lhs.identifier == 'V119@0x104@0xc5':
                #     print()
                may_conditions = set()
                
                for condition in conditions_list:
                    if not condition in may_conditions:
                        may_conditions.add(condition)
                        
                    for use_var in [condition.dst_var, condition.cond_var]:
                        may_conditions |= var_conditions_dep[use_var.value.identifier]

                for arg in tac_op.args:
                    if arg.value.def_sites is not None:
                       may_conditions |= var_conditions_dep[arg.value.identifier] 
                       
                var_conditions_dep[tac_op.lhs.identifier] = may_conditions
                
                # for condition in may_conditions:
                #     if condition not in conditions_list:
                #         conditions_list.append(condition)
            
            # Conditions           
            if tac_op.opcode == Opcodes.JUMPI:
                # skip self-loop conditions
                # if block.ident() == "0x226":
                #     print()
                
                dest, cond = tac_op.args
                # check whether the JUMPI condition is satisfied
                need_opposite = False
                next_tac_block = tac_path.tac_blocks[tac_path.entry_index+block_idx+1].tac_ops[0]
                if next_tac_block.pc != dest.value.const_value:
                    need_opposite = True
            
                # * indeed, check in tac stage
                if cond.value.is_const and cond.value.const_value == int(need_opposite):
                    tac_path.illegal = True
                    return [], {}

                # flag out const conditions
                if cond.value.is_const:
                    continue
                
                if check_feasibility:
                    current_path_idents += f"{str(block.ident())}-{int(need_opposite)}"
                
                condTree = tree_from_variable(cond.value, need_opposite=need_opposite)
            
                sha3_optimized |= condTree.with_optimized
                
                condition = Condition(
                    optree=condTree,
                    condition_pc=hex(tac_op.pc),
                    dst_var=dest,
                    cond_var=cond,
                    block=block,
                    block_ident=block.ident()
                )
                condition.set_cstates(condTree.cstates)

                conditions_list.append(condition)

                if condition.get_cstate("check_on_calls") or condition.get_cstate("check_on_creates") or condition.get_cstate("check_on_selfdestruct"):
                    conditions_list.pop()
                    continue
                
                elif condition.get_cstate("check_on_extcodesize"):
                    condTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(condTree, copy_state_variable=True)
                    alias_evm_variable = condTree_alias.sons[0].alias_evm_variable
                    if alias_evm_variable is not None and isinstance(alias_evm_variable, EVMState) and len(alias_evm_variable.keys) == 0:
                        alias_evm_variable = evm_analyzer.getEVMState(alias_evm_variable)
                        if alias_evm_variable.type.is_elementary:
                            alias_evm_variable.change_to_contract_type()
                    
                    condition.optree = expanded_condition_tree(condTree_alias)
                    
                    continue
                
                elif condition.get_cstate("check_on_caller"):
                    condTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(condTree, copy_state_variable=True)
                    
                    condition.optree = expanded_condition_tree(condTree_alias)
                    
                    if check_feasibility:
                        checker.add_constraint(condition.optree)
                    
                    continue
                
                elif condition.get_cstate("check_on_sload"):
                    condTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(condTree, copy_state_variable=True)
                    
                    condition.optree = expanded_condition_tree(condTree_alias)
                    
                    if condition.get_cstate("check_on_callreturn"):
                        for eqtree in condition.optree.get_all_sons("EQ"):
                            ltree, rtree = eqtree.sons
                            strltree, strrtree = str(ltree), str(rtree)
                            to_change_v = None
                            if rtree.alias_evm_variable is not None and ("CALLRETURN" in strltree or "CALLCODERETURN" in strltree):
                                behavior_pc = ltree.name.split("@")[1]
                                to_change_v = rtree.alias_evm_variable
                            elif ltree.alias_evm_variable is not None and ("CALLRETURN" in strrtree or "CALLCODERETURN" in strrtree):
                                behavior_pc = rtree.name.split("@")[1]
                                to_change_v = ltree.alias_evm_variable
                            if to_change_v is not None:
                                for su in semantic_units:
                                    if behavior_pc in su.behavior.behavior_pcs and str(su.behavior.rhs) in ["0x1","0x2"]:
                                        evm_analyzer.getEVMState(to_change_v).change_to_bytesM(32)
                                        break
                    
                    if check_feasibility:
                        checker.add_constraint(condition.optree)
                    
                    continue
                else:
                    condTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(condTree, copy_state_variable=True)
                    
                    condition.optree = expanded_condition_tree(condTree_alias)
                    
                    if check_feasibility:
                        checker.add_constraint(condition.optree)

                    continue
            
                
            # Behaviros
            elif tac_op.opcode in [Opcodes.SSTORE,
                                   Opcodes.CALL, Opcodes.CALLCODE, Opcodes.DELEGATECALL, Opcodes.STATICCALL,
                                   Opcodes.CREATE, Opcodes.CREATE2,
                                   Opcodes.SELFDESTRUCT]:
                if check_feasibility and checker.after_add_constraints:
                    checker.after_add_constraints = False
                    check_res = checker.check(current_path_idents)                
                
                    if check_res == -1:
                        # if debug:
                        #     print()
                        tac_path.illegal = True
                        return [], {}
                                
                _condition_lists = conditions_list[:]
                for arg in tac_op.args + tac_op.values:
                    for c in var_conditions_dep.get(arg.value.name,[]):
                        if not c in _condition_lists:
                            _condition_lists.append(c)
                for c in conditions_list[:]:
                    alias_evm_variable = c.optree.contained_evm_states
                    for s in alias_evm_variable:
                        for _c in var_conditions_dep.get(str(s), []):
                            if not _c in _condition_lists:
                                _condition_lists.append(_c)
                
                # Behaviors: sstore
                if tac_op.opcode in [Opcodes.SSTORE]:
                    # if block.ident() == "0x454":
                    #     print()
                    
                    slot_key, slot_value = tac_op.args
                    slot_key_tree, slot_value_tree = tree_from_variable(slot_key.value), tree_from_variable(slot_value.value)

                    sha3_optimized |= slot_key_tree.with_optimized
                    sha3_optimized |= slot_value_tree.with_optimized
                
                    if debug:
                        slot_key_tree.vis_graph().render(f"slot_key_tree",format="svg",cleanup=True)
                        slot_value_tree.vis_graph().render(f"slot_value_tree",format="svg",cleanup=True)
                    
                    sstore_updates = evm_analyzer.sstore_analysis(slot_key_tree, slot_value_tree)
                    
                    sstore_optimized |= len(sstore_updates) > 1
                    
                    for update_evm_state, update_value in sstore_updates:
                        if update_evm_state is not None and update_value is not None:
                            # evm_analyzer.evm_state_sstore_locations[str(update_evm_state)].append(tac_op.pc)
                            
                            # we should first set alias of update_value and then update_evm_state, else a := a-1 will be a1 = a1-1
                            # e.g., 0x21ab6c9fac80c59d401b37cb43f81ea9dde7fe34
                            update_value_alias = evm_analyzer.set_alias_evm_variable_for_tree(update_value)
                            key_str = ""
                            for v in update_evm_state.keys:
                                key_str += "[%s]"%(str(v))

                            update_evm_state.counts_mapping[key_str].append(tac_op.loc)
                            in_evm_state = evm_analyzer.getEVMState(update_evm_state)
                            if not (update_evm_state is in_evm_state or in_evm_state.counts_mapping[key_str] is update_evm_state.counts_mapping[key_str]):
                                in_evm_state.counts_mapping[key_str].append(tac_op.loc)
                                
                            update_evm_state.counts = len(update_evm_state.counts_mapping[key_str])

                            
                            # evm_analyzer.evm_state_ref[str(update_evm_state)][update_evm_state.counts] = update_value_alias
                            
                            if check_feasibility:
                                checker.add_sstore(update_evm_state, update_value_alias)

                            var_conditions_dep[str(update_evm_state)] = _condition_lists

                            # _condition_lists = [deepcopy(_c) for _c in conditions_list]
                            # _condition_lists = conditions_list
                            # # _condition_lists = conditions_list[:]
                            _behavior = Behavior(
                                rhs=update_evm_state,
                                lhs=[update_value_alias],
                                behavior_type=BehaviorType.SSTORE,
                                behavior_pcs=[hex(tac_op.pc)],
                                block_ident=block.ident(),
                            )
                            _semantic_unit = SemanticUnit(
                                conditions=_condition_lists,
                                behavior=_behavior,
                                belong_functions=[f"{tac_path.function.function_signature}_{tac_path.function.function_name}"]
                            )
                            
                            if "CALLRETURN" in update_value_alias.name or "CALLCODERETURN" in update_value_alias.name:
                                behavior_pc = update_value_alias.name.split("@")[1]
                                for su in semantic_units:
                                    # https://docs.soliditylang.org/en/v0.8.25/units-and-global-variables.html#mathematical-and-cryptographic-functions
                                    # 0x1 for ecrecover, 0x2 for sha256
                                    if behavior_pc in su.behavior.behavior_pcs and str(su.behavior.rhs) in ["0x2"]:
                                        evm_analyzer.getEVMState(update_evm_state).change_to_bytesM(32)
                                        break                        
                            
                            semantic_units.append(_semantic_unit)

                # Behaviors: call
                elif tac_op.opcode in [Opcodes.CALL, Opcodes.CALLCODE, Opcodes.DELEGATECALL, Opcodes.STATICCALL]:
                    if tac_op.opcode in [Opcodes.CALL, Opcodes.CALLCODE]:
                        gas, addr, value = tac_op.values[:3]
                        args = [] if len(tac_op.values) == 5 else tac_op.values[5:] 
                        
                        if isinstance(value, str):
                            valueTree = tree_from_variable(int("0x"+value,16))
                        else:
                            valueTree = tree_from_variable(value.value)
                        sha3_optimized |= valueTree.with_optimized
                        valueTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(valueTree)
              
                        lhs = [valueTree_alias]

                        try:
                            _args = []
                            for arg in args:
                                if isinstance(arg, str):
                                    argTree = tree_from_variable(int("0x"+arg,16))
                                else:
                                    argTree = tree_from_variable(arg.value)
                                sha3_optimized |= argTree.with_optimized
                                argTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(argTree)
                                _args.append(argTree_alias)
                                
                                with_ext_call = True
                            lhs.extend(_args)
                        except Exception as e:
                            pass

                    else:
                        with_ext_call = True
                        gas, addr = tac_op.values[:2]
                        value = None
                        args = [] if len(tac_op.values) == 4 else tac_op.values[4:]
                        
                        lhs = []

                        try:
                            _args = []
                            for arg in args:
                                if isinstance(arg, str):
                                    argTree = tree_from_variable(int("0x"+arg,16))
                                else:
                                    argTree = tree_from_variable(arg.value)
                                sha3_optimized |= argTree.with_optimized
                                argTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(argTree)
                                _args.append(argTree_alias)
                                
                            lhs.extend(_args)
                        except Exception as e:
                            pass
                    if isinstance(addr, str):
                        addrTree = tree_from_variable(int("0x"+addr,16))
                    else:
                        addrTree = tree_from_variable(addr.value)
                    sha3_optimized |= addrTree.with_optimized
                    
                    addrTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(addrTree)
                    
                    # value __set__
                    if len(args) > 0 or value is None:
                        _alias_evm_variable = addrTree_alias.alias_evm_variable
                        if _alias_evm_variable is not None:
                            alias_evm_variable = evm_analyzer.getEVMVariable(_alias_evm_variable)
                            if isinstance(alias_evm_variable, EVMState) and len(alias_evm_variable.keys) == 0:
                                if alias_evm_variable.type.is_elementary:
                                    alias_evm_variable.change_to_contract_type()
                            else:
                                alias_evm_variable.change_to_contract_type()

                    # force change to EVMVariable
                    if addrTree_alias.alias_evm_variable is None:
                        addrTree_alias.alias_evm_variable = EVMProperty(str(addrTree_alias.name))
                    
                    # _condition_lists = conditions_list[:]
                    _behavior = Behavior(
                        rhs=addrTree_alias.alias_evm_variable,
                        lhs=lhs,
                        behavior_type=getattr(BehaviorType, tac_op.opcode.name),
                        behavior_pcs=[hex(tac_op.pc)],
                        block_ident=block.ident(),
                    )
                    _semantic_unit = SemanticUnit(
                        conditions=_condition_lists,
                        behavior=_behavior,
                        belong_functions=[f"{tac_path.function.function_signature}_{tac_path.function.function_name}"]
                    )
                    
                    semantic_units.append(_semantic_unit)

                # Behaviors: create
                elif tac_op.opcode in [Opcodes.CREATE, Opcodes.CREATE2]:
                    value = tac_op.values[0]
                    if isinstance(value, str):
                        valueTree = tree_from_variable(int("0x"+value,16))
                    else:
                        valueTree = tree_from_variable(value.value)
                    sha3_optimized |= valueTree.with_optimized
                    valueTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(valueTree)

                    lhs = [valueTree_alias]

                    if tac_op.opcode == Opcodes.CREATE:
                        # CREATE has one argument: code
                        args = [] if len(tac_op.values) <= 3 else tac_op.values[3:]
                        for arg in args:
                            if isinstance(arg, str):
                                argTree = tree_from_variable(int("0x"+arg,16))
                            else:
                                argsTree = tree_from_variable(arg.value)
                            sha3_optimized |= argsTree.with_optimized
                            argsTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(argsTree)

                            lhs.append(argsTree_alias)
                    else:
                        # CREATE2 has two arguments: code and the salt
                        args = [] if len(tac_op.values) <= 4 else tac_op.values[4:]
                        for arg in args:
                            if isinstance(arg, str):
                                argTree = tree_from_variable(int("0x"+arg,16))
                            else:
                                argsTree = tree_from_variable(arg.value)
                            sha3_optimized |= argsTree.with_optimized
                            argsTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(argsTree)

                            lhs.append(argsTree_alias)
                        
                        salt = tac_op.values[3]
                        if isinstance(salt, str):
                            saltTree = tree_from_variable(int("0x"+salt,16))
                        else:
                            saltTree = tree_from_variable(salt.value)
                        sha3_optimized |= saltTree.with_optimized
                        saltTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(saltTree)

                        lhs.append(saltTree_alias)
                    
                    # _condition_lists = conditions_list[:]
                    _behavior = Behavior(
                        rhs=EVMProperty(name="newContract"),
                        lhs=lhs,
                        behavior_type=getattr(BehaviorType, tac_op.opcode.name),
                        behavior_pcs=[hex(tac_op.pc)],
                        block_ident=block.ident(),
                    )
                    _semantic_unit = SemanticUnit(
                        conditions=_condition_lists,
                        behavior=_behavior,
                        belong_functions=[f"{tac_path.function.function_signature}_{tac_path.function.function_name}"]
                    )
                    
                    semantic_units.append(_semantic_unit)
                        
                # Behaviors: destruct
                else:
                    addr = tac_op.values[0]
                    
                    if isinstance(addr, str):
                        addrTree = tree_from_variable(int("0x"+addr,16))
                    else:
                        addrTree = tree_from_variable(addr.value)
                    sha3_optimized |= addrTree.with_optimized
                    
                    addrTree_alias = evm_analyzer.set_alias_evm_variable_for_tree(addrTree)

                    # _condition_lists = conditions_list[:]
                    _behavior = Behavior(
                        rhs=addrTree_alias.alias_evm_variable,
                        lhs=[OpTree(name="BALANCE(ADDRESS)")],
                        behavior_type=getattr(BehaviorType, tac_op.opcode.name),
                        behavior_pcs=[hex(tac_op.pc)],
                        block_ident=block.ident(),
                    )
                    _semantic_unit = SemanticUnit(
                        conditions=_condition_lists,
                        behavior=_behavior,
                        belong_functions=[f"{tac_path.function.function_signature}_{tac_path.function.function_name}"]
                    )
                    
                    semantic_units.append(_semantic_unit)
    
    if check_feasibility:
        check_res = checker.check(current_path_idents)                
    
        if check_res == -1:
            tac_path.illegal = True
            return [], {}
    
    return post_semantic_unit_processing(semantic_units, exit_blocks=exit_blocks, language=evm_analyzer.language), {"sha3_optimized":sha3_optimized, "sstore_optimized":sstore_optimized, "with_extcall":with_ext_call}
    # return semantic_units, {"with_optimized":with_optimized}
