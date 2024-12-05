"""gas:https://ethereum.stackexchange.com/questions/70208/gas-is-0-when-executing-call-opcode"""
import json
import os
import re
import string
from inspect import istraceback
from typing import *

import disco.common.structures.base.memtypes as MemT
import disco.common.structures.opcodes as opcodes
from disco.common.utils.lifting_utils import SHA3_MAPPING_PATH

SYMBOL_MAPPING = {
    "ISZERO":"(0 == {})",
    # binary operator
    "GT":"({} > {})",
    "LT":"({} < {})",
    "SGT":"({} > {})",
    "SLT":"({} < {})",
    "EQ":"({} == {})",
    "ADD":"({} + {})",
    "SUB":"({} - {})",
    "MUL":"({} * {})",
    "DIV":"({} / {})",
    "MOD":"({} % {})",
    "AND":"({} & {})",
    "OR":"({} | {})",
    "EXP":"({} ** {})",
    "SIGNEXTEND":"(SIGNEXTEND({1},{0}))"
}

SYMBOL_MAPPING_REV = {
    "ISZERO":"(0 != {})",
    "GT":"({} <= {})",
    "LT":"({} >= {})",
    "EQ":"({} != {})",
    "SGT":"({} <= {})",
    "SLT":"({} >= {})",
}

SYMBOL_MAPPING_ARITH = {
    "GT":">",
    "LT":"<",
    "EQ":"==",
    "SGT":">",
    "SLT":"<",
    "ADD":"+",
    "SUB":"-",
    "MUL":"*",
    "DIV":"/",
    "MOD":"%",
    "AND":"&",
    "OR":"|",
    "EXP":"**",
}

CHECK_ON_SLOAD = ["SLOAD"]
CHECK_ON_CALLER = ["CALLER"]
CHECK_ON_CALLVALUE = ["CALLVALUE"]
CHECK_ON_EXTCODESIZE = ["EXTCODESIZE"]
CHECK_ON_CALLDATASIZE = ["CALLDATASIZE"]

# SAI
CHECK_ON_CALLS = ["CALL", "CALLCODE","STATICCALL","DELEGATECALL"]
CHECK_ON_CREATES = ["CREATE", "CREATE2"]
CHECK_ON_SELFDESTRUCT = ["SELFDESTRUCT"]

CHECK_ON_CALLRETURNS = [f"{CALL}RETURN" for CALL in CHECK_ON_CALLS]

# BACKGROUND_OPCODE = ('TIMESTAMP','BLOCK','CALLVALUE')

if os.path.exists(SHA3_MAPPING_PATH):
    with open(SHA3_MAPPING_PATH,"r") as f:
        OPTIMIZED_CONSTANT = json.load(f)
else:
    OPTIMIZED_CONSTANT = dict()

