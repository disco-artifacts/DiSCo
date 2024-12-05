import disco.common.structures.base.memtypes as MemT

class TACArg:
    """
    Contains information held in an argument to a TACOp.
    A TACArg may hold the current value of an argument, if it exists.
    This allows updated/refined stack data to be propagated 
    into the body of a TACBasicBlock.
    """
    def __init__(self, var: MemT.Variable = None):
        self.value = var

    def __str__(self):
        return str(self.value)

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        )

    @classmethod
    def from_var(cls, var: MemT.Variable):
        return cls(var=var)

class TACLocRef:
    """Contains a reference to a program counter within a particular block."""

    def __init__(self, block, pc):
        self.block = block
        """The block that contains the referenced instruction."""
        self.pc = pc
        """The program counter of the referenced instruction."""

    def __deepcopy__(self, memodict={}):
        return type(self)(self.block, self.pc)

    def __str__(self):
        return "{}.{}".format(self.block.ident(), hex(self.pc))

    def __eq__(self, other):
        return self.block == other.block and self.pc == other.pc

    def __hash__(self):
        return hash(self.block) ^ hash(self.pc)

    def get_instruction(self):
        """Return the TACOp referred to by this TACLocRef, if it exists."""
        for i in self.block.tac_ops:
            if i.pc == self.pc:
                return i
        return None
