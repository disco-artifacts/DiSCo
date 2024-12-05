import json
import os
import shutil
import sys
import time
from collections import defaultdict
from typing import *

from disco.app.descriptions.describers import (anti_capitalize,
                                                describe_behaviors,
                                                describe_conditions)
from disco.app.descriptions.utils import find_return_pcs
from disco.app.utils import split_semantic_units, callreturn_propagation
from disco.app.graph_construction import load_semantic_units
from disco.common.structures.unit.behavior_element import BehaviorType
from disco.common.structures.unit.semantic_unit import SemanticUnit
from disco.common.structures.unit.behavior_element import Behavior
from disco.common.structures.unit.condition_element import Condition
from disco.common.utils.mongodb_utils import (get_args_list_by_signature,
                                               get_inferred_names)
  
def load_inferred_names(address):
    inferred_names = list(get_inferred_names(address))

    ret_names = {}
    count_names = {inferred_name['data_name']:1 for inferred_name in inferred_names if inferred_name['with_name']==1}
    for inferred_name in inferred_names:
        if inferred_name['with_name'] == 0:
            if inferred_name['pred_name@1'] not in count_names:
                suffix = ""
                count_names[inferred_name['pred_name@1']] = 0
            else:
                count_names[inferred_name['pred_name@1']] += 1
                suffix = str(count_names[inferred_name['pred_name@1']])
            ret_names[inferred_name['data_name']] = inferred_name['pred_name@1'] + suffix
    
    return ret_names

def prunning_semantic_behaviors(_semantic_units:List[SemanticUnit]):
    with_loops = False
    set_conditions = []
    pcs2sus = defaultdict(list)

    for semantic_unit in _semantic_units:
        set_condition = set()
        for condition in semantic_unit.conditions:
            if not (condition.cstates['check_on_calls'] | condition.cstates['check_on_creates'] | condition.cstates['check_on_selfdestruct'] | condition.cstates['check_on_extcodesize']) and not condition in set_condition:
                set_condition.add(condition) # deduplication conditions

        set_conditions.append(set_condition)
        ps = sum(hash(p) for p in semantic_unit.behavior.behavior_pcs)
        pcs2sus[ps].append((len(set_conditions), semantic_unit))
    
    semantic_units = []
    for pc, sus in pcs2sus.items():
        ssus = sorted(sus, key=lambda x: x[0])
        semantic_units.append(ssus[0][1])
        
        with_loops |= len(sus) > 1
    return semantic_units, with_loops

def function2payable(f2semanticunits:Dict[str, List[SemanticUnit]]):
    f2payable = dict()
    for f, sus in f2semanticunits.items():
        payable = True
        if all(len(su.conditions) > 0 and su.conditions[0].cstates['check_on_callvalue'] and str(su.conditions[0]) in ['(0 == CALLVALUE)', '(CALLVALUE == 0)'] for su in sus):
            payable = False
        if not payable:
            for su in sus:
                su.conditions = su.conditions[1:]
        f2payable[f] = payable
    return f2payable

def group_by_functions(semantic_units:List[SemanticUnit]):
    f2semanticunits = defaultdict(list)
    
    for semantic_unit in semantic_units:
        for f in semantic_unit.belong_functions:
            f2semanticunits[f].append(semantic_unit)
    return f2semanticunits, function2payable(f2semanticunits)

def prepare_function_header(function_name:str, payable:bool, with_args:bool=True):
    function_signature, function_name = function_name.split("_",1)
    header = ""

    if payable:
        header += f"For the payable {function_name} function"
    else:
        header += f"For the {function_name} function"
    args = get_args_list_by_signature(function_signature) if with_args and len(function_signature) > 0 else []
    if len(args) > 0:
        if len(args) == 1:
            header += f", it has one argument and its type is {args[0]}"
        else:
            header += f", it has {len(args)} arguments and the type of each argument is as follows: {', '.join(args)}"
    header += ".\n"
    
    return header
        

class SuGroups:
    def __init__(self, base_su:Tuple[List[Condition], Behavior]) -> None:
        self.sus = [base_su]
        
        self.common_conds = set(base_su[0])
    
    def has_same_conds(self, su:Tuple[List[Condition], Behavior]):
        return len(self.common_conds & set(su[0])) > 0 or (len(self.common_conds) == 0 and len(set(su[0])) == 0)
    
    def add_su(self, su:Tuple[List[Condition], Behavior]):
        self.sus.append(su)
        
        self.common_conds &= set(su[0])
    
    def remove_conds(self):
        sus = []
        for su in self.sus:
            sus.append((list(set(su[0])-self.common_conds), su[1]))
        self.sus = sus
        return sus

    def stopped(self):
        return all(len(su[0])==0 for su in self.sus)