class OpTree:
    def __init__(self, name:str, sons=None, reference_blocks=None, is_zero:bool=False, with_optimized:bool=False) -> None:
        # some constant are optimized (e.g., SHA3)
        self.with_optimized = with_optimized
        if name in OPTIMIZED_CONSTANT:
            self.with_optimized = True
            self.name = "SHA3"
            sons = [OpTree(hex(OPTIMIZED_CONSTANT[name]['key'])), OpTree(hex(OPTIMIZED_CONSTANT[name]['index']))]
        else:
            self.name = name
            """Name of the root"""
        
        if sons is None:
            sons = []
        elif isinstance(sons, OpTree):
            sons = [sons]
        self.sons = sons
        """Sons of the root"""

        self.father:OpTree = None
        """Father of the root"""
        self.son_idx:int = -1
        
        self.cstates = {
            'check_on_sload':True if name in CHECK_ON_SLOAD else False,
            'check_on_caller':True if name in CHECK_ON_CALLER else False,
            'check_on_callvalue':True if name in CHECK_ON_CALLVALUE else False,
            'check_on_extcodesize':True if name in CHECK_ON_EXTCODESIZE else False,
            'check_on_calldatasize':True if name in CHECK_ON_CALLDATASIZE else False,

            'check_on_calls':True if name in CHECK_ON_CALLS else False,
            'check_on_creates':True if name in CHECK_ON_CREATES else False,
            'check_on_selfdestruct':True if name in CHECK_ON_SELFDESTRUCT else False,
            
            'check_on_callreturn':True if any(c in name for c in CHECK_ON_CALLRETURNS) else False,
        }
        
        for son_idx, son in enumerate(sons):
            son.father = self
            son.son_idx = son_idx
            self.with_optimized |= son.with_optimized
            
            self.cstates['check_on_sload'] |= son.cstates['check_on_sload']
            self.cstates['check_on_caller'] |= son.cstates['check_on_caller']
            self.cstates['check_on_callvalue'] |= son.cstates['check_on_callvalue']
            self.cstates['check_on_extcodesize'] |= son.cstates['check_on_extcodesize']
            self.cstates['check_on_calldatasize'] |= son.cstates['check_on_calldatasize']
            
            self.cstates['check_on_calls'] |= son.cstates['check_on_calls']
            self.cstates['check_on_creates'] |= son.cstates['check_on_creates']
            self.cstates['check_on_selfdestruct'] |= son.cstates['check_on_selfdestruct']
            
            self.cstates['check_on_callreturn'] |= son.cstates['check_on_callreturn']
            
        self.contained_evm_states = []
        """The related EVM States of this tree"""
        self.contained_evm_args = []
        """The related EVM Args of the tree"""
        self.contained_evm_properties = []
        """The related EVM Properties of the tree"""
        
        self.alias_evm_variable = None
        """The Alias meaning of the tree. e.g. EVMState, EVMArg"""

        # self._smt = None
        # """SMT for solver"""
        self.is_zero = is_zero
        self.loc = -1 # used for computing counts
        
        self._smt = None
        """SMT for solver"""

        self.reference_blocks = reference_blocks if reference_blocks is not None else set()
        for son in sons:
            self.reference_blocks |= son.reference_blocks  
            
    def from_tree(self, tree):
        """Tree edit, keep the object id"""
        tree.father = self.father
        for k,v in vars(tree).items():
            setattr(self, k, v)

    def get_background(self)->List[Optional[str]]:
        """
            return nodes related to "background", e.g. callvalue, timestamp
        """
        queue:List[OpTree] = [self]
        ret = []
        while len(queue):
            head = queue.pop(0)
            if not head.name.startswith('0x'): 
                _op = opcodes.opcode_by_name(head.name)
                if _op.pop == 0 and _op.push == 1:
                    ret.append(head.name)
            for s in head.sons:
                queue.append(s)
        return ret 

    def _pop(self, pop_count:int=0):
        root = self
        for i in range(pop_count):
            root = root.sons[0]
        return root

    def _is_numeric(self):
        if not self.name.startswith("0x"):
            return False, -1
        else:
            return True, int(self.name, base=16)

    # why default is False?
    # change to True
    def details(self, with_counts:bool=True, with_keys:bool=True):
        if self.alias_evm_variable is not None:
            return self.alias_evm_variable.details(with_counts, with_keys)
        else:
            if self.name.startswith("0x"):
                return self.name

            elif self.name == "ISZERO":
                son = self.sons[0]
                if son.name in SYMBOL_MAPPING_REV:
                    format_ = SYMBOL_MAPPING_REV.get(son.name)
                    return format_.format(*tuple(str(s) for s in son.sons))
                else:
                    format_ = SYMBOL_MAPPING.get(self.name, None)
                    return format_.format(str(son))
            else:
                format_ = SYMBOL_MAPPING.get(self.name, None)
                if format_:
                    return format_.format(str(self.sons[0]),str(self.sons[1]))
                elif len(self.sons) > 0:
                    return "{}({})".format(self.name, ",".join(str(son) for son in self.sons))
                else:
                    return self.name
    
    def __str__(self) -> str:
        return self.details()
            
    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, __o: object) -> bool:
        return type(__o) == type(self) and hash(__o) == hash(self)

    def __lt__(self, __o: object) -> bool:
        if type(self) == type(__o):
            if self.name.startswith("0x") and __o.name.startswith("0x"):
                self_value = int(self.name, 16)
                o_value = int(__o.name, 16)
                return self_value < o_value
            elif self.name.startswith("0x") and not __o.name.startswith("0x"):
                return True
        return False

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )

    @classmethod
    def from_const(cls, const_value:str):
        return cls(const_value)

    def get_son(self, NAME:str=None, NUM:bool=False, anti:bool=False):
        """Get the specific son by son's name.
        Args:
            `anti`: if anti, get the other.
            `NUM`: if NUM, get the num son.
        """
        for son in self.sons:
            if not anti:
                if NAME and son.name == NAME:
                    return son
                if NUM and son.name.startswith("0x"):
                    return son
            else:
                if NUM and not son.name.startswith("0x"):
                    return son
                if NAME and son.name != NAME:
                    return son

        # cannot find the specific son
        return None

    def get_all_sons(self, NAME:str=None, stop_on_alias=False):
        rets = []
        queue = [self]
        while len(queue) > 0:
            root = queue.pop()
            if root.name == NAME:
                rets.append(root)
            if stop_on_alias and root.alias_evm_variable is not None:
                continue
            for son in root.sons:
                queue.append(son)
        return rets

    def vis_graph(self, prefix:str="", return_root:bool=False):
        from graphviz import Digraph
        """The prefix is the graph prefix, used to identify graph"""
        G = Digraph(node_attr={"class":"node"},edge_attr=None, graph_attr={"rankdir":"lr","bgcolor":"lemonchiffon","label":str(self)})
        # to draw in order
        same_level_edges = []

        spec = prefix + "_" + "0"

        current = self
        root = "%s_%s"%(spec, current.name)

        G.node(name="%s_%s"%(spec, current.name), label=current.name)                

        # spec, node
        # spec is used to distinguish different nodes
        queue = [(spec, current)]
        while len(queue) > 0:
            spec_fa, current = queue.pop()
            for son_idx, son in enumerate(current.sons):
                spec_son = spec_fa + str(son_idx)
                if son_idx == 0:
                    pre_son = "%s_%s"%(spec_son, son.name)
                else:
                    cur_son = "%s_%s"%(spec_son, son.name)
                    same_level_edges.append((pre_son, cur_son))
                    pre_son = cur_son
                G.node(name="%s_%s"%(spec_son, son.name), label=son.name)
                G.edge("%s_%s"%(spec_fa , current.name),"%s_%s"%(spec_son, son.name))           
                queue.append((spec_son, son))
        
            with G.subgraph(name="same_level%s"%spec_fa) as sg:
                sg.attr(rank="same")
                sg.attr(rankdir="LR")
                sg.edges(same_level_edges)
                sg.edge_attr["style"]="invis"

            same_level_edges = []

        if return_root:
            return G, root
        else:
            return G

