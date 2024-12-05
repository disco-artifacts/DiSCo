from typing import *

import disco.common.structures.opcodes as Opcodes
from disco.common.lifting.variables_analyzer import EVMVariableAnalyzer
from disco.common.structures.evm_variable import EVMArg, EVMProperty, EVMState
from disco.common.structures.tac_path import TACPath
from disco.common.structures.tac_tree import tree_from_variable

def valid_forward_chains(forward_chains):
    return not any(forward_chain.opcode.name in ["LT","GT","SLT","SGT","EQ"] for forward_chain in forward_chains)        

def valid_evm_states(evm_states:List[EVMState], language:str="Solidity"):
    if len(evm_states) == 0: return False
    base_index = evm_states[0].index

    for i, evm_state in enumerate(evm_states):
        # * Read only one evm state variable
        if language == "Solidity":
            if evm_state.index != base_index:
                return False
            # * The keys can only contain evm args
            if not all([isinstance(key.alias_evm_variable, EVMArg) for key in evm_state.keys]):
                return False
        else:
            if (evm_state.index != base_index + i) and (evm_state.index != base_index):
                return False
            # * The keys can contain evm args or index (e.g., 0,1)
            if not all([isinstance(key.alias_evm_variable, EVMArg) or isinstance(key.alias_evm_variable, EVMProperty) for key in evm_state.keys]):
                return False
    return True

# indeed: forward analysis
def dfs_chains(tac_op, forward_chain:List, forward_chains:List):
    forward_chain.append(tac_op)
    
    use_sites = tac_op.lhs.use_sites
   
    # if the variable is not used anymore, the use_sites are None   
    if use_sites is None or len(use_sites) < 1:
        forward_chains.append(forward_chain.copy())
    else:
        for site in use_sites:
            use_tac_op = site.get_instruction()
            if hasattr(use_tac_op, 'lhs'):
                dfs_chains(use_tac_op, forward_chain, forward_chains)
            else:
                forward_chains.append(forward_chain.copy())
                
    forward_chain.pop()

def extract_state_variables(evm_analyzer:EVMVariableAnalyzer, tac_path:TACPath, debug:bool=False):
    """Analysis the public state variables according to the non-state-affected paths.

    Arguments:
        tac_path: TACPath, the execution tac_path.
    """
    evm_states = []
    if len(tac_path.tac_blocks) == 0: return None
    if not tac_path.tac_blocks[-1].tac_ops[-1].opcode == Opcodes.RETURN: return None
    for block in tac_path.tac_blocks:
        for tac_op in block.tac_ops:
            if tac_op.opcode == Opcodes.SLOAD:
                forward_chains = []
                _evm_states = []
                dfs_chains(tac_op, [], forward_chains)

                for forward_chain in forward_chains:
                    if not valid_forward_chains(forward_chain): continue
                    last_tac_op = forward_chain[-1]
                    evm_state_visiting_tree = tree_from_variable(last_tac_op.lhs)
                    if debug:
                        print("\n".join([str(tac_op) for tac_op in forward_chain]) + f"\n{'='*20}\n")
                        evm_state_visiting_tree.vis_graph().render(f"ret_visit",format="svg",cleanup=True)
                    
                    evm_state_visiting_tree_str = str(evm_state_visiting_tree)
                    if evm_state_visiting_tree_str in evm_analyzer.has_analyzed_trees:
                        evm_states.append(evm_analyzer.has_analyzed_trees[evm_state_visiting_tree_str])

                    sload_trees = evm_state_visiting_tree.get_all_sons(NAME="SLOAD")
                    for sload_tree in sload_trees:
                        evm_state, forward_tree = evm_analyzer.sload_analysis(sload_tree,copy_state_variable=False)                       
                        
                        evm_analyzer.has_analyzed_trees[str(forward_tree)] = evm_state.copy()

                        _evm_states.append(evm_state)

                    if valid_evm_states(_evm_states, language=evm_analyzer.language):
                        evm_states.extend(_evm_states)
                    else:
                        return None

    if valid_evm_states(evm_states, language=evm_analyzer.language):
        # some contracts implement a getXXX function, we strip the `get` and set the name of the state variable
        function_name = tac_path.function.function_name
        if function_name.lower().startswith("get"):
            function_name = function_name[3:]
        
        evm_states[0].name = None if function_name.startswith("0x") else function_name
        evm_states[0].signature = tac_path.function.function_signature
        evm_states[0].is_public = True
        
        if len(evm_states) > 1 and evm_analyzer.language == "Vyper":
            for evm_state in evm_states:
                evm_state.change_to_string_type()
        
        return evm_states[0]
    
    return None