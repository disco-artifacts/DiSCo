import os
import shutil
from typing import *

import json
from graphviz import Digraph

from disco.common.structures.evm_variable import EVMArg, EVMProperty, EVMState, EVMVariable
from disco.common.structures.tac_tree import OpTree, expanded_condition_tree
from disco.common.structures.unit.behavior_element import Behavior
from disco.common.structures.unit.condition_element import Condition
from disco.common.structures.unit.semantic_unit import SemanticUnit
from disco.app.utils import split_semantic_units, callreturn_propagation
from disco.app.graph import Edge, Graph, Node, NodeType, NODE_TYPE_COLOR

SYMBOL_MAPPING_COMPARISON_REV = {
    "GT":"<=",
    "LT":">=",
    "EQ":"!=",
}

SYMBOL_MAPPING_COMPARISON = {
    "GT":">",
    "LT":"<",
    "EQ":"=="
}

SYMBOL_MAPPING_ARITH = {
    "ADD":"+",
    "SUB":"-",
    "MUL":"*",
    "DIV":"/",
    "MOD":"%",
    "AND":"&",
    "OR":"|",
    "XOR":"!=",
    "EXP":"**",
    "SIGNEXTEND":"SIGNEXTEND"
}
EVM_Variable2Node:Dict[str, int] = dict()
class OutOfRulesException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

def load_semantic_units(semantic_unit_paths) -> List[SemanticUnit]:
    semantic_units:List[SemanticUnit] = []
    for semantic_unit_path in semantic_unit_paths:
        if os.path.exists(semantic_unit_path):
            with open(f"{semantic_unit_path}","r") as f:
                for line in f:
                    try:
                        su_data = json.loads(line)
                    except Exception as e:
                        # raise e
                        continue
                    semantic_unit = SemanticUnit.load(su_data)
                    semantic_units.append(semantic_unit)

    return semantic_units

def load_data_types(data_type_paths) -> Dict:
    evm_state2_data_type = dict()
    for data_type_path in data_type_paths:
        if os.path.exists(data_type_path):
            with open(data_type_path, "r") as f:
                _evm_state2_data_type = json.load(f)
                for v in _evm_state2_data_type:
                    evm_variable = EVMState.load(v)
                    evm_state2_data_type[evm_variable.details(with_keys=False, with_counts=False)] = str(evm_variable.type)
    return evm_state2_data_type

def load_unseen_names(psv_name_paths) -> Dict:
    unseen_names = dict()
    for psv_path in psv_name_paths:
        if os.path.exists(psv_path):
            with open(psv_path, "r") as f:
                _psv_names = json.load(f)
                unseen_names.update(_psv_names)
    return unseen_names

def depict_evm_variable(evm_variable:EVMVariable, call_returns=None) -> Tuple[Node, List[Edge]]:
    rootName = evm_variable.details(with_keys=False, with_counts=False)
    edges = []
    str_evm_variable = str(evm_variable)
    global EVM_Variable2Node
    if str_evm_variable in EVM_Variable2Node:
        return EVM_Variable2Node[str_evm_variable], []
    else:
        if isinstance(evm_variable, EVMState):
            rootNode = Node(rootName, NodeType.OBJ_EVM_STATE)
            preNode = rootNode
            if len(evm_variable.keys) > 0:
                for key in evm_variable.keys:
                    keyNode, key_edges = depict_optree(key)
                    _keyNode = Node("key", NodeType.OP_KEY)
                    
                    rootNode = _keyNode
                    edges.extend(key_edges)
                    edges.append(Edge(keyNode, _keyNode))
                    edges.append(Edge(_keyNode, preNode))
                    preNode = keyNode
            
            EVM_Variable2Node[str_evm_variable] = rootNode
            return rootNode, edges

        elif isinstance(evm_variable, EVMProperty):
            if rootName.startswith("0x") or rootName == "0":
                if rootName == "0": rootName = hex(int(rootName))
                rootNode = Node(rootName, NodeType.OBJ_CONST)
                # return , edges
            elif "RETURN" in rootName:
                pc = rootName.split("@")[-1]
                if pc in call_returns:
                    rootNode = Node(call_returns[pc], NodeType.OBJ_EVM_PROPERTY)
                    # return , edges
                else:
                    rootNode = Node(rootName, NodeType.OBJ_EVM_PROPERTY)
            # EVM_Variable2Node[str_evm_variable] = rootNode
            else:
                rootNode = Node(rootName, NodeType.OBJ_EVM_PROPERTY)
                # return Node(rootName, NodeType.OBJ_EVM_PROPERTY), edges
        else:
            rootNode = Node(rootName, NodeType.OBJ_EVM_ARG)
            # return Node(rootName, NodeType.OBJ_EVM_ARG), edges

        EVM_Variable2Node[str_evm_variable] = rootNode
        return rootNode, edges

