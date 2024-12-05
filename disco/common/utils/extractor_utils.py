from collections import defaultdict
from typing import *

from disco.common.structures.unit.behavior_element import (Behavior,
                                                            BehaviorType)
from disco.common.structures.unit.condition_element import Condition
from disco.common.structures.unit.semantic_unit import SemanticUnit

# TODO : multiple pcs
def is_or_add(semantic_unit):
    if len(semantic_unit.behavior.lhs) == 1:
        optree = semantic_unit.behavior.lhs[0]
        if optree.name == "OR":
            lson = optree.sons[0]
            if lson.name == "ADD" and str(lson.sons[0]) == str(lson.sons[1]):
                return True
    return False

def is_update_length(semantic_unit):
    if not semantic_unit.behavior.rhs.type_is_dynamic:
        return False
    else:
        return is_or_add(semantic_unit)

def sat_tree(optree):
    # return True
    if len(optree.sons) == 0:
        return True
    elif len(optree.sons) == 2:
        name = optree.name
        if name in ['GT','LT','EQ'] and any(tree.alias_evm_variable is not None and hasattr(tree.alias_evm_variable, 'is_dynamic') and tree.alias_evm_variable.is_dynamic for tree in optree.sons):
            return False
        else:
            return all(sat_tree(s) for s in optree.sons)
    else:
        return all(sat_tree(s) for s in optree.sons)

def pruning_unnecessary_conditions(semantic_unit:SemanticUnit):
    new_cond = []
    for c in semantic_unit.conditions:
        if sat_tree(c.optree):       
            new_cond.append(c)
    semantic_unit.conditions = new_cond
    return semantic_unit

def check_su_with_dynamics(semantic_unit):
    if semantic_unit.behavior.rhs.type_is_dynamic:
        return True
    elif any([lhs.alias_evm_variable is not None and lhs.alias_evm_variable.type_is_dynamic for lhs in semantic_unit.behavior.lhs]):
        return True
    elif any([hasattr(evm_arg, 'type_is_dynamic') and evm_arg.type_is_dynamic for lhs in semantic_unit.behavior.lhs for evm_arg in lhs.contained_evm_args]):
        return True
    return False

def post_semantic_unit_processing_v2(_semantic_units:List[SemanticUnit], exit_blocks, language:str="Solidity"):
    """For dynamic typed updates, merge them into one"""
    semantic_units = []
    
    # su_same_condition:Dict[str, List[SemanticUnit]] = defaultdict(list)

    su_with_dynamics:List[SemanticUnit] = []
    su_same_rhs:Dict[str, List[SemanticUnit]] = defaultdict(list)
    for semantic_unit in _semantic_units:
        if semantic_unit.behavior.behavior_type == BehaviorType.SSTORE and semantic_unit.behavior.rhs.type_is_dynamic:
            su_same_rhs[semantic_unit.behavior.rhs.details(with_counts=False, with_keys=False)].append(semantic_unit)
        elif check_su_with_dynamics(semantic_unit):
            su_with_dynamics.append(semantic_unit)
            if semantic_unit.behavior.behavior_type == BehaviorType.SSTORE and not semantic_unit.behavior.rhs.type_is_dynamic:
                semantic_unit.behavior.rhs.change_to_string_type()
            
        else:
            new_cond = []
            for c in semantic_unit.conditions:
                if exit_blocks.get(c.block_ident, "") == c.block_ident:
                    continue
                new_cond.append(c)
            new_su = SemanticUnit(
                conditions=new_cond,
                behavior=semantic_unit.behavior,
                belong_functions=semantic_unit.belong_functions
            )
            if not is_update_length(new_su):
                semantic_units.append(pruning_unnecessary_conditions(new_su))
    
    __semantic_units = []
    for _sus in su_same_rhs.values():
        __rhs = _sus[0].behavior.rhs
        __lhs = _sus[0].behavior.lhs
        __pcs = []
        for ___su in _sus:
            __pcs.extend(___su.behavior.behavior_pcs)

        if __rhs.type.is_array:
            __rhs = _sus[-1].behavior.rhs
            __lhs = _sus[-1].behavior.lhs
            behavior_type = getattr(BehaviorType, 'PUSH')
            __rhs.keys.clear()
        else:        
            # dynamic mapping/basic dynamics
            behavior_type = getattr(BehaviorType, 'SSTORE')
            ___lhs = []
            if language == "Vyper":
                ___lhs.append(__lhs[0])
            else:
                add_sons = __lhs[0].get_all_sons("ADD")
                if len(add_sons) == 0:
                    ___lhs.append(__lhs[0])
                else:
                    for add_son in add_sons:
                        if str(add_son.sons[0]) == str(add_son.sons[1]):
                            if add_son.sons[0].alias_evm_variable is not None and isinstance(add_son.sons[0].alias_evm_variable.keys, str):
                                add_son.sons[0].alias_evm_variable.keys = ""
                            
                            ___lhs.append(add_son.sons[0])
                            break
            __lhs = ___lhs
        _behavior = Behavior(
            rhs=__rhs,
            lhs=__lhs,
            behavior_type=behavior_type,
            behavior_pcs=__pcs,
            block_ident=_sus[-1].behavior.block_ident,
        )
        _conditions = []
        contained_evm_variables = [__rhs.details(with_counts=False, with_keys=True)] + [lhs.details(with_counts=False, with_keys=True) for lhs in __lhs]
        for c in _sus[-1].conditions:
            if len(c.optree.contained_evm_states + c.optree.contained_evm_args) > 0 and all(es.details(with_counts=False, with_keys=True) in contained_evm_variables for es in c.optree.contained_evm_states + c.optree.contained_evm_args):
                continue
            _conditions.append(c)
        
        __semantic_units.append(
            SemanticUnit(
                conditions=_conditions,
                behavior=_behavior,
                belong_functions=_sus[-1].belong_functions
            )
        )

    if language == "Vyper" and len(__semantic_units) > 0:
        ___semantic_units = [__semantic_units[0]]
        base_pcs = __semantic_units[0].behavior.behavior_pcs
        for su in __semantic_units[1:]:
            if sum(hash(p) for p in su.behavior.behavior_pcs) == sum(hash(p) for p in base_pcs):
                continue
            else:
                ___semantic_units.append(su)
                base_pcs = su.behavior.behavior_pcs
        
        __semantic_units = ___semantic_units
    
    semantic_units.extend([pruning_unnecessary_conditions(su) for su in __semantic_units if not is_update_length(su)])
        
    for semantic_unit in su_with_dynamics:
        _conditions = []
        dynamics = []
        if semantic_unit.behavior.rhs.type_is_dynamic:
            dynamics.append(semantic_unit.behavior.rhs.details(with_counts=False, with_keys=True))
        for lhs in semantic_unit.behavior.lhs:
            if lhs.alias_evm_variable is not None and lhs.alias_evm_variable.type_is_dynamic:
                dynamics.append(lhs.alias_evm_variable.details(with_counts=False, with_keys=True))
        
            for evm_arg in lhs.contained_evm_args + lhs.contained_evm_states:
                if hasattr(evm_arg, 'type_is_dynamic') and evm_arg.type_is_dynamic:
                    dynamics.append(evm_arg.details(with_counts=False, with_keys=True))        
        
        for c in semantic_unit.conditions:
            if len(c.optree.contained_evm_states + c.optree.contained_evm_args) > 0 and all(es.details(with_counts=False, with_keys=True) in dynamics for es in c.optree.contained_evm_states + c.optree.contained_evm_args):
                continue
            _conditions.append(c)

        semantic_unit.conditions = _conditions
        if not is_update_length(semantic_unit):
            semantic_units.append(pruning_unnecessary_conditions(semantic_unit))
    return semantic_units