def tree_from_variable(variable:MemT.Variable, need_opposite:bool=False) -> OpTree:
    """Return an operation tree from the variable according its usage information.
    
    Arguments:
        variable: MemT.Variable, tac variable, it can be a const.
        need_opposite: bool, true iff opposite and add a ISZERO node.

    Returns:
        optree: OpTree, tree structure of the variable usage.
    """
    # variable folding
    while isinstance(variable, MemT.Variable) and isinstance(variable.value, MemT.Variable) and variable.value is not None:
        variable = variable.value

    if isinstance(variable, MemT.Variable) and variable.is_const:
        variable = variable.const_value

    if isinstance(variable,int):
        if not need_opposite:
            optree = OpTree(hex(variable))
            if variable == 0:
                optree.is_zero = True
            return optree
        else:
            optree = OpTree("ISZERO",OpTree(hex(variable)))
            if variable != 0:
                optree.is_zero = True
            return optree

    if not isinstance(variable, MemT.Variable):
        # DynamicVariable
        if variable.is_const:
            optree = OpTree(hex(variable.const_value))
        else:
            if variable.offset.is_const and variable.length.is_const:
                optree = tree_from_variable(variable.value)
            else:
                sons = [tree_from_variable(variable.offset), tree_from_variable(variable.length)]
                optree = OpTree(variable.value.name, sons=sons)
    else:
        def_sites = list(variable.def_sites)[0]
        # def_sites is not None
        inst = def_sites.get_instruction()
        opcodeNode = inst.opcode.name
        loc = inst.loc

        references_blocks = set()
        references_blocks.add(def_sites.block)

        if opcodeNode == "CONST":
            optree = OpTree(hex(inst.lhs.const_value))
            if inst.lhs.const_value == 0:
                optree.is_zero = True
        elif opcodeNode == "MLOAD":
            if isinstance(inst.lhs.value, MemT.Variable):
                optree = tree_from_variable(inst.lhs.value)
            else:
                value = inst.lhs.value
                while hasattr(value, "value") and not isinstance(value.value, MemT.Variable):
                    value = value.value
                sons = [tree_from_variable(value.offset), tree_from_variable(value.length)]
                optree = OpTree(value.name, sons=sons, reference_blocks=references_blocks)
                optree.loc = loc
            # optree.transaction_index = inst.transaction_index
            # optree.transaction_value = inst.transaction_value
        else:
            # constant propagation
            sons = []
            if len(inst.values) > 0:
                if opcodeNode == "SHA3":
                    values = inst.values[2:]
                else:
                    values = inst.values
                for arg in values:
                    if not isinstance(arg, str): # for transactions, the args are real values
                        arg_value = arg.value
                        if arg_value.is_const:
                            const_tree = OpTree(hex(arg_value.const_value))
                            const_tree.is_zero = arg_value.const_value == 0
                            sons.append(const_tree)
                        else:
                            son = tree_from_variable(arg_value)
                            sons.append(son)
                    else:
                        if len(arg) > 0:
                            const_tree = OpTree("0x" + arg)
                            const_tree.is_zero = int("0x" + arg, 16) == 0
                            sons.append(const_tree)
            else:
                for arg in inst.args:
                    arg_value = arg.value
                    if arg_value.is_const:
                        const_tree = OpTree(hex(arg_value.const_value))
                        const_tree.is_zero = arg_value.const_value == 0
                        sons.append(const_tree)
                    elif arg_value.def_sites is not None:
                        son = tree_from_variable(arg_value)
                        sons.append(son)
                    else:
                        raise NotImplementedError("The arg value is not const and def_site is empty")
            # constant propagation
            if (opcodeNode == "DIV" and sons[0].is_zero) or (opcodeNode == "MUL" and (sons[0].is_zero or sons[1].is_zero)):
                optree = OpTree(hex(0))
                optree.is_zero = True
            elif opcodeNode == "ADD" and sons[0].is_zero:
                optree = sons[1]
            elif (opcodeNode == "ADD" and sons[1].is_zero) or (opcodeNode == "SUB" and sons[1].is_zero):
                optree = sons[0]
            else:
                optree = OpTree(opcodeNode, sons, references_blocks)
            # optree.transaction_index = inst.transaction_index
            # optree.transaction_value = inst.transaction_value
        
            optree.loc = loc

    if not need_opposite:
        if optree.is_zero:
            optree.is_zero = False 
        return optree
    else:
        if optree.name == "ISZERO":
            return optree.sons[0]
        else:
            optree = OpTree("ISZERO", optree)
            optree.loc = loc
            return optree

