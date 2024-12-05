from typing import *

from .edge import Edge
from .node import Node, NodeType

class Graph:
    def __init__(self, nodes=None, edges=None, node2idx=None) -> None:
        self.nodes:List[Node] = list() if nodes is None else nodes
        self.edges:List[Edge] = list() if edges is None else edges        
        # id2node is nodes
        self.node2idx:Dict[int,int] = dict() if node2idx is None else node2idx

    def addNode(self, node:Node):
        if not node in self.nodes:
            self.node2idx[id(node)] = len(self.nodes)
            self.nodes.append(node)
            
    def getNode(self, _node:Node):
        for node in self.nodes:
            if node.node_type == _node.node_type:
                if _node.node_type.value >= 4:
                    break # always push the node
                else:
                    if node.name == _node.name:
                        return node
        self.addNode(_node)
        return _node

    def addEdge(self, edge:Edge):
        edge.lidx = self.node2idx[id(self.getNode(edge.lnode))] # use getNode rather than addNode
        edge.ridx = self.node2idx[id(self.getNode(edge.rnode))] # use getNode rather than addNode

        if not edge in self.edges:
            self.edges.append(edge)

    def dump(self):
        return {
            "nodes":[node.dump() for node in self.nodes],
            "edges":[edge.dump() for edge in self.edges]
        }
    
    @classmethod
    def build_from_edges(cls, edges:List[Tuple[Node,Node]]):
        graph = cls()
        for edge in edges:
            graph.addEdge(edge)
        
        return graph
    
    @classmethod
    def load(cls, data):
        nodes = []
        node2idx = dict()
        for node in data['nodes']:
            node = Node.load(node)
            node2idx[id(node)] = len(nodes)
            nodes.append(node)

        edges = []
        for edge in data['edges']:
            edge = Edge.load(edge)
            edge.lnode = nodes[edge.lidx]
            edge.rnode = nodes[edge.ridx]
            edges.append(edge)        
        return cls(nodes, edges, node2idx)
