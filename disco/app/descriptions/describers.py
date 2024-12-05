from collections import defaultdict
from typing import *

from disco.app.descriptions.rules import (INDEX_MAPPING, OP_DESCRIPTIONS,
                                           PROPERTY_DESCRIPTIONS)
from disco.app.descriptions.utils import (anti_capitalize, optimize_phrase,
                                           pretty_bignum, to_checksum_address)
from disco.common.structures.evm_variable import (EVMArg, EVMProperty,
                                                   EVMState, EVMVariable)
from disco.common.structures.tac_tree import OpTree, expanded_condition_tree
from disco.common.structures.unit.behavior_element import (Behavior,
                                                            BehaviorType)
from disco.common.structures.unit.condition_element import Condition
from disco.common.utils.mongodb_utils import get_name_by_signature


class OrderedBehavior:
    def __init__(self, behavior:Behavior, inferred_names, dep_behaviors=None, following_behaviors:List=None) -> None:
        self.behavior = behavior
        self.inferred_names = inferred_names
        self.dep_behaviors = [] if dep_behaviors is None else dep_behaviors
        self.following_behaviors = [] if following_behaviors is None else following_behaviors

    def describe_behavior(self, deep:int=1) -> str:
        description = " "*2*deep + "- " + describe_behavior(self.behavior, self.inferred_names)
        described_afterthat = False
        for behavior in self.following_behaviors:
            # description += behavior.describe_behavior(deep+1) + "\n"
            behavior.dep_behaviors.pop()
            if len(behavior.dep_behaviors) == 0:
                if not described_afterthat:
                    description = description.rstrip(".")
                    description += ". Afterthat, \n"
                    described_afterthat = True
                description += behavior.describe_behavior(deep+1) + "\n"
        
        return description.strip("\n")

def unshift_args(_args):
    args = []
    for arg in _args:
        if "0x1000000000000000000000000*" in arg:
            args.append(arg.replace("0x1000000000000000000000000*","").lstrip("(").rstrip(")"))
        else:
            args.append(arg)
    return args

def describe_multi_args(_args):
    if len(_args) == 0:
        return ""
    elif len(_args) == 1:
        return _args[0]
    else:
        return ", ".join(_args[:-1]) + ", and " + _args[-1]

