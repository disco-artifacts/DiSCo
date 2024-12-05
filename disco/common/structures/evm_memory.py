import typing as T
from copy import deepcopy

import disco.common.structures.base.memtypes as MemT
from disco.common.exceptions.MemoryHandlingExceptions import MemoryLengthExtendedError

SIZE_IN_BYTES:int = 32

class DynamicVariable:
    def __init__(self, value:MemT.Variable, offset:MemT.Variable, length:MemT.Variable=None):
        self.value = value
        self.offset = offset
        self.length = MemT.Variable(value=1, name="C") if length is None else length
    
    def __str__(self) -> str:
        return "{}:[{}:{}+{}]".format(str(self.value), str(self.offset), str(self.offset), str(self.length))

    def __repr__(self) -> str:
        return "<{0} object {1}: {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )

    def __hash__(self) -> int:
        return hash("%d-%d-%d"%(hash(self.value), hash(self.offset), hash(self.length)))

    def __eq__(self, __o: object) -> bool:
        return type(self) == type(__o) and hash(self) == hash(__o)

    def length_extend(self, extend_length:int=1):
        if self.length.is_const:
            self.length = MemT.Variable(value=self.length.const_value + extend_length, name="C")
        else:
            raise MemoryLengthExtendedError(f"the extend length {str(extend_length)} is not a const")
            
    @property
    def is_const(self) -> bool:
        return self.value.is_const and self.offset.is_const and self.length.is_const

    @property
    def const_value(self):
        if self.is_const:
            if self.length.const_value == 0:
                return 0 # ! error, e.g., 0x867ffb5a3871b500f65bdfafe0136f9667deae06,0xd1ceeeeee83f8bcf3bedad437202b6154e9f5405
            return int("0x"+hex(self.value.const_value)[2:].rjust(64,"0")[self.offset.const_value*2:self.offset.const_value*2+self.length.const_value*2],16)
        else:
            return None

    @property
    def name(self):
        if self.value is not None:
            return self.value.name
        else:
            return None

    @classmethod
    def zero_value(cls):
        return cls(
            value=MemT.Variable(value=0, name="C"),
            offset=MemT.Variable(value=0, name="C")
        )

    def __deepcopy__(self, memodict={}):
        return type(self)(self.value,
                          self.offset,
                          self.length)

def variable_propagation(v:MemT.Variable) -> MemT.Variable:
    while isinstance(v, MemT.Variable) and v.value is not None and (isinstance(v.value, MemT.Variable)):
        v = v.value
    return v

def stack_memory(m_list):
    ret_m = []
    for m in m_list:
        ret_m.append(m)
        if isinstance(m, DynamicVariable) and m.length.is_const and isinstance(ret_m[-1], DynamicVariable) and ret_m[-1].value.is_const and ret_m[-1].value.const_value == 0:
            ret_m.pop()
            ret_m.append(m)
    return ret_m
