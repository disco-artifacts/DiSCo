import copy
import json
import os
from collections import defaultdict
from typing import *

from disco.common.exceptions.LiftingExceptions import OutOfRulesException
from disco.common.structures.evm_variable import (SIZE_IN_BYTES, EVMArg, EVMProperty,
                                                   EVMState, EVMType,
                                                   EVMVariable)
from disco.common.structures.opcodes import BLOCK_TRANSACTION_PROPERTIES
from disco.common.structures.tac_tree import OpTree, tree_cast_removal
from disco.common.utils.lifting_utils import (compute_offset, hex2str, SHA3_MAPPING_PATH,
                                               is_numberic, numberic)

class EVMVariables:
    def __init__(self, evm_states:Set=None, evm_storage_dynamic_occupied:Dict=None, has_analyzed_trees:Dict=None, language:str="Solidity") -> None:
        """EVM Variables Collections"""
        self.evm_states:Set[EVMState] = set() if evm_states is None else evm_states
        self.evm_storage_dynamic_occupied:Dict[int,bool] = defaultdict(bool) if evm_storage_dynamic_occupied is None else defaultdict(lambda:False, evm_storage_dynamic_occupied)
        self.has_analyzed_trees:Dict[str,EVMVariable] = dict() if has_analyzed_trees is None else has_analyzed_trees

        self.evm_args:Set[EVMArg] = set()
        self.evm_properties:Set[EVMProperty] = set()
        
        self.language = language

    def getEVMVariable(self, evm_variable):
        if isinstance(evm_variable, EVMState):
            return self.getEVMState(evm_variable)
        elif isinstance(evm_variable, EVMProperty):
            return self.getEVMProperty(evm_variable)
        else:
            return self.getEVMArg(evm_variable)

    def getEVMState(self, evm_state:EVMState):
        """get evm_state in the evm_states, same id"""
        for _evm_state in self.evm_states:
            if evm_state.index == _evm_state.index:
                if self.evm_storage_dynamic_occupied[evm_state.index]:
                    return _evm_state
                elif evm_state.type is not None:
                    if not evm_state.type.is_dynamic and _evm_state == evm_state:
                        return _evm_state

                    elif evm_state.type.is_dynamic:
                        if evm_state.name is None:
                            evm_state.name = _evm_state.name
                        if _evm_state.is_public:
                            evm_state.is_public = _evm_state.is_public
                        self.evm_states.remove(_evm_state)
                        break
        # print("add new state variables "+str(evm_state))
        self.addEVMState(evm_state)
        return evm_state

    def getEVMArg(self, evm_arg:EVMArg):
        for _evm_arg in self.evm_args:
            if _evm_arg.index == evm_arg.index:
                if not evm_arg.is_dynamic:
                    return _evm_arg
                else:
                    _evm_arg.is_dynamic = evm_arg.is_dynamic
                    return _evm_arg
        self.addEVMArg(evm_arg)
        return evm_arg

    def getEVMProperty(self, evm_property:EVMProperty):
        for _evm_property in self.evm_properties:
            if _evm_property == evm_property:
                return _evm_property

        return evm_property

    def addEVMVariable(self, evm_variable):
        if isinstance(evm_variable, EVMState):
            self.addEVMState(evm_variable)
        else:
            self.addEVMArg(evm_variable)

    def addEVMState(self, evm_state:EVMState):
        if evm_state.offset is None and evm_state.length is None:
            self.evm_storage_dynamic_occupied[evm_state.index] = True
        self.evm_states.add(evm_state)

    def delEVMState(self, evm_state:EVMState):
        self.evm_states.remove(evm_state)

    def addEVMArg(self, evm_arg:EVMArg):
        self.evm_args.add(evm_arg)

    def addEVMProperty(self, evm_property:EVMProperty):
        self.evm_properties.add(evm_property)

    def dump(self) -> Dict:
        return {
            "EVMVariables":{
                "evm_states":[evm_state.dump() for evm_state in self.evm_states],
                "evm_storage_dynamic_occupied":self.evm_storage_dynamic_occupied,
                "has_analyzed_trees":{k:v.dump() for k,v in self.has_analyzed_trees.items() if isinstance(v, EVMState)}
            }
        }
    
    @classmethod
    def load(cls, data):
        return cls(
            evm_states=set(EVMState.load(evm_state) for evm_state in data['EVMVariables']['evm_states']),
            evm_storage_dynamic_occupied={int(k):v for k,v in data['EVMVariables']['evm_storage_dynamic_occupied'].items()},
            has_analyzed_trees={k:EVMState.load(v) for k,v in data['EVMVariables']['has_analyzed_trees'].items()}
        )    
    