def depict_optree(optree:OpTree, call_returns=None) -> Tuple[Node, List[Edge]]:
    if call_returns is None: call_returns = dict()
    """return the root node and edges"""
    if optree.alias_evm_variable is not None:
        return depict_evm_variable(optree.alias_evm_variable, call_returns)
    elif optree.name.startswith("0x") or optree.name == "0":
        if optree.name == "0": optree.name = hex(int(optree.name))
        edges = []
        return Node(optree.name, NodeType.OBJ_CONST), edges        
    else:
        edges = []
        if "RETURN" in optree.name and "CALL" in optree.name:
            pc = optree.name.split("@")[-1]
            if pc in call_returns:
                return Node(call_returns[pc], NodeType.OBJ_EVM_PROPERTY), []
            else:
                # skip this node
                return Node(str("UNK"), NodeType.OP_UNK), []
        elif "CALLDATACOPY" in optree.name:
            if optree.sons[0].name.startswith("0x"):
                if optree.sons[0].name == "0x0":
                    is_dynamic = True 
                    index = -1
                else:
                    is_dynamic = False
                    index = int(optree.sons[0].name,16)
                
                return depict_evm_variable(EVMArg(index, is_dynamic=is_dynamic), call_returns)
            else:
                # UNK
                return depict_evm_variable(EVMArg(-1, is_dynamic=True), call_returns)

        elif len(optree.sons) == 1:
            if optree.name == "ISZERO":
                son = optree.sons[0]
                if son.name == "ISZERO":
                    rootNode = Node("!=", NodeType.OP_COMPARISON)
                    lNode, _edges = depict_optree(son.sons[0], call_returns)
                    rNode = Node(str("0x0"), NodeType.OBJ_CONST)
                    edges.extend(_edges)
                    edges.append(Edge(lNode, rootNode))
                    edges.append(Edge(rootNode, rNode))
                    return rootNode, edges

                elif son.name in SYMBOL_MAPPING_COMPARISON_REV:
                    rootNode = Node(SYMBOL_MAPPING_COMPARISON_REV[son.name], NodeType.OP_COMPARISON)
                    lNode, ledges = depict_optree(son.sons[0], call_returns)
                    rNode, redges = depict_optree(son.sons[1], call_returns)

                    edges.extend(ledges)
                    edges.extend(redges)
                    
                    edges.append(Edge(lNode, rootNode))
                    edges.append(Edge(rootNode, rNode))
                    return rootNode, edges

                else:
                    rootNode = Node("==", NodeType.OP_COMPARISON)
                    lNode, _edges = depict_optree(son, call_returns)
                    rNode = Node(str(0), NodeType.OBJ_CONST)
                    edges.extend(_edges)
                    edges.append(Edge(lNode, rootNode))
                    edges.append(Edge(rootNode, rNode))
                    return rootNode, edges
            else:
                rootNode = Node(optree.name, NodeType.OP_COMPARISON)
                lNode, _edges = depict_optree(optree.sons[0], call_returns)
                edges.extend(_edges)
                
                edges.append(Edge(lNode, rootNode))
                return rootNode, edges
                
        elif len(optree.sons) == 2:
            if optree.name in SYMBOL_MAPPING_COMPARISON or optree.name in SYMBOL_MAPPING_ARITH:
                if optree.name in SYMBOL_MAPPING_COMPARISON:
                    rootName = SYMBOL_MAPPING_COMPARISON[optree.name]
                    node_type = NodeType.OP_COMPARISON
                else:
                    rootName = SYMBOL_MAPPING_ARITH[optree.name]
                    node_type = NodeType.OP_ARITHMETIC
                    
                rootNode = Node(rootName, node_type)
                
                lNode, ledges = depict_optree(optree.sons[0], call_returns)
                rNode, redges = depict_optree(optree.sons[1], call_returns)

                edges.extend(ledges)
                edges.extend(redges)
                
                edges.append(Edge(lNode, rootNode))
                edges.append(Edge(rootNode, rNode))
                return rootNode, edges
                
            else:
                return Node(str(optree), NodeType.OP_UNK), []
                # raise OutOfRulesException()
        else:
            return Node(str(optree), NodeType.OP_UNK), []
            # raise OutOfRulesException()

