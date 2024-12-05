from disco.common.structures.evm_variable import EVMArg, EVMProperty, EVMState
from disco.common.structures.tac_tree import OpTree

def serialize_tree(optree:OpTree):
    if optree is None:
        return None

    serialize_sons = [serialize_tree(son) for son in optree.sons]
    
    return {
        "name": optree.name,
        "alias_evm_variable": optree.alias_evm_variable.dump() if optree.alias_evm_variable is not None else None,
        "contained_evm_states": [evm_state.dump() for evm_state in optree.contained_evm_states],
        "sons": serialize_sons
    }

def deserialize_tree(data):
    if data is None:
        return None
    __alias_evm_variable_type = data['alias_evm_variable']
    if __alias_evm_variable_type is None:
        alias_evm_variable = None
    else:
        alias_evm_variable_type = __alias_evm_variable_type['variableType']
        if alias_evm_variable_type == "EVMState":
            alias_evm_variable = EVMState.load(__alias_evm_variable_type)
        elif alias_evm_variable_type == "EVMProperty":
            alias_evm_variable = EVMProperty.load(__alias_evm_variable_type)
        elif alias_evm_variable_type == "EVMArg":
            alias_evm_variable = EVMArg.load(__alias_evm_variable_type)
    
    contained_evm_states = [EVMState.load(evm_state) for evm_state in data['contained_evm_states']]
    
    sons = [deserialize_tree(son) for son in data['sons']]
    tree = OpTree(data['name'], sons)
    tree.alias_evm_variable = alias_evm_variable
    tree.contained_evm_states = contained_evm_states
    return tree