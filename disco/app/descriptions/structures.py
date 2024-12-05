from typing import *


class SemanticNode:
    def __init__(self, node, node_hash=None, pres=None, succs=None) -> None:
        self.node = node
        
        self.node_hash = node_hash
        
        self.pres = [] if pres is None else pres
        self.succs = [] if succs is None else succs

    def __eq__(self, __o: object) -> bool:
        return type(__o) == type(self) and hash(__o) == hash(self)

    def __hash__(self) -> int:
        if self.node_hash is None:
            self.node_hash = hash(self.node)
        return self.node_hash

    def __str__(self) -> str:
        return str(self.node)

    def __repr__(self) -> str:
        return repr(self.node)

class SemanticUnitGraph:
    # Node Types: Condition or Behavior
    def __init__(self) -> None:
        self.roots = []
        
        self.nodes:List[SemanticNode] = []
        self.edges:List[Tuple[SemanticNode,SemanticNode]] = []
        
    def addNode(self, elem):
        node = SemanticNode(elem)
        if not node in self.nodes:
            self.nodes.append(node)
        else:
            node = self.nodes[self.nodes.index(node)]
        return node
        
    def addEdge(self, src, dst):
        src_node = self.addNode(src)
        dst_node = self.addNode(dst)
        
        if dst_node not in src_node.succs:            
            dst_node.pres.append(src_node)
            src_node.succs.append(dst_node)
            self.edges.append((src_node, dst_node))

    def getRoots(self):
        roots = []
        for node in self.nodes:
            if len(node.pres) == 0:
                roots.append(node)
        self.roots = roots
        
        return roots
    
    def vis_graph(self):
        from graphviz import Digraph
        G = Digraph(node_attr={"class":"node"},edge_attr=None, graph_attr={"rankdir":"lr","bgcolor":"lemonchiffon"})
        for node in self.nodes:
            G.node(str(hash(node)), shape='box', label=str(node), style='filled')

        for src, dst in self.edges:
            G.edge(str(hash(src)), str(hash(dst)))
            
        return G
