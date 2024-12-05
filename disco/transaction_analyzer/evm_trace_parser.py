import typing as t
import disco.common.structures.evm_cfg as cfg
import disco.common.structures.opcodes as opcodes

class EVMTraceParser:
    def __init__(self, trace:t.Iterable[dict]) -> None:
        """
        Parses raw trace and creates corresponding EVMOps.
        """
        
        self._trace = trace
        
        self._ops = []
        """
        List of program operations extracted from the raw input object.
        Indices from this list are used as unique identifiers for program
        operations when constructing BasicBlocks.
        """
        
    def parse(self) -> t.Iterable[cfg.EVMOp]:
        for traceop in self._trace:
            self._ops.append(self.evm_op_from_traceop(traceop))

        return self._ops
    
    @staticmethod
    def evm_op_from_traceop(traceop:dict) -> cfg.EVMOp:
        pc = int(traceop['pc'], 16)
        vals = traceop['values'] # all hex value
        opcode = opcodes.opcode_by_name(traceop['op'])
        
        if opcode.is_push0():
            val = 0
        else:
            if opcode.is_push():
                val = int(vals[0],16)
            else:
                val = None
        
        return cfg.EVMOp(
            pc=pc,
            opcode=opcode,
            value=val,
            values=vals
        )