# TODO : change called function signature to function name
def describe_behavior(behavior:Behavior, inferred_names):
    if behavior.behavior_type == BehaviorType.SSTORE:
        try:
            state_type = behavior.rhs.type
        except:
            state_type = None
        update_value = describe_op_tree(behavior.lhs[0], inferred_names, behavior.depend_calls, state_type=state_type) if len(behavior.lhs) > 0 else "0"
        # update_value = update_type(update_value, behavior.rhs.type)
        target = describe_evm_state(behavior.rhs, inferred_names, behavior.depend_calls)
        if "the" in target:
            return f"{target} will be updated to {update_value}."
        else:
            return f"the state variable {target} will be updated to {update_value}."
    elif behavior.behavior_type == BehaviorType.PUSH:
        pushed_value = f"the value {describe_op_tree(behavior.lhs[0], inferred_names, behavior.depend_calls)}" if len(behavior.lhs) > 0 else "0"
        return f"{pushed_value} will be put to {describe_evm_state(behavior.rhs, inferred_names, behavior.depend_calls)}."
    elif behavior.behavior_type == BehaviorType.CREATE:
        creation_code = describe_op_tree(behavior.lhs[1], inferred_names, behavior.depend_calls) if len(behavior.lhs) > 0 else ""
        return f"it creates a new smart contract with creation code {creation_code}"
    elif behavior.behavior_type == BehaviorType.CREATE2:
        creation_code = describe_op_tree(behavior.lhs[1], inferred_names, behavior.depend_calls) if len(behavior.lhs) > 0 else ""
        salt_value = describe_op_tree(behavior.lhs[2], inferred_names, behavior.depend_calls) if len(behavior.lhs) > 1 else ""
        return f"it creates a new smart contract with creation code {creation_code} and salt value {salt_value}"
    elif behavior.behavior_type == BehaviorType.CALL or behavior.behavior_type == BehaviorType.CALLCODE:
        if len(behavior.lhs) > 1:
            ethers = f"{describe_op_tree(behavior.lhs[0], inferred_names, behavior.depend_calls)}"
            if ethers == "0x0" or ethers == "0":
                ethers = ""
            else:
                if ethers == "BALANCE ADDRESS":
                    ethers = "ether valued the balance of this contract"
                else:
                    ethers = f"ether valued {ethers}"

            args = []
            for lhs in behavior.lhs[1:]:
                des_arg = describe_op_tree(lhs, inferred_names, behavior.depend_calls)
                args.append(des_arg)

            str_evm_variable = describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)
            # support built-in functions
            if str_evm_variable in ['0x1','0x2']:
                if str_evm_variable == '0x1':
                    des = f"it calls a built-in function ecrecover."
                else:
                    des = f"it calls a built-in function sha256."
                called_args = describe_multi_args(unshift_args(args))
            else:
                if len(args) == 0:
                    des = f"it calls an external contract {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}"
                    if len(ethers) > 0:
                        des += " with " + ethers
                    return des
                else:
                    if len(args[0]) <= 10: # called signature
                        called_signature = args[0]
                    else:
                        # 0x8fd1e427396ddb511533cf9abdbebd0a7e08da35
                        if "SHA3(0x7472616e7366657228616464726573732c75696e7432353629)" in args[0]:
                            called_signature = "0xa9059cbb"
                        else:
                            called_signature = "0x"+args[0][2:].rjust(64,"0")[:8]        
                    called_name = get_name_by_signature(called_signature)
                    called_args = describe_multi_args(unshift_args(args[1:]))
                    if called_name == called_signature:
                        des = f"it calls an external function whose signature is {called_signature} of contract {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}."
                    else:
                        des = f"it calls an external function {called_name} of {str_evm_variable}."
            if len(ethers) > 0:
                des = des.rstrip(".")
                des += " with " + ethers 
            if len(args) > 1:
                des = des.rstrip(".")
                if len(ethers) > 0:
                    des += " and "
                else:
                    des += " with "
                if len(args[1:]) == 1:
                    if called_args.endswith("argument") or called_args.endswith("arguments"):
                        des += f"{called_args}."
                    else:
                        des += f"{called_args} as the argument."
                else:
                    des += f"the following argument list: {called_args}."
            if behavior.call_returns is not None and len(behavior.call_returns) > 0:
                des = des.rstrip(".")
                des += f", and gets the returned value as {behavior.call_returns}."
            return des
        else:
            ethers = f"{describe_op_tree(behavior.lhs[0], inferred_names, behavior.depend_calls)}" if len(behavior.lhs) > 0 else "" 
            if "msg.value" in ethers:
                return f"it transfers {ethers} to {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}."
            elif ethers == "BALANCE ADDRESS":
                return f"it transfers all the ether of this contract to {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}."
            else:
                return f"it transfers ether valued {ethers} to {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}."

    elif behavior.behavior_type == BehaviorType.DELEGATECALL:
        des = f"it delegates a call to {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}"
        
        args = f"{','.join([describe_op_tree(lhs, inferred_names, behavior.depend_calls) for lhs in behavior.lhs[0:]])}" if len(behavior.lhs) > 0 else ""
        if len(behavior.lhs[0:]) == 1:
            des += " with "
            if args.endswith("argument") or args.endswith("arguments"):
                des += f"{args}."
            else:
                des += f"the {args} argument."
        else:
            des += f" with arguments: {args}."
        return des
    elif behavior.behavior_type == BehaviorType.STATICCALL:
        args = []
        for lhs in behavior.lhs:
            des_arg = describe_op_tree(lhs, inferred_names, behavior.depend_calls)
            args.append(des_arg)

        str_evm_variable = describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)
        
        # support built-in functions
        if str_evm_variable in ['0x1','0x2']:
            if str_evm_variable == '0x1':
                des = f"it calls a built-in function ecrecover."
            else:
                des = f"it calls a built-in function sha256."
            called_args = describe_multi_args(unshift_args(args))
        else:
            if len(args[0]) <= 10: # called signature
                called_signature = args[0]
            else:
                called_signature = "0x"+args[0][2:].rjust(64,"0")[:8]        
            called_name = get_name_by_signature(called_signature)
            called_args = describe_multi_args(unshift_args(args[1:]))
            if called_name == called_signature:
                des = f"it statically calls an external function whose signature is {called_signature} of contract {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}."
            else:
                des = f"it statically calls an external function {called_name} of {str_evm_variable}."
            # args = f"{','.join([describe_op_tree(lhs, inferred_names, behavior.depend_calls) for lhs in behavior.lhs[0:]])}" if len(behavior.lhs) > 0 else ""
            # des = f"it calls statically to {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}"
            args = args[1:]
        if len(args) >= 1:
            des = des.rstrip(".")
            des += " with "
            if len(args[0:]) == 1:
                if called_args.endswith("argument") or called_args.endswith("arguments"):
                    des += f"{called_args}."
                else:
                    des += f"{called_args} as the argument."
            else:
                des += f"the following argument list: {called_args}."
        if behavior.call_returns is not None and len(behavior.call_returns) > 0:
            des = des.rstrip(".")
            des += f", and gets the returned value as {behavior.call_returns}."
        return des
    elif behavior.behavior_type == BehaviorType.SELFDESTRUCT:
        return f"the contract will be destroyed and its balance will be sent to {describe_evm_variable(behavior.rhs, inferred_names, behavior.depend_calls)}."