def expanded_condition_tree(_tree:OpTree):
    if _tree.alias_evm_variable is not None or _tree.name not in ['GT','ISZERO','EQ','LT','SLT','SGT','XOR']:
        # tree = OpTree("GT", [_tree, OpTree("0")])
        tree = OpTree("ISZERO", [OpTree("ISZERO", [_tree])])
        tree.contained_evm_args = _tree.contained_evm_args
        tree.contained_evm_states = _tree.contained_evm_states
        tree.contained_evm_properties = _tree.contained_evm_properties
        return tree
    else:
        return _tree

def tree_cast_removal(tree:OpTree, evm_analyzer=None) -> OpTree:
    if tree.alias_evm_variable is not None:
        return tree
    
    # bool cast
    if tree.name == "ISZERO" and tree.sons[0].name == "ISZERO":
        v = tree.sons[0].sons[0]
        if evm_analyzer is not None and v.alias_evm_variable is not None:
            alias_evm_variable = evm_analyzer.getEVMVariable(v.alias_evm_variable)
            # to make sure the alias evm variable is evm state
            if alias_evm_variable.index > -1 and isinstance(alias_evm_variable.keys, list) and alias_evm_variable.type.is_elementary and alias_evm_variable.length == 1:
                alias_evm_variable.change_to_bool_type()
        return tree_cast_removal(v, evm_analyzer)

    # uint/bytes cast
    elif tree.name == "AND":
        left, right = map(lambda x:x.name[2:] if x.name.startswith("0x") else x.name, tree.sons)
        if re.match("^(0)*(f)+$", left):
            return tree_cast_removal(tree.sons[1], evm_analyzer)
        elif re.match("^(0)*(f)+$", right):
            return tree_cast_removal(tree.sons[0], evm_analyzer)   

    # int cast
    elif tree.name == "SIGNEXTEND":
        return tree_cast_removal(tree.sons[1], evm_analyzer)

    # type fix
    # 0xd1613bfb12c53bff3fb19f6a8bc69c4a3a6cdf2d
    elif tree.name in ["ADD","MUL","SUB","DIV","SDIV","MOD","SMODE","EXP"]:
        for son in tree.sons:
            if evm_analyzer is not None and son.alias_evm_variable is not None:
                alias_evm_variable=evm_analyzer.getEVMVariable(son.alias_evm_variable)
                son.alias_evm_variable.change_to_computable_type()
                alias_evm_variable.change_to_computable_type()
    
    elif tree.name in ["SHR", "SAR"] and tree.sons[0].name == "0x0":
        return tree_cast_removal(tree.sons[1], evm_analyzer)
    
    return tree
