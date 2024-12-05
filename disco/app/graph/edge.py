from .node import Node

class Edge:
    def __init__(self, lnode:Node=None, rnode:Node=None, lidx:int=-1, ridx:int=-1) -> None:
        self.lnode = lnode
        self.rnode = rnode
        
        self.lidx = lidx
        self.ridx = ridx
        
    def dump(self):
        return {"lidx":self.lidx, "ridx":self.ridx}
    
    @classmethod
    def load(cls, data):
        return cls(lidx=data["lidx"], ridx=data["ridx"])
