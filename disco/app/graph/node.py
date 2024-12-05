from enum import Enum

class NodeType(Enum):
    OBJ_EVM_STATE = 0
    OBJ_EVM_PROPERTY = 1

    # the semantics of the following two types of nodes would be masked
    OBJ_EVM_ARG = 2 # Masked as Arg
    OBJ_CONST = 3 # Masked as Const
    
    OP_COMPARISON = 4 # `>`,`<`,etc.
    OP_ARITHMETIC = 5 # `+`,`-`,etc.
    OP_LOGIC = 6 # only `cause`` node

    OP_BEHAVIOR = 7 # `CALLX`,`SSTORE`,`DESTRUCT`,`CREATEX`
    OP_KEY = 8  # to represent balanceOf`[CALLER]` and bids`[n]`
    
    OP_UNK = 9

NODE_TYPE_COLOR = {
    NodeType.OP_COMPARISON:"linen",
    NodeType.OP_BEHAVIOR: "palegreen",
    NodeType.OP_ARITHMETIC: "lightskyblue",
    NodeType.OP_LOGIC: "salmon",
    NodeType.OP_KEY: "lightskyblue",
    NodeType.OP_UNK: "grey"
}

class Node:
    def __init__(self, name:str, node_type:NodeType, data_type:str="", unseen_name:str="") -> None:
        self.name = name
        self.node_type = node_type
    
        # the following two attributes are used for name inference
        # data_type means address, uint256, etc.
        self.data_type = data_type
        # psv name is the ground name of the name
        self.unseen_name = unseen_name
    
    def __hash__(self) -> int:
        return hash(str(self))
    
    def __str__(self) -> str:
        return f"{self.name}({self.node_type.name})"
    
    def __repr__(self) -> str:
        return "<{0} object {1}: {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        )

    def dump(self):
        return {"name":self.name, "node_type":self.node_type.name, "data_type":self.data_type, "unseen_name":self.unseen_name}
    
    @classmethod
    def load(cls, data):
        name = data["name"]
        node_type = getattr(NodeType, data["node_type"])
        data_type = data["data_type"]
        unseen_name = data["unseen_name"]
        
        return cls(name=name, node_type=node_type, data_type=data_type, unseen_name=unseen_name)