class EVMVariableAnalyzer(EVMVariables):
    def __init__(self, evm_states:Set=None, evm_storage_dynamic_occupied:Dict=None, has_analyzed_trees:Dict=None, language:str="Solidity", checker=None) -> None:
        super().__init__(evm_states, evm_storage_dynamic_occupied, has_analyzed_trees, language=language)
        # for each path, locations/ref of state variables may be different
        # self.evm_state_ref = defaultdict(dict)
        """state variable lattice"""
        # self.evm_state_sstore_locations = defaultdict(list)
        
        self.checker = checker

    def reset_path_sensitive_args(self):
        # for each path, locations/ref of state variables may be different
        # self.evm_state_sstore_locations.clear()
        # self.evm_state_ref.clear()
        for evm_state in self.evm_states:
            evm_state.clear()
        if self.checker is not None:
            self.checker.reset()

    def forward_analysis(self, tree:OpTree, hints:defaultdict(bool), from_sstore:bool=False):
        """Returns the offset, length, hints of the state variable for type inference by forward analysis, function called by `self.sload_analysis`.
        
        Arguments:
            tree: OpTree, optree to analysis (root is SLOAD opcode or Index Const)
            hints: defaultdict(bool), type hints records
            from_sstore: bool, true iff sstore analysis
        Returns:
            offset: int, the offset of the state variable in a slot
            length: int, the length of the state variable in a slot
            hints: defaultdict(bool), some type hints
        """
        
        def forward_AND(tree:OpTree):
            offset, length = 0, SIZE_IN_BYTES
            forward_tree = tree.father
            if not from_sstore:
                and_value = forward_tree.get_son(NUM=True)
                # the and value is like 
                #   0x[0,m][f,n], it means it is lower_order (the higher 0s are omitted, length < 64)
                #   0x[f,m][0,n], it means it is higher_order
                if and_value is not None and is_numberic(and_value.name):
                    and_value = and_value.name[2:]
                    offset = 0
                    if len(and_value) == 64: 
                        hints['is_higher_order'] = True

                    if and_value == "1":
                        # string or bytes, e.g.,0xc8697fda750de0d9efb5782bbd620e7128cd09cd
                        hints['is_dynamic'] = True
                        return None, None, forward_tree
                    else:
                        length = and_value.count("f") // 2
                elif set([forward_tree.sons[0].name, forward_tree.sons[1].name]) == set(["SLOAD","SUB"]):
                    # string or bytes
                    hints['is_dynamic'] = True
                    return None, None, forward_tree
                else:
                    raise OutOfRulesException(f"[forward analysis], SLOAD->AND, but the and value {str(and_value)} is neither a const or sub")
            else:
                # infer type from sstore tree
                and_value = forward_tree.get_son(NUM=True)
                if and_value is not None and is_numberic(and_value.name):
                    and_value = and_value.name[2:]
                    and_value = and_value.rjust(64,"0")

                    offset = 0
                    length = 0
                    for v in reversed(and_value):
                        if v == "f":
                            offset += 1
                        else:
                            break
                    if offset == 0:
                        w_i = reversed(and_value)
                    else:
                        w_i = reversed(and_value[:-offset]) 
                    for v in w_i:
                        if v == "0":
                            length += 1
                        else:
                            break
                    if offset % 2 == 0 and length % 2 == 0:
                        offset = offset // 2
                        length = length // 2
                    else:
                        raise OutOfRulesException(f"length {str(length)} or offset {str(offset)} %2 != 0")

                else:
                    raise OutOfRulesException("SSTORE, but the node is const")
            return offset, length, forward_tree
        
        def forward_DIV(tree:OpTree):
            offset, length = 0, SIZE_IN_BYTES
            forward_tree = tree.father # forward tree's name is DIV
            div_value = forward_tree.sons[1].name
            if is_numberic(div_value):
                offset = compute_offset(div_value) // 2
                if offset == -1:
                    raise OutOfRulesException(f"[forward analysis], the exp value {str(div_value)} is not 2**x")
            else:
                raise OutOfRulesException(f"[forward analysis], the exp value {str(div_value)} is not 2**x")

            # compute length
            forward_tree = forward_tree.father
            # (SLOAD->DIV->SIGNEXTEND): int<M>
            if forward_tree.name == "SIGNEXTEND":
                hints['is_signed'] = True
                signextend_b = forward_tree.sons[0]
                if is_numberic(signextend_b.name):
                    length = numberic(signextend_b.name)+1
                else:
                    raise OutOfRulesException(f"[forward analysis], SIGNEXTEND bit {str(signextend_b)} is not const")
            
            # (SLOAD->DIV->AND): uint<M>、address、bool
            # AND is not strict-ordered
            elif forward_tree.name == "AND":
                if forward_tree.father is not None and forward_tree.father.name == "ISZERO":
                    # add boolean hints
                    hints['is_bool'] = True
                and_value = forward_tree.get_son(NUM=True)
                if and_value:
                    and_value = hex2str(and_value.name)
                    length = and_value.count("f") // 2
                else:
                    raise OutOfRulesException(f"[forward analysis], AND value {str(and_value)} is not const")
            
            # (SLOAD->DIV->MUL): bytes<M>
            elif forward_tree.name == "MUL":
                hints['is_higher_order'] = True
                mul_value = forward_tree.get_son(NUM=True)
                if mul_value:
                    mul_value = hex2str(mul_value.name)
                    length = SIZE_IN_BYTES - mul_value.count("0") // 2

                else:
                    raise OutOfRulesException(f"[forward analysis], MUL value {str(mul_value)} is not const")
            else:
                raise OutOfRulesException(f"[foward analysis], Unknown pattern SLOAD->DIV->{forward_tree.name}?")
            
            return offset, length, forward_tree
        
        if tree.name == "SLOAD":
            if tree.father is None:
                # offset is 0 and length is SIZE_IN_BYTES
                return 0, SIZE_IN_BYTES, tree
            else:
                
                    # SLOAD -> AND
                    if tree.father.name == "AND":
                        return forward_AND(tree)

                    # SLOAD -> DIV
                    elif tree.father.name == "DIV":
                        return forward_DIV(tree)

                    else:
                        # offset is 0 and length is SIZE_IN_BYTES
                        return 0, SIZE_IN_BYTES, tree

        # elif from_sstore and is_numberic(tree.name):
        elif is_numberic(tree.name):
            # offset is 0 and length is SIZE_IN_BYTES
            return 0, SIZE_IN_BYTES, tree

        else:
            raise OutOfRulesException(f"[forward analysis], the tree node {str(tree)} is not considered...")

    def backward_analysis(self, tree:OpTree, hints:defaultdict(bool)=None):
        """Returns the `index` of the state variable and type hints by analysis instructions iterativly

        Arguments:
            tree: OpTree, optree to analysis (root is SLOAD opcode or Index Const)
            hints: defaultdict(bool), type hints records
        Returns:
            index: int, the index of the state variable
            keys: List[Optional[EVMState,EVMArg]], shift indexs 
            hints: defaultdict(bool), type hints records

        """

        if hints is None: hints = defaultdict(bool)

        if tree.name == "SLOAD":
            root_backward_1 = tree.sons[0]
        else:
            root_backward_1 = tree

        keys = []
        index = self._handle(root_backward_1, hints, keys) 

        return index, keys

    def sload_analysis(self, tree:OpTree, from_sstore:bool=False, copy_state_variable:bool=True):
        """Returns the state variables using forward anslysis and backward analysis.

        ! Be careful when use sload analysis for it will add a state variable anyway.

        ? When or Why to use copy_state_variable, SSTORE, a1 = a0 + 1, different a, a0 is copied

        Arguments:
            tree: OpTree, optree to analysis (root is SLOAD opcode or Index Const)
            from_sstore: bool, true iff the tree is from sstore_analysis
            return_forward_tree: bool, true iff return the forward tree(only used to set alias_evm_variable)
        Returns:
            evm_state: EVMState, state variable
            keys: 
            forward_tree: OpTree, the tree is the pattern visiting the state variable
        """
        hints = defaultdict(bool)
        index, keys = self.backward_analysis(tree, hints)
        # for Public Variables, the forward tree is OpTree like SLOAD->DIV->AND
        # for Private Variables, the forward tree is Tree like SLOAD->AND (value is opposite)
        try:
            offset, length, forward_tree = self.forward_analysis(tree, hints, from_sstore=from_sstore)
        except OutOfRulesException as e:
            offset, length, forward_tree = 0, SIZE_IN_BYTES, tree
        # get is_dynamic from backward analysis but forward analysis may reupdate offset and length
        if hints['is_dynamic']: offset, length = None, None

        type = EVMType(hints, length)

        evm_state = EVMState(
            index=index,
            offset=offset,
            length=length,
            type=type)

        evm_state = self.getEVMVariable(evm_state)
        if copy_state_variable:
            evm_state = copy.deepcopy(evm_state)
        evm_state.keys = [self.set_alias_evm_variable_for_tree(v) for v in keys]
        
        return evm_state, forward_tree

    def calldata_backward(self, root:OpTree, hints):
        if is_numberic(root.sons[0].name):
            index = numberic(root.sons[0].name)
            # index = numberic(root.sons[0].name) - 0x4
            # if index % 0x20 == 0:
            #     index = index // 0x20
            # else:
            #     raise NotImplementedError("backward operations of CALLDATALOAD is not considerd, the (index-4)/0x20!=0")
        elif root.sons[0].name == "ADD":
            hints['is_dynamic'] = True
            hints['is_length'] = True
            # e.g., 0xd1ceeeefa68a6af0a5f6046132d986066c7f9426
            dep_call = root
            while True:
                calldataloads = dep_call.sons[0].sons[0].get_all_sons("CALLDATALOAD") + dep_call.sons[0].sons[1].get_all_sons("CALLDATALOAD")
                if len(calldataloads) == 0:
                    break
                else:
                    dep_call = calldataloads[0]
                if dep_call.sons[0].name != "ADD":
                    break
            if dep_call.name == "CALLDATALOAD":
                return self.calldata_backward(dep_call, hints)
            else:
                raise NotImplementedError("backward operations of CALLDATALOAD is not considerd")
        else:
            raise NotImplementedError("backward operations of CALLDATALOAD is not considerd")
        return index

    def calldata_analysis(self, calldata_tree:OpTree):
        hints = defaultdict(bool)
        arg_index = self.calldata_backward(calldata_tree, hints)

        keys = ""
        if hints['is_length']:
            keys = "length"
        elif hints['is_offset']:
            keys = "offset"
        
        if calldata_tree.father is not None and calldata_tree.father.name == "ADD" and calldata_tree.father.father is not None and calldata_tree.father.father.name == "CALLDATALOCA":
            keys = "offset"
            
        arg = EVMArg(index=arg_index, is_dynamic=hints['is_dynamic'], keys=keys)
        evm_arg = self.getEVMArg(arg)
        return evm_arg
        
    def sstore_analysis(self, key_tree:OpTree, value_tree:OpTree) -> List[Tuple[EVMState, OpTree]]:
        """Returns the operationed state variable and the to-set value.

        Arguments:
            key_tree: OpTree, the key argument of SSTORE (in tree format)
            value_tree: OpTree, the value argument of SSTORE (in tree format)
        Returns:
            evm_state: EVMState, state variable to update
            Vv: OpTree, the value to update
        """
        def _handle_OR(evm_state_tree):
            """The GV is AND => SLOAD => idx"""
            if evm_state_tree.name == "AND":
                # => AND
                and_son_backward_sload = evm_state_tree.get_son(NAME="SLOAD")
                if and_son_backward_sload:
                    # => AND => SLOAD
                    # Security
                    evm_state, _ = self.sload_analysis(and_son_backward_sload, from_sstore=True)
                else:
                    evm_state = None
                return evm_state, and_son_backward_sload
            else:
                return None, None
        
        def _handle_MUL(vvTree, hints):
            if vvTree.name == "AND":
                # => MUL => AND
                signextend_backward_value = vvTree.get_son(NAME="SIGNEXTEND")
                if signextend_backward_value:
                    # => MUL => AND => SIGNEXTEND
                    hints['is_signed'] = True
                    Vv = signextend_backward_value.sons[1]
                else:
                    # => MUL => AND
                    hints['is_signed'] = False
                    # ! break changes
                    Vv = vvTree
            # (value -> ISZERO -> ISZERO -> MUL): bool
            elif vvTree.name == "ISZERO":
                # => MUL => ISZERO
                iszero_backward_value = vvTree.get_son(NAME="ISZERO")
                if iszero_backward_value:
                    Vv = iszero_backward_value.sons[0]
                else:
                    raise NotImplementedError("sstore analysis, only one ISZERO")
            # (value -> DIV -> MUL): bytes<M>
            elif vvTree.name == "DIV":
                Vv = vvTree.sons[0]
                hints['is_higher_order'] = True
            else:
                Vv = None
            return Vv, hints

        updates = []
        evm_state = None
        Vv = None

        hints = defaultdict(bool)

        # set and to-set value are on the both sides of the tree
        # Or is not strict-ordered, try on the both
        # if the root is "OR", it means it has masking
        if value_tree.name == "OR":
            ors = value_tree.get_all_sons("OR")
            # * some optimizations may exist, two SSTOREs are optimized to one time, e.g. 0x73600ae44810343067e6fac315d90d30b3e0378a
            for sstore_time, vtree in enumerate(reversed(ors)):
                # for each iteration, edit the next tree tree.from_tree
                if sstore_time > 0 and sloadTree is not None:
                    ors[-sstore_time].from_tree(sloadTree)
                
                # first assume the left is vvTree and the right is evm_state_tree
                vvTree, evm_state_tree = vtree.sons
                evm_state, sloadTree = _handle_OR(evm_state_tree=evm_state_tree)
                index_, *_ = self.backward_analysis(key_tree)
                if evm_state is None or evm_state.index != index_:
                    # indeed, the left is evm_state_tree and the right is vvTree
                    evm_state_tree, vvTree = vtree.sons
                    evm_state, sloadTree = _handle_OR(evm_state_tree=evm_state_tree)
                    if evm_state is None or evm_state.index != index_:
                        # Security
                        evm_state, _ = self.sload_analysis(key_tree)
                        vvTree = vtree
                        if evm_state is None:
                            raise NotImplementedError("sstore analysis, evm_state_tree is not AND")
                # analysis to-set value

                # analysis write value
                # the left son(in tree format) is write_value
                # the right son(in tree format) is to pad (we aren't care about this)
                if vvTree.name == "MUL":
                    # => MUL
                    # vvTree_ = vvTree.sons[0]
                    # (value -> SIGNEXTEND -> AND -> MUL): int<M>
                    # (value -> AND -> MUL): uint<M>
                    Vv, hints_ = _handle_MUL(vvTree.sons[0], hints=defaultdict(bool))
                    if Vv is None:
                        Vv, hints_ = _handle_MUL(vvTree.sons[1], hints=defaultdict(bool))
                        if Vv is None:
                            # e.g., 0x999999c60566e0a78df17f71886333e1dace0bae
                            l,r = vvTree.sons[0].name.replace("0x",""), vvTree.sons[1].name.replace("0x","")
                            if l[0] == "1" and all(i =="0" for i in l[1:]):
                                Vv = vvTree.sons[1]
                            elif r[0] == "1" and all(i =="0" for i in r[1:]):
                                Vv = vvTree.sons[0]
                            else:
                                raise NotImplementedError("sstore analysis, the name of MUL is not in [AND,ISZERO,DIV]")
                        else:
                            hints.update(hints_)
                    else:
                        hints.update(hints_)
                else:
                    Vv = vvTree
                    if is_numberic(Vv.name):
                        # 0xa78987d838a113db1be683a6477d4279ed34510a
                        if evm_state.offset is not None and evm_state.offset + evm_state.length!= 32 and len(Vv.name) > (32-evm_state.offset-evm_state.length) * 2:
                            Vv.name = Vv.name[:-(32-evm_state.offset-evm_state.length)*2]

                Vv.father = None
                updates.append((evm_state, Vv))
        # AND with masking
        # AND without masking
        elif value_tree.name == "AND":
            and_son_backward_sload = value_tree.get_son(NAME="SLOAD")
            if and_son_backward_sload:
                index_right, *_ = self.backward_analysis(and_son_backward_sload)
                index_left, *_ = self.backward_analysis(key_tree)
                # masking
                if index_right == index_left:
                    left_value = value_tree.get_son(NAME="SLOAD",anti=True)
                    # => AND => SLOAD
                    # for contract 0xc1ec40b714281519ea367eb06429d1701ed18b5f BUYER_STEP_2: S[x] := S[y]
                    evm_state, _ = self.sload_analysis(and_son_backward_sload, from_sstore=True)
                    if evm_state.length and is_numberic(left_value.name) and left_value.name[2:].count("0") == evm_state.length * 2:
                        Vv = OpTree("0x0")
                    else:
                        Vv = value_tree

                else:
                    evm_state, _ = self.sload_analysis(key_tree)
                    Vv = value_tree

            else:
                evm_state, _ = self.sload_analysis(key_tree)
                Vv = value_tree
            Vv.father = None
            updates.append((evm_state, Vv))
        else:
            # 0xbee149d5cef48724918836c48f2749a5c5f75f8c update to CALLVALUE
            evm_state, _ = self.sload_analysis(key_tree)
            Vv = value_tree
            Vv.father = None
            updates.append((evm_state, Vv))

        return updates

    def _handle_SHA3(self, root:OpTree, hints=defaultdict(bool), keys:List=[]):
        # when the type is mapping, the sons are (key, v's slot)
        # the first two args are offset and length
        # https://ethereum.stackexchange.com/questions/149311/storage-collision-in-vyper-hashmap
        if len(root.sons) == 2:
            hints['is_mapping'] = True
            hints['is_array'] = False
            if self.language == "Vyper":
                keys.insert(0, root.sons[1])
                return self._handle(root.sons[0], hints, keys)
            else:
                keys.insert(0, root.sons[0])
                return self._handle(root.sons[1], hints, keys)

        # when the type is dynamic array, the sons are v's slot
        elif len(root.sons) == 1:
            hints['is_array'] = True
            hints['is_mapping'] = False
            hints['is_dynamic'] = True
            return self._handle(root.sons[0], hints)

        else:
            raise NotImplementedError("The count of SHA3's sons is not in [1,2]")

    # 0x27c48b2f1d99cab6f6f6ae143204a0029666e29b
    def _ADD_has_SHA3(self, root:OpTree) -> OpTree:
        if root.name == "ADD":
            if root.sons[0].name == "SHA3":
                return root.sons[0], root.sons[1]
            elif root.sons[1].name == "SHA3":
                return root.sons[1], root.sons[0]
            elif root.sons[0].name == "ADD":
                return self._ADD_has_SHA3(root.sons[0])
            elif root.sons[1].name == "ADD":
                return self._ADD_has_SHA3(root.sons[1])
            else:
                return None, None
        else:
            return None, None

    def _handle_ADD(self, root:OpTree, hints=defaultdict(bool), keys:List=[]):
        # both the sons are not const, because of const folding
        hints['is_array'] = True
        # the left is visit params 
        # and the right is index
        sha3_node, _keys = self._ADD_has_SHA3(root)
        if sha3_node:
            # dynamic array
            hints['is_dynamic'] = True
            keys.insert(0, _keys)
            return self._handle(sha3_node, hints, keys)
        # some optimization on SHA3, e.g. is 0x7255e01f934307ffb7a41fc78b6b1688f5dc6845
        elif len(root.sons[0].name) == 64+2 and root.sons[1].name == "SLOAD":
            hints['is_dynamic'] = True
            root.sons[0] = OpTree("SHA3", root.sons[1].sons)
            return self._handle(root.sons[0] , hints, keys)
        elif len(root.sons[1].name) == 64+2 and root.sons[0].name == "SLOAD":
            hints['is_dynamic'] = True
            root.sons[1] = OpTree("SHA3", root.sons[0].sons)
            return self._handle(root.sons[1] , hints, keys)
        else:
            # static array
            return self._handle(root.sons[1], hints, keys)

    def _handle_CONST(self, root:OpTree, hints=defaultdict(bool)):
        if is_numberic(root.name):
            return numberic(root.name)
        else:
            hints['is_array'] = True
            return 0

    def _handle(self, root:OpTree, hints=defaultdict(bool), keys=[]):
        """
        - For `simple variable`, `T v`, visiting `v` by `v's slot'
        - For `Fixed-size array`, `T[10] v`, visiting `v[n]` by `(v's slot) + n*(size of T)`
        - For `Dynamic array`, `T[] v`, visiting `v[n]` by `SHA3(v's slot) + n*(size of T)`
                                        visiting `v.length` by `v's slot`
        - For `Mapping`, `mapping(T1 => T2) v`, visiting `v[key]` by `SHA3(key.(v's slot)`
        """
        # mapping(T1 => T2) v, v[key], SHA3(key.(v's slot)) 
        if root.name == "SHA3":
            index = self._handle_SHA3(root, hints, keys)
        # T[] v, v[n], SHA3(v's slot) + n * (size of T)
        #        v.length v's slot
        # T[10] v, v[n], (v's slot) + n*(size of T)
        elif root.name == "ADD":
            index = self._handle_ADD(root, hints, keys)
        # T v, v, v's slot
        else:
            index = self._handle_CONST(root, hints)

        return index

    def set_alias_evm_variable_for_tree(self, tree:OpTree, copy_state_variable:bool=True) -> OpTree:
        """Returns the value tree after setting alias_evm_variable.

        Arguments:
            tree: OpTree, tree structure of the updated value.
        Returns:
            tree: OpTree, tree structure of the updated value, some tree node with `alias_evm_variable` attribute.
        """
        evm_states:List[EVMState] = []
        evm_args:List[EVMArg] = []
        evm_properties:List[EVMProperty] = []

        queue = [tree]
        while len(queue) > 0:
            current = queue.pop()
            current_str = str(current)
            if current_str in self.has_analyzed_trees:
                _analyzed_evm_variable = self.has_analyzed_trees[current_str]
                _alias_evm_variable = self.getEVMVariable(_analyzed_evm_variable)
                if copy_state_variable and isinstance(_alias_evm_variable, EVMState):
                    alias_evm_variable = copy.deepcopy(_alias_evm_variable)
                    alias_evm_variable.keys = _analyzed_evm_variable.keys
                    alias_evm_variable.counts = self.compute_counts(alias_evm_variable, current)
                else:
                    alias_evm_variable = _alias_evm_variable
                
                # .append(alias_evm_variable)
                current.alias_evm_variable = alias_evm_variable
                
                if isinstance(alias_evm_variable, EVMState):
                    evm_states.append(alias_evm_variable)
                elif isinstance(alias_evm_variable, EVMArg):
                    evm_args.append(alias_evm_variable)
                elif isinstance(alias_evm_variable, EVMProperty):
                    evm_properties.append(alias_evm_variable)
                
                current.contained_evm_states = evm_states
                current.contained_evm_args = evm_args
                current.contained_evm_properties = evm_properties
                
            else:
                if current.name == "SLOAD":
                    alias_evm_variable, forward_tree = self.sload_analysis(current, copy_state_variable=copy_state_variable)
                    self.has_analyzed_trees[str(forward_tree)] = alias_evm_variable

                    if alias_evm_variable is not None:
                        alias_evm_variable.counts = self.compute_counts(alias_evm_variable, forward_tree)
                        forward_tree.alias_evm_variable = alias_evm_variable
                        
                        forward_tree.contained_evm_states.append(alias_evm_variable)
                        evm_states.append(alias_evm_variable)
                                        
                elif "CALLDATALOAD" in current.name:
                    alias_evm_variable = self.calldata_analysis(current)
                    self.has_analyzed_trees[str(current)] = alias_evm_variable

                    if alias_evm_variable is not None:
                        current.alias_evm_variable = alias_evm_variable
                        evm_args.append(alias_evm_variable)
                
                # e.g., Vyper contract 0xa0a4a2af46af4cf37eacc495eedcae269ef2720e CALLDATACOPY[0x4:0x20] is arg1
                elif "CALLDATACOPY" in current.name:
                    if current.sons[1].name == "CALLDATALOAD":
                        alias_evm_variable = self.calldata_analysis(current.sons[1])
                        # alias_evm_variable.keys = "value"
                        self.has_analyzed_trees[str(current)] = alias_evm_variable

                        if alias_evm_variable is not None:
                            current.alias_evm_variable = alias_evm_variable
                            evm_args.append(alias_evm_variable)
                            
                    elif current.sons[0].name == "0x0" and current.sons[1].name == "CALLDATASIZE":
                        alias_evm_variable = EVMArg(-1, is_dynamic=True)
                        self.has_analyzed_trees[str(current)] = alias_evm_variable

                        if alias_evm_variable is not None:
                            current.alias_evm_variable = alias_evm_variable
                            evm_args.append(alias_evm_variable)
                    
                    elif current.sons[0].name == "ADD":
                        calldataload_sons = current.sons[0].get_all_sons("CALLDATALOAD")
                        alias_evm_variable = None
                        for calldata_son in calldataload_sons:
                            if calldata_son.father.name == "ADD" and calldata_son.father.sons[0].name == "0x4":
                                alias_evm_variable = self.calldata_analysis(calldata_son.father.sons[1])
                            elif calldata_son.father.name == "ADD" and calldata_son.father.sons[1].name == "0x4":
                                alias_evm_variable = self.calldata_analysis(calldata_son.father.sons[0])
                        
                        # if current.sons[0].sons[0].name == "0x4" and current.sons[0].sons[1].name == "CALLDATALOAD":
                        #     alias_evm_variable = self.calldata_analysis(current.sons[0].sons[1])
                        # elif current.sons[0].sons[1].name == "0x4" and current.sons[0].sons[0].name == "CALLDATALOAD":
                        #     alias_evm_variable = self.calldata_analysis(current.sons[0].sons[0])
                        # else:
                        #     alias_evm_variable = None                            

                        if alias_evm_variable is not None:
                            # alias_evm_variable.keys = "value"
                            self.has_analyzed_trees[str(current)] = alias_evm_variable

                            current.alias_evm_variable = alias_evm_variable
                            evm_args.append(alias_evm_variable)
                            
                    elif current.sons[0].name.startswith("0x"):
                        alias_evm_variable = EVMArg(numberic(current.sons[0].name), is_dynamic=False)
                        self.has_analyzed_trees[str(current)] = alias_evm_variable

                        if alias_evm_variable is not None:
                            current.alias_evm_variable = alias_evm_variable
                            evm_args.append(alias_evm_variable)
                        
                elif current.name in BLOCK_TRANSACTION_PROPERTIES or current.name.startswith("0x"): # const
                    evm_property = EVMProperty(current.name)
                    self.has_analyzed_trees[str(current)] = evm_property
                    
                    if evm_property is not None:
                        current.alias_evm_variable = evm_property
                        evm_properties.append(evm_property)

                else:
                    for son in current.sons:
                        queue.append(son)

        tree = self.type_cast_removal(tree)
        
        tree.contained_evm_states = evm_states
        tree.contained_evm_args = evm_args
        tree.contained_evm_properties = evm_properties
        
        return tree

    def compute_counts(self, evm_state:EVMState, forward_tree:OpTree):
        son = forward_tree.get_all_sons("SLOAD")[0]
        loc = son.loc
        res = 0
        
        __keys_str = ""
        for v in evm_state.keys:
            __keys_str += "[%s]"%(str(v))

        for index in evm_state.counts_mapping[__keys_str]:
            if index <= loc:
                res += 1
            else:
                break
        return res

    def string_bytes_shift_removal(self, tree:OpTree):
        if tree.name == "OR":
            lson, rson = tree.sons
            if lson.name == "AND":
                llson, rlson = lson.sons  
            elif rson.name == "AND":
                llson, rlson = rson.sons
            else:
                return tree

            if llson.alias_evm_variable is not None and hasattr(llson.alias_evm_variable, 'is_dynamic') and llson.alias_evm_variable.is_dynamic and rlson.name == "NOT" and str(rlson.sons[0]).startswith("((0x100 ** (0x20 - "):
                return llson
            elif rlson.alias_evm_variable is not None and hasattr(rlson.alias_evm_variable, 'is_dynamic') and rlson.alias_evm_variable.is_dynamic and llson.name == "NOT" and str(llson.sons[0]).startswith("((0x100 ** (0x20 - "):
                return rlson
            else:
                return tree
        else:
            return tree
    
    # With Tree Edit
    def type_cast_removal(self, tree:OpTree):
        tree = self.string_bytes_shift_removal(tree)
        tree = tree_cast_removal(tree, self)
        queue = [tree]
        while len(queue) > 0:
            current = queue.pop()
            for s_idx, son in enumerate(current.sons):
                new_son = tree_cast_removal(son, self)
                current.sons[s_idx] = new_son
                queue.append(new_son)
        return tree