class Describer:
    def __init__(self, semantic_units:List[SemanticUnit], inferred_names, describe_subject_first:bool=True, describe_dependency:bool=True) -> None:
        self.semantic_units = semantic_units
        self.inferred_names = inferred_names
        
        self.describe_subject_first = describe_subject_first
        self.describe_dependency = describe_dependency
        
        _, self.call_returns = callreturn_propagation(self.semantic_units)
    
        self.condition_mapping, self.behavior_mapping, self.list_semantic_units = split_semantic_units(semantic_units)
        
        for c in self.condition_mapping.values():
            c.depend_calls = self.call_returns
        
        self.with_dependency = False

    def group_by_conditions(self, sus) -> List[SuGroups]:
        if len(sus) == 0: return []
        groups = [SuGroups(sus[0])]
        for i in range(1, len(sus)):
            hasInter = False
            for group in groups:
                if group.has_same_conds(sus[i]):
                    group.add_su(sus[i])
                    hasInter = True
                    break
            if not hasInter:
                groups.append(SuGroups(sus[i]))
        
        return groups

    def describe(self, sus, level):
        description = ""
        grouped_sus = self.group_by_conditions(sus)
        for group in sorted(grouped_sus, key=lambda x:len(x.common_conds), reverse=False):
            if len(group.common_conds) > 0:
                description += " "*2*level + "- " + describe_conditions([self.condition_mapping[c] for c in group.common_conds], self.inferred_names, self.describe_subject_first) + "\n"
            new_sus = group.remove_conds()
            if not group.stopped():
                description += self.describe(new_sus, level+1)    
            else:
                deep = level
                if len(group.common_conds) > 0:
                    deep += 1                    
                behavior_descriptions, _with_dependency = describe_behaviors([self.behavior_mapping[su[1]] for su in group.sus], self.inferred_names, describe_dependency=self.describe_dependency, deep=deep)
                description += behavior_descriptions
                self.with_dependency |= _with_dependency
        return description
    
def describe_semantic_units(semantic_units:List[SemanticUnit], inferred_names, describe_subject_first:bool=True, describe_dependency:bool=True) -> str:
    
    describer = Describer(semantic_units, inferred_names, describe_subject_first, describe_dependency)
    
    return describer.describe(describer.list_semantic_units, 0), describer.with_dependency

def semantic_units_to_description(semantic_units, inferred_names, describe_subject_first:bool=True, describe_dependency:bool=True, split_function:bool=True):
    descriptions = ""
    with_dependency = False

    if split_function:
        f2sus, f2payable = group_by_functions(semantic_units)
    
        for f, fsus in f2sus.items():
            function_header = prepare_function_header(f, f2payable.get(f, False))
    
            descriptions += function_header
            
            _descriptions, _with_dependency = describe_semantic_units(fsus, inferred_names=inferred_names, describe_subject_first=describe_subject_first, describe_dependency=describe_dependency)
            descriptions +=  _descriptions + "\n"
            with_dependency |= _with_dependency
            
    else:
        _descriptions, _with_dependency = describe_semantic_units(semantic_units, inferred_names=inferred_names, describe_subject_first=describe_subject_first, describe_dependency=describe_dependency)
        descriptions +=  _descriptions
        with_dependency |= _with_dependency

    return descriptions, with_dependency

def with_optimiztions(log_files):
    for log_file in log_files:
        if os.path.exists(log_file):
            with open(log_file,"r") as f:
                for line in f:
                    if "with_optimized" in line:
                        return True
    return False

def generate_descriptions(address, working_dir, version:str="v1", result_types:List[str]=["constructor_result", "static_result"], format:str="txt", describe_subject_first:bool=False, describe_dependency:bool=True, use_inferred_names:bool=True, description_version:str="v1", split_function:bool=True, force_rerun:bool=True):
    address = address.lower()
    description_start = time.time()
    
    out_dir = f"{working_dir}/{address}/out_{version}"
    description_dir = f"{out_dir}/description_{description_version}"
    if force_rerun and os.path.exists(description_dir):
        shutil.rmtree(description_dir)
    os.makedirs(description_dir, exist_ok=True)
    
    suffix = f"{int(use_inferred_names)}{int(split_function)}"
    
    description_file = f"{description_dir}/description_{suffix}.{format}"
    
    with_dependency = False
    if use_inferred_names:
        inferred_names = load_inferred_names(address)
        # Vyper S(16777215)
        inferred_names["S(16777215)"] = "locked"
    else:
        inferred_names = dict()
    semantic_units = load_semantic_units([f"{out_dir}/{result_type}/semantic_units.json" for result_type in result_types])
    
    descriptions, with_dependency = semantic_units_to_description(semantic_units, inferred_names, describe_subject_first, describe_dependency, split_function)
    
    print(descriptions)
    
    with open(description_file,"w") as f:
        f.write(f"{descriptions}\n")

    with_optimiztion = with_optimiztions([f"{out_dir}/{result_type}/analysis.log" for result_type in result_types])
    
    description_end = time.time()

    with open(f"{description_dir}/description_meta.json","w") as f:
        json.dump({
            "status":1,
            "with_optimiztion":int(with_optimiztion),
            "with_dependency":int(with_dependency),
            "description_time":description_end - description_start,
            "description":descriptions,
            "with_inferred_names":int(len(inferred_names) > 1)
        }, f, indent='\t')

if __name__ == "__main__":
    generate_descriptions(address="0xc6e5e9c6f4f3d1667df6086e91637cc7c64a13eb", working_dir='./')