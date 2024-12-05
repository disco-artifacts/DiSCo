from typing import *
from disco.app.descriptions.utils import find_return_pcs
from disco.common.structures.unit.semantic_unit import SemanticUnit
from collections import defaultdict
from disco.common.structures.unit.behavior_element import BehaviorType
from disco.common.structures.unit.semantic_unit import SemanticUnit
from disco.common.structures.unit.behavior_element import Behavior

def split_semantic_units(semantic_units:List[SemanticUnit]):
    condition_mapping = dict()
    behavior_mapping = dict()
    su_mapping = set()
    list_semantic_units = []
    
    for semantic_unit in semantic_units:
        if len(str(semantic_unit).split(" ")) > 10000:
            continue
        prunning_conditions = []
        for condition in semantic_unit.conditions:
            hash_cond = hash(condition)
            condition_mapping[hash_cond] = condition
            if not (condition.cstates['check_on_creates'] | condition.cstates['check_on_selfdestruct'] | condition.cstates['check_on_extcodesize']) and not "RETURNDATASIZE" in str(condition) and not "CALLDATASIZE" in str(condition) and "< 0x10000000000000000000000000000000000000000" not in str(condition) and not hash_cond in prunning_conditions: # 0x1000xxx is for Vyper code
                prunning_conditions.append(hash_cond) # deduplication conditions
        
        hash_behav = hash(semantic_unit.behavior)
        behavior_mapping[hash_behav] = semantic_unit.behavior
        
        hash_su = hash('-'.join(str(h) for h in prunning_conditions + [hash_behav]))
        if not hash_su in su_mapping:
            list_semantic_units.append((prunning_conditions, hash_behav))
            su_mapping.add(hash_su)
    return condition_mapping, behavior_mapping, list_semantic_units

def callreturn_propagation(semantic_units:List[SemanticUnit]):
    pc2semantic_units:Dict[str, SemanticUnit] = dict()
    for semantic_unit in semantic_units:
        if semantic_unit.behavior.behavior_type in [BehaviorType.CALL,BehaviorType.CALLCODE,BehaviorType.DELEGATECALL,BehaviorType.STATICCALL]:
            for pc in semantic_unit.behavior.behavior_pcs:
                pc2semantic_units[pc] = semantic_unit

    used_pcs:Dict[str, List[SemanticUnit]] = defaultdict(list)
    # TODO : returns in condition
    for semantic_unit in semantic_units:
        for hs in semantic_unit.behavior.lhs + [semantic_unit.behavior.rhs]:
            str_hs = str(hs)
            if "RETURN" in str_hs:
                callpc = find_return_pcs(str_hs)
                for pc in callpc:
                    used_pcs[pc].append(semantic_unit)
                    
        for condition in semantic_unit.conditions:
            str_condition = str(condition)
            if "RETURN" in str_condition:
                callpc = find_return_pcs(str_condition)
                for pc in callpc:
                    used_pcs[pc].append(semantic_unit)
    
    # TODO bug to fix
    call_returns = dict()
    for pc in sorted(list(set(used_pcs.keys()) & set(pc2semantic_units.keys())), key=lambda x:int(x,16), reverse=False):
        return_idx = f"v{len(call_returns)}"
        pc2semantic_units[pc].behavior.call_returns = return_idx
        for semantic_unit in used_pcs[pc]:
            if semantic_unit.behavior.depend_calls is not None:
                semantic_unit.behavior.depend_calls[pc] = return_idx
            else:
                semantic_unit.behavior.depend_calls = {pc:return_idx}
            
        call_returns[pc] = return_idx
    return semantic_units, call_returns