def depict_condition(condition:Condition) -> List[Edge]:
    condition_node, edges = depict_optree(expanded_condition_tree(condition.optree), call_returns=condition.depend_calls)
    
    return condition_node, edges

def depict_behavior(behavior:Behavior) -> List[Edge]:
    edges = []
    behavior_node = Node(behavior.behavior_type.name, NodeType.OP_BEHAVIOR)
    if behavior_node.name == "SELFDESTRUCT":
        behavior.lhs = []
    for lhs in behavior.lhs:
        lNode, ledges = depict_optree(lhs, call_returns=behavior.depend_calls)

        edges.append(Edge(lNode, behavior_node))
        edges.extend(ledges)
    
    rNode, redges = depict_evm_variable(behavior.rhs, call_returns=behavior.depend_calls)
    edges.extend(redges)
    # edges.append(Edge(behavior_node, rNode))    
    edges.append(Edge(rNode, behavior_node))
    
    if behavior.call_returns is not None:
        retNode = Node(behavior.call_returns, NodeType.OBJ_EVM_PROPERTY)
        edges.append(Edge(behavior_node, retNode))    
    
    return behavior_node, edges

def depict_conditions(conditions:Dict[int,Condition]):
    condition_nodes = {}
    edges = []
    # for i in range(len(conditions)):
    for c, condition in conditions.items():
        # ignore some conditions
        if condition.cstates['check_on_calls']:
            continue
        
        condition_node, edges_from_condition = depict_condition(condition)
        edges.extend(edges_from_condition)
        # condition_nodes.append(condition_node)
        condition_nodes[c] = condition_node

    return condition_nodes, edges

def depict_behaviors(behaviors:Dict[int,Behavior]) -> Tuple[List[Node],List[Edge]]:
    behavior_nodes = {}
    edges = []
    # for i in range(len(behaviors)):
    #     behavior = behaviors[i]
    for b, behavior in behaviors.items():
        behavior_node, edges_from_behavior = depict_behavior(behavior)
        edges.extend(edges_from_behavior)
        # behavior_nodes.append(behavior_node)
        behavior_nodes[b] = behavior_node

    return behavior_nodes, edges

def add_connection(conditions_nodes, behavior_nodes, semantic_units_mapping) -> List[Edge]:
    edges = []
    cause_nodes:Dict[int, Node] = {}
    for semantic_unit_mapping in semantic_units_mapping:
        if len(semantic_unit_mapping[0]) > 0:
            merged_hash = sum(hash(idx) for idx in semantic_unit_mapping[0])
            if not merged_hash in cause_nodes:
                cause_nodes[merged_hash] = Node("cause", NodeType.OP_LOGIC)

                for ci in semantic_unit_mapping[0]:
                    edges.append(Edge(conditions_nodes[ci], cause_nodes[merged_hash]))
            cause_node = cause_nodes[merged_hash]
            
            edges.append(Edge(cause_node, behavior_nodes[semantic_unit_mapping[1]]))
        
    return edges