def describe_evm_state(evm_state:EVMState, inferred_names, call_returns):
    pure_name = evm_state.details(with_keys=False, with_counts=False)
    if pure_name in inferred_names:
        pure_name = inferred_names[pure_name]
    else:
        pure_name = pure_name.replace(":","_").replace("(","_").replace(")","").lower()
    pure_name:str = inferred_names.get(pure_name,pure_name)
    if len(evm_state.keys) == 0 and (evm_state.type.is_elementary or evm_state.type.is_user_define or evm_state.type.is_other_type):
        if evm_state.type.is_elementary and evm_state.type.type_name == "bool":
            return f"{pure_name}"

        if evm_state.type.is_contract:
            pre = "the external contract "
        else:
            pre = ""
        return pre+pure_name
    elif evm_state.type.is_array:
        index = ""
        for key in evm_state.keys:
            index += describe_op_tree(key, inferred_names, call_returns) 
        if len(index) == 0:
            return f"the element in the {pure_name}"     
        return f"the element in the {pure_name} with index {index}"
    else:
        if pure_name[-1].isnumeric():
            suffix = pure_name[-1]
            pure_name = pure_name[:-1]
        else:
            suffix = ''

        if pure_name.lower().endswith("of"):
            pure_name = pure_name.lower()[:-2]

        if len(evm_state.keys) == 0: # unresolved args, e.g.,0xb8c77482e45f1f44de1745f52c74426c631bdd52
            from_des = "the address"
        else:
            from_des = describe_op_tree(evm_state.keys[0], inferred_names, call_returns)
        if len(evm_state.keys) == 1:
            return f"the {pure_name}{suffix} of {from_des}"
        elif len(evm_state.keys) == 2:
            to_des = describe_op_tree(evm_state.keys[1], inferred_names, call_returns)
            return f"the {pure_name}{suffix} from {from_des} to {to_des}"
        else:
            keystr = ""
            for key in evm_state.keys:
                substr = describe_op_tree(key, inferred_names, call_returns)
                keystr += f"[{substr}]"
            return f"{pure_name}{keystr}"