class MemoryException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class EVMMemory:

    def __init__(self, memory_list=None, memory_mapping=None) -> None:
        """A light weight Memory implement
        Here, we did not implement MLOAD/MSTORE totally,
        for example, if lenght is variable when comes to CALLDATACOPY
        
        For accurately implementation, please ref pape `Precise static modeling of Ethereum memory`"""
        self.memory_list:T.List[DynamicVariable] = memory_list if memory_list is not None else list()
        self.memory_mapping = memory_mapping if memory_mapping is not None else dict()

    def mload(self, offset:MemT.Variable, length:MemT.Variable=None) -> T.List:
        if length is None: length = MemT.Variable(value=SIZE_IN_BYTES)

        offset = variable_propagation(offset)
        length = variable_propagation(length)
        
        if offset in self.memory_mapping:
            if length in self.memory_mapping[offset]:
                return [self.memory_mapping[offset][length]]
            else:
                # todo
                var = list(self.memory_mapping[offset].values())[:][0]
                var.length = length
                
                return [var]
        
        elif not offset.is_const:
            if offset in self.memory_mapping:                
                self.memory_mapping[offset][length] = MemT.Variable(value=0, name="C")
            else:
                self.memory_mapping[offset] = {length:MemT.Variable(value=0, name="C")}
        
            return [self.memory_mapping[offset][length]]
        
        elif offset.is_const and length.is_const:
            offset_const = offset.const_value
            length_const = length.const_value
            if length_const == 0:
                return []

            if len(self.memory_list) < offset_const+length_const:
                self.memory_list.extend([DynamicVariable.zero_value() for _ in range(offset_const+length_const-len(self.memory_list))])
            mload_values = [deepcopy(self.memory_list[offset_const])]
            for i in range(1,length_const):
                if self.memory_list[offset_const+i].value == mload_values[-1].value:
                    if self.memory_list[offset_const+i].value.is_const and mload_values[-1].value.is_const and mload_values[-1].value.const_value==0:
                        mload_values[-1].length_extend()
                    elif self.memory_list[offset_const+i].offset.is_const and mload_values[-1].offset.is_const and mload_values[-1].length.is_const:
                        if self.memory_list[offset_const+i].offset.const_value == mload_values[-1].offset.const_value + mload_values[-1].length.const_value:
                            mload_values[-1].length_extend()
                        else:
                            mload_values.append(deepcopy(self.memory_list[offset_const+i]))
                    else:
                        raise MemoryLengthExtendedError(f"memory length cannot extended")
                else:
                    mload_values.append(deepcopy(self.memory_list[offset_const+i]))

            memValues = []
            for mvalue in mload_values:
                if isinstance(mvalue, MemT.Variable):
                    memValues.append(mvalue)
                elif isinstance(mvalue.value, MemT.Variable):
                    if mvalue.offset.is_const and mvalue.length.is_const and mvalue.offset.const_value == 0 and mvalue.length.const_value == 0x20:
                        memValues.append(mvalue.value)
                    else:
                        memValues.append(mvalue)
                else:
                    if mvalue.offset.is_const and mvalue.length.is_const:
                        offset_const = mvalue.offset.const_value
                        length_const = mvalue.length.const_value
                        dvalue = mvalue.value
                        if dvalue.offset.is_const and dvalue.length.is_const:
                            d_offset_const = dvalue.offset.const_value
                            d_length_const = dvalue.length.const_value
                            if d_offset_const + d_length_const >= offset_const + length_const:
                                mvalud_copy = deepcopy(mvalue.value)
                                mvalud_copy.offset = MemT.Variable(value=offset_const+d_offset_const, name="C")
                                mvalud_copy.length = MemT.Variable(value=length_const, name="C")
                                memValues.append(mvalud_copy)
                            else:
                                memValues.append(mvalue)
                        else:
                            memValues.append(mvalue)
                    else:
                        memValues.append(mvalue)                    
            
            return stack_memory(memValues)
        else:
            raise MemoryLengthExtendedError("Memory loop up error")

    def mstore(self, offset:MemT.Variable, value:MemT.Variable, length:MemT.Variable=None) -> None:
        if length is None:
            length = MemT.Variable(value=SIZE_IN_BYTES)
        if isinstance(length, int):
            length = MemT.Variable(value=length)
        offset = variable_propagation(offset)
        value = variable_propagation(value)
        length = variable_propagation(length)

        if offset.is_const and length.is_const:
            offset = offset.const_value
            length = length.const_value
            
            if len(self.memory_list) < offset+length:
                self.memory_list.extend([DynamicVariable.zero_value() for _ in range(offset+length-len(self.memory_list))])

            for i in range(length):
                self.memory_list[offset+i] = DynamicVariable(value=value, offset=MemT.Variable(value=i, name="C"))
            return
        else:
            if offset in self.memory_mapping:                
                self.memory_mapping[offset][length] = value
            else:
                self.memory_mapping[offset] = {length:value}

    def __str__(self) -> str:
        ret = "Sured:" + "\n"
        cot = len(self.memory_list)
        for i in range(0, cot//32):
            var = self.mload(i*32, 32)
            for v in var:
                if v.is_const:
                    ret += "[%d:%d]:%s"%(i*32,(i+1)*32,hex(v.const_value)) + "\n"
                else:
                    ret += "[%d:%d]:%s"%(i*32,(i+1)*32,v.name) + "\n"

        ret += "UnSured:" + "\n"
        for k,v in self.memory_mapping.items():
            ret += "%s:%s"%(str(k), str(v)) + "\n"
        return ret

    def __repr__(self) -> str:
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )

    def __deepcopy__(self, memodict={}):
        return type(self)(deepcopy(self.memory_list), deepcopy(self.memory_mapping))