def semantic_units_to_graph(semantic_units:List[SemanticUnit]) -> Graph:
    edges = []
    _, call_returns = callreturn_propagation(semantic_units)
    _conditions, behaviors, semantic_units_mapping = split_semantic_units(semantic_units)
    conditions = {}
    for su in semantic_units_mapping:
        for c in su[0]:
            if not c in conditions:
                conditions[c] = _conditions[c]
    for c in conditions.values():
        c.depend_calls = call_returns
     
    conditions_nodes, edges_from_conditions = depict_conditions(conditions)
    behavior_nodes, edges_from_behaviors = depict_behaviors(behaviors)
    edges.extend(edges_from_conditions)
    edges.extend(edges_from_behaviors)
    connection_edges = add_connection(conditions_nodes, behavior_nodes, semantic_units_mapping)
    edges.extend(connection_edges)
    graph = Graph.build_from_edges(edges)
    
    return graph

def construct_graph(address, working_dir, result_types:List[str]=["static_result","constructor_result"], visualization:bool=False, force_recon:bool=True):
    address = address.lower()
    
    out_dir = f"{working_dir}/{address}"
    graph_dir = f"{out_dir}/graph"
    if force_recon and os.path.exists(graph_dir): shutil.rmtree(graph_dir)
    os.makedirs(graph_dir, exist_ok=True)
    graph_file = f"{graph_dir}/graph.json"
    
    if not force_recon and os.path.exists(graph_file):
        with open(graph_file,"r") as f:
            dumped_graph = json.load(f)
        graph = Graph.load(dumped_graph)
    else:
        unseen_names = load_unseen_names([f"{out_dir}/fused_result/unseen_names.json"])
        evm_state2_data_type = load_data_types([f"{out_dir}/{result_type}/evm_states.json" for result_type in reversed(result_types)])        
        semantic_units = load_semantic_units([f"{out_dir}/{result_type}/semantic_units.json" for result_type in result_types])
        graph = semantic_units_to_graph(semantic_units)

        # post process, add psv names
        for node in graph.nodes:
            if node.node_type == NodeType.OBJ_EVM_STATE:
                if len(node.unseen_name) == 0 and node.name in unseen_names:
                    node.unseen_name = unseen_names[node.name]
                if node.name in evm_state2_data_type:
                    node.data_type = evm_state2_data_type[node.name]
                else:
                    node.data_type = "UNK"
        
        with open(graph_file,"w") as f:
            json.dump(graph.dump(), f)
    
    if visualization:
        vis_graph(graph, f"{graph_dir}").render(cleanup=True)

def analysis_graph_stat(graph:Graph):
    stat = {
        "#node":len(graph.nodes),
        "#edge":len(graph.edges),
    }
    
    types_distribution = {node_type.name:0 for node_type in NodeType}
    evm_w_names, evm_wo_names = 0,0
    for node in graph.nodes:
        types_distribution[node.node_type.name] += 1
        if node.node_type == NodeType.OBJ_EVM_STATE:
            if "(" in node.name:
                evm_wo_names += 1
            else:
                evm_w_names += 1
    stat['types_distribution'] = types_distribution
    stat['evm_stat'] = {"w_name":evm_w_names,"wo_name":evm_wo_names}
    
    return stat   

def vis_graph(graph:Graph, output_path: str, format='svg', filename="graph") -> Digraph:
    G = Digraph(name=filename, filename=filename, directory=output_path, format=format)
    for node in graph.nodes:
        if node.node_type == NodeType.OP_LOGIC:
            G.node(str(graph.node2idx[id(node)]), shape='diamond', label=node.name, style='filled', fillcolor="salmon")
        elif node.node_type in [NodeType.OBJ_CONST, NodeType.OBJ_EVM_ARG, NodeType.OBJ_EVM_PROPERTY, NodeType.OBJ_EVM_STATE]:
            G.node(str(graph.node2idx[id(node)]), shape='parallelogram', label=node.name)
        else:
            G.node(str(graph.node2idx[id(node)]), shape='box', label=node.name, style='filled', fillcolor=NODE_TYPE_COLOR[node.node_type])

    for edge in graph.edges:
        G.edge(str(edge.lidx), str(edge.ridx))

    return G

if __name__ == "__main__":
    construct_graph(address="0xe400289d3432abb8a7e0151091a816729e2d57ac", working_dir='./')