def describe_evm_property(evm_property:EVMProperty, call_returns):
    property_name = PROPERTY_DESCRIPTIONS.get(evm_property.name, evm_property.name)
    if property_name.startswith("0x"):
        if len(property_name) >= 2+36 and len(property_name) <= 2+40:
            return to_checksum_address("0x" + property_name[2:].rjust(40,"0"))
        elif len(property_name) > 2+40:
            if all(s=='f' for s in property_name[2:]):
                return "uint(-1)"
            else:
                return property_name
    if "RETURN" in property_name:
        pc = property_name.split("@")[-1]
        if pc in call_returns:
            return call_returns[pc]
    # if property_name.startswith("0x"): 
    #     print()
    # if property_name.startswith("0x"): return int(property_name, 16)
    return property_name

def describe_evm_arg(evm_arg:EVMArg):
    if evm_arg.index >= 0:
        index = INDEX_MAPPING.get(evm_arg.index+1, f"{evm_arg.index+1}-th")
        if len(evm_arg.keys) > 0:
            return f"the {evm_arg.keys} of the {index} argument"
        else:
            return f"the {index} argument"
    else:
        return "all the arguments"

def describe_evm_variable(evm_variable:EVMVariable, inferred_names, call_returns=None):
    if call_returns is None: call_returns = dict()
    if isinstance(evm_variable, EVMState):
        return describe_evm_state(evm_variable, inferred_names, call_returns)
    elif isinstance(evm_variable, EVMProperty):
        return describe_evm_property(evm_variable, call_returns)
    else:
        return describe_evm_arg(evm_variable)

def describe_constant_by_type(constant:str, state_type):
    if state_type is None:
        # if optree.father is not None and optree.father.name in ["ADD","SUB","MUL","DIV"]:
        #     return str(int(optree.name,16))
        if len(constant) >= 2+36 and len(constant) <= 2+40:
            return to_checksum_address("0x" + constant[2:].rjust(40,"0"))
        elif int(constant, 16) <= 1000000000000000:
            return str(int(constant, 16))
        else:
            pretty_num = pretty_bignum(int(constant,16))
            return str(pretty_num)
    else:
        try:
            if state_type.is_elementary:
                if state_type.type_name == "address":
                    return to_checksum_address("0x" + constant[2:].rjust(40,"0"))
                elif state_type.type_name == "bool":
                    if int(constant,16) == 0:
                        return "false"
                    else:
                        return "true"
                elif state_type.type_name.startswith("int") or state_type.type_name.startswith("uint"):
                    return str(int(constant,16))
                elif state_type.type_name in ["string","bytes"]:
                    pretty_num = pretty_bignum(int(constant,16))
                    return str(pretty_num)
                else:
                    # return hex number
                    return constant
            elif state_type.is_user_define:
                if state_type.type_name == "user_define_contract":
                    return to_checksum_address("0x" + constant[2:].rjust(40,"0"))
                else:
                    return str(int(constant,16))                  
            else:
                return constant
        except:
            return describe_constant_by_type(constant, None)

def describe_op_tree(optree:OpTree, inferred_names, call_returns=None, state_type=None) -> str:
    if call_returns is None: call_returns = dict()
    if optree.alias_evm_variable is not None:
        if optree.name.startswith("0x"):
            return describe_constant_by_type(optree.name, state_type)
        return describe_evm_variable(optree.alias_evm_variable, inferred_names, call_returns)
    elif optree.name == "0":
        return "0"
    else:
        base_ret = OP_DESCRIPTIONS.get(optree.name, optree.name)
        if "RETURN" in optree.name:
            pc = optree.name.split("@")[-1]
            if pc in call_returns:
                return call_returns[pc]
        if "CALLDATACOPY" in optree.name:
            if optree.sons[0].name.startswith("0x"):
                if optree.sons[0].name == "0x0":
                    is_dynamic = True 
                    index = -1
                else:
                    is_dynamic = False
                    index = int(optree.sons[0].name,16)
                
                return describe_evm_arg(EVMArg(index, is_dynamic=is_dynamic))
        if "SHA3" in optree.name:
            return "SHA3(" + ",".join(describe_op_tree(son, inferred_names, call_returns) for son in optree.sons) + ")"

        if optree.name == "CREATE":
            return "the contract just created"
        # if optree.cstates['check_on_caller']:
        #     caller = optree.get_son("CALLER")
        #     if caller is None:
        #         if optree.name == "ISZERO":
        #             if len(optree.sons) == 1 and optree.sons[0].name == "EQ":
        #                 return "when the caller is not " + describe_op_tree(optree.sons[0], inferred_names, call_returns)
        #     elif optree.name == "EQ":
        #         ret = optree.get_son(NAME="CALLER", anti=True)
        #         if ret is None:
        #             return base_ret % (describe_op_tree(optree.sons[0], inferred_names, call_returns), describe_op_tree(optree.sons[1], inferred_names, call_returns))
        #         return f"when the caller is {describe_op_tree(ret, inferred_names, call_returns)}"
    
        if r"%s" in base_ret:
            _tmp = tuple(describe_op_tree(son, inferred_names, call_returns) for son in optree.sons)
            if optree.name == "ISZERO":                
                if ">" in _tmp[0]:
                    _tmp = _tmp[0].replace(">", "<=")
                    return _tmp

                elif "<" in _tmp[0]:
                    _tmp = _tmp[0].replace("<", ">=")
                    return _tmp

                elif "==" in _tmp[0]:
                    _tmp = _tmp[0].replace("==", "!=")
                    return _tmp

                elif "== 0" in _tmp[0]:
                    _tmp = _tmp[0].replace("== 0", "!= 0")
                    return _tmp

            return base_ret % _tmp
        elif len(optree.sons) == 1:
            return base_ret + " " + describe_op_tree(optree.sons[0], inferred_names, call_returns)
        elif len(optree.sons) == 2:
            return describe_op_tree(optree.sons[0], inferred_names, call_returns) + " " + base_ret + " " + describe_op_tree(optree.sons[1], inferred_names, call_returns)
        else:
            return base_ret + " ".join(describe_op_tree(son, inferred_names, call_returns) for son in optree.sons)


def describe_behaviors(behaviors:List[Behavior], inferred_names, describe_dependency:bool=True, deep:int=1):
    description = ""
    ordered_bahaviors:List[OrderedBehavior] = [OrderedBehavior(behavior, inferred_names) for behavior in behaviors]
    with_dependency = False
    has_described = defaultdict(bool)
    if describe_dependency:
        ordered_bahaviors, with_dependency = make_sure_orders(ordered_bahaviors)
    
    for ordered_bahavior in ordered_bahaviors:
        desc = ordered_bahavior.describe_behavior(deep) + "\n"
        if has_described[desc] is False:
            description += desc
            has_described[desc] = True
    
    return description, with_dependency

def merge_user_description(user_descriptions):
    if len(user_descriptions) == 0:
        return "For any caller"
    else:
        return ", and ".join(user_descriptions)

def describe_conditions(conditions:List[Condition], inferred_names, describe_subject_first:bool=True) -> List[str]:
    description = []
    if describe_subject_first:
        user_conditions = []
        other_conditions = []
        for condition in conditions:
            if condition.cstates['check_on_caller']:
                user_conditions.append(condition)
            else:
                other_conditions.append(condition)
        user_descriptions = _describe_conditions(user_conditions, inferred_names)
        description.append(merge_user_description(user_descriptions))
    else:
        other_conditions = conditions
        
    description.extend(_describe_conditions(other_conditions, inferred_names))
    
    if len(description) > 0:
        des_conditions = ", and ".join([optimize_phrase(desc) for desc in description]) + ":"
    else:
        des_conditions = ""
    if des_conditions.lower().startswith("for"):
        return des_conditions.capitalize()
    else:
        if len(des_conditions) > 0:
            if des_conditions.lower().startswith("before") or des_conditions.lower().startswith("after"):
                return des_conditions.capitalize()
            else:
                return "When "+ anti_capitalize(des_conditions)
        else:
            return ""

def get_def_use(ordered_behavior:OrderedBehavior):
    behavior = ordered_behavior.behavior
    defs, uses = set(), set()
    if behavior.behavior_type == BehaviorType.SSTORE:
        defs.add((behavior.rhs.details(with_counts=False),behavior.rhs.counts))
    else:
        uses.add((behavior.rhs.details(with_counts=False),behavior.rhs.counts))
    
    if behavior.call_returns is not None:
        defs.add((behavior.call_returns,1))
    
    if behavior.depend_calls is not None:
        for v in set(behavior.depend_calls.values()):
            uses.add((v,1)) 
    
    for lhs in behavior.lhs:
        for lhs_evm_state in lhs.contained_evm_states:
            uses.add((lhs_evm_state.details(with_counts=False), lhs_evm_state.counts))
    
    return defs, uses


def make_sure_orders(ordered_behaviors:List[OrderedBehavior]) -> List[OrderedBehavior]:
    with_dependency = False
    def_uses = [get_def_use(ordered_behavior) for ordered_behavior in ordered_behaviors]
    for i in range(len(ordered_behaviors)):
        bi_def, bi_use = def_uses[i]
        for j in range(i+1, len(ordered_behaviors)):
            bj_def, bj_use = def_uses[j]
            
            for bi_defi in bi_def:
                for bj_usei in bj_use:
                    if bj_usei[0] == bi_defi[0]:
                        if bj_usei[1] < bi_defi[1]: # j -> i
                            ordered_behaviors[j].following_behaviors.append(ordered_behaviors[i])
                            ordered_behaviors[i].dep_behaviors.append(ordered_behaviors[j])
                            with_dependency = True
                            break
                        elif bj_usei[1] == bi_defi[1]: # i -> j
                            ordered_behaviors[i].following_behaviors.append(ordered_behaviors[j])
                            ordered_behaviors[j].dep_behaviors.append(ordered_behaviors[i])
                            with_dependency = True
                            break

            for bj_defj in bj_def:
                for bi_usei in bi_use:
                    if bi_usei[0] == bj_defj[0]:
                        if bi_usei[1] < bj_defj[1]: # i -> j
                            ordered_behaviors[i].following_behaviors.append(ordered_behaviors[j])
                            ordered_behaviors[j].dep_behaviors.append(ordered_behaviors[i])
                            with_dependency = True
                            break
                        elif bi_usei[1] == bj_defj[1]: # j -> i
                            ordered_behaviors[j].following_behaviors.append(ordered_behaviors[i])
                            ordered_behaviors[i].dep_behaviors.append(ordered_behaviors[j])
                            with_dependency = True
                            break
    ret_behaviors = []
    for behavior in ordered_behaviors:
        if behavior.dep_behaviors is None or len(behavior.dep_behaviors) == 0:
            ret_behaviors.append(behavior)
    
    return ret_behaviors, with_dependency

def _describe_conditions(conditions:List[Condition], inferred_names):
    description = []
    for condition in conditions:
        if condition.cstates['check_on_calls']:
            str_cond = str(condition)
            if "0 ==" in str_cond:
                description.append("the call or transfer fails")
            else:
                description.append("the call or transfer succeeds")
        else:
            description.append(describe_op_tree(expanded_condition_tree(condition.optree), inferred_names, condition.depend_calls))
        
    return description
