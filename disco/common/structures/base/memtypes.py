# BSD 3-Clause License
#
# Copyright (c) 2016, 2017, The University of Sydney. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""memtypes.py: Symbolic representations of ways of storing information
in the ethereum machine."""

import copy
import typing as t

VAR_DEFAULT_NAME = "Var"
"""The fallback name when creating a fresh variable."""
VAR_RESULT_NAME = "Res"
"""The name to apply to variables resulting from an arithmetic operation."""


class Variable:
    """
    A symbolic variable whose value is supposed to be
    the result of some TAC operation. Its size is 32 bytes.
    """

    SIZE = 32
    """Variables are 32 bytes in size."""

    CARDINALITY = 2 ** (SIZE * 8)
    """
    The number of distinct values this variable could contain.
    The maximum integer representable by this Variable is then CARDINALITY - 1.
    """

    def __init__(self, value = None, name: str = VAR_DEFAULT_NAME,
                 def_sites = None, use_sites = None):
        """
        Args:
          values: the set of values this variable could take.
          name: the name that uniquely identifies this variable.
          def_sites: a set of locations (TACLocRefs) where this variable
                     was possibly defined.
          use_sites: a set of locations (TACLocRefs) where this variable
                     was possibly used.                    
        """
        if isinstance(value, int):
            self.value = value % self.CARDINALITY
        else:
            self.value = None
        self.name = name
        self.def_sites = def_sites
        self.use_sites = use_sites

    def __deepcopy__(self, memodict={}):
        return type(self)(copy.deepcopy(self.value, memodict),
                          self.name,
                          self.def_sites[:],
                          None if self.use_sites is None else self.use_sites[:])

    @property
    def identifier(self) -> str:
        """Return the string identifying this object."""
        return self.name

    @property
    def is_const(self) -> bool:
        return isinstance(self.value, int)

    @property
    def const_value(self) -> int:
        if self.is_const:
            return self.value
        else:
            return None

    def __str__(self):
        if self.is_const:
            if self.identifier == "C":
                return hex(self.const_value)
            else:
                return "%s(%s)"%(self.identifier,hex(self.const_value))
        elif self.value is not None:
            return "%s(%s)"%(self.identifier,str(self.value))
        else:
            return self.identifier
        
    def __repr__(self):
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        )

    def __eq__(self, other):
        return type(self) == type(other) and hash(self) == hash(other)

    def __hash__(self):
        # return hash(self.identifier)
        if self.value is not None:
            return hash(self.value)
        else:
            return hash(self.identifier)
    
    def __lt__(self, __o:object) -> bool:
        if type(__o) == type(self):
            if self.is_const and __o.is_const:
                if self.const_value < __o.const_value:
                    return True
            else:
                return self.identifier < __o.identifier    
        return False

    def complement(self) -> 'Variable':
        """
        Return the signed two's complement interpretation of this constant's values.
        """
        return type(self)(value=self.twos_comp(self.value),
                          name=VAR_RESULT_NAME)

    @classmethod
    def twos_comp(cls, v: int) -> int:
        """
        Return the signed two's complement interpretation of the given integer.
        """
        return v - cls.CARDINALITY if v & (cls.CARDINALITY >> 1) else v

    # EVM arithmetic operations follow.
    # For comparison operators, "True" and "False" are represented by Constants
    # with the value 1 and 0 respectively.
    # Op function names should be identical to the opcode names themselves.

    @classmethod
    def arith_op(cls, opname: str, args: t.Iterable['Variable'],
                 name=VAR_RESULT_NAME) -> 'Variable':
        """
        Apply the named arithmetic operation to the given Variables' values
        in all permutations, and return a Variable containing the result.

        Args:
          opname: the EVM operation to apply.
          args: a sequence of Variables whose length matches the
                arity of the specified operation.
          name: the name of the result Variable.
        """
        # prod = itertools.product(*(list(e) for e in args))
        args = [arg.const_value for arg in args]
        f = getattr(cls, opname)
        return cls(value=f(*args), name=name)

    @classmethod
    def ADD(cls, l: int, r: int) -> int:
        """Return the sum of the inputs."""
        return l + r

    @classmethod
    def MUL(cls, l: int, r: int) -> int:
        """Return the product of the inputs."""
        return l * r

    @classmethod
    def SUB(cls, l: int, r: int) -> int:
        """Return the difference of the inputs."""
        return l - r

    @classmethod
    def DIV(cls, l: int, r: int) -> int:
        """Return the quotient of the inputs."""
        return 0 if (r == 0) else (l // r)

    @classmethod
    def SDIV(cls, l: int, r: int) -> int:
        """Return the signed quotient of the inputs."""
        l_val, r_val = cls.twos_comp(l), cls.twos_comp(r)
        sign = 1 if ((l_val * r_val) >= 0) else -1
        return 0 if (r_val == 0) else (sign * (abs(l_val) // abs(r_val)))

    @classmethod
    def MOD(cls, v: int, m: int) -> int:
        """Modulo operator."""
        return 0 if (m == 0) else (v % m)

    @classmethod
    def SMOD(cls, v: int, m: int) -> int:
        """Signed modulo operator. The output takes the sign of v."""
        v_val, m_val = cls.twos_comp(v), cls.twos_comp(m)
        sign = 1 if (v_val >= 0) else -1
        return 0 if (m == 0) else (sign * (abs(v_val) % abs(m_val)))

    @classmethod
    def ADDMOD(cls, l: int, r: int, m: int) -> int:
        """Modular addition: return (l + r) modulo m."""
        return 0 if (m == 0) else ((l + r) % m)

    @classmethod
    def MULMOD(cls, l: int, r: int, m: int) -> int:
        """Modular multiplication: return (l * r) modulo m."""
        return 0 if (m == 0) else ((l * r) % m)

    @classmethod
    def EXP(cls, b: int, e: int) -> int:
        """Exponentiation: return b to the power of e."""
        return b ** e

    @classmethod
    def SIGNEXTEND(cls, bits: int, value: int) -> int:
        """
        ref: https://github.com/ethereum/py-evm/blob/1af151ab218b905f4fdf7a285cbe14ebf094a7c4/eth/vm/logic/arithmetic.py
        Return v, but with the high bit of its b'th byte extended all the way
        to the most significant bit of the output.
        """
        if bits <= 31:
            testbit = bits * 8 + 7
            sign_bit = (1 << testbit)
            if value & sign_bit:
                result = value | (2**256 - sign_bit)
            else:
                result = value & (sign_bit - 1)
        else:
            result = value
        return result

    @classmethod
    def LT(cls, l: int, r: int) -> int:
        """Less-than comparison."""
        return 1 if (l < r) else 0

    @classmethod
    def GT(cls, l: int, r: int) -> int:
        """Greater-than comparison."""
        return 1 if (l > r) else 0

    @classmethod
    def SLT(cls, l: int, r: int) -> int:
        """Signed less-than comparison."""
        return 1 if (cls.twos_comp(l) < cls.twos_comp(r)) else 0

    @classmethod
    def SGT(cls, l: int, r: int) -> int:
        """Signed greater-than comparison."""
        return 1 if (cls.twos_comp(l) > cls.twos_comp(r)) else 0

    @classmethod
    def EQ(cls, l: int, r: int) -> int:
        """Equality comparison."""
        return 1 if (l == r) else 0

    @classmethod
    def ISZERO(cls, v: int) -> int:
        """1 if the input is zero, 0 otherwise."""
        return 1 if (v == 0) else 0

    @classmethod
    def AND(cls, l: int, r: int) -> int:
        """Bitwise AND."""
        return l & r

    @classmethod
    def OR(cls, l: int, r: int) -> int:
        """Bitwise OR."""
        return l | r

    @classmethod
    def XOR(cls, l: int, r: int) -> int:
        """Bitwise XOR."""
        return l ^ r

    @classmethod
    def NOT(cls, v: int) -> int:
        """Bitwise NOT."""
        return ~v

    @classmethod
    def BYTE(cls, b: int, v: int) -> int:
        """Return the b'th byte of v."""
        return (v >> ((cls.SIZE - b) * 8)) & 0xFF

    @classmethod
    def SHL(cls, b: int, v: int) -> int:
        """Bitwise shift left."""
        return v << b

    @classmethod
    def SHR(cls, b: int, v: int) -> int:
        """Bitwise shift right."""
        return v >> b

    @classmethod
    def SAR(cls, b: int, v: int) -> int:
        """Arithmetic shift right."""
        return cls.twos_comp(v) >> b

class VariableStack:
    """
    A stack that holds TAC variables.
    It is also a lattice, so meet and join are defined, and they operate
    element-wise from the top of the stack down.

    The stack is taken to be of infinite capacity, with empty slots extending
    indefinitely downwards. An empty stack slot is interpreted as a Variable
    with Bottom value, for the purposes of the lattice definition.
    Thus an empty stack would be this lattice's Bottom, and a stack "filled" with
    Top Variables would be its Top.
    We therefore have a bounded lattice, but we don't need the extra complexity
    associated with the BoundedLatticeElement class.
    """

    DEFAULT_MAX = 1024
    """
    The default maximum size of a variable stack.
    Any further elements pushed to a stack that is at its capacity are discarded.
    """

    DEFAULT_MIN_MAX_SIZE = 20
    """The minimum maximum size of a variable stack."""

    def __init__(self, state: t.Iterable[Variable] = None,
                 max_size=DEFAULT_MAX, min_max_size=DEFAULT_MIN_MAX_SIZE):
        self.value = [] if state is None else state

        self.empty_pops = 0
        """The number of times the stack was popped while empty."""

        self.min_max_size = min_max_size
        """
        The minimum size of this variable stack's maximum size.
        Taking the meet of two stacks produces a stack whose maximum size is the
        smaller of the two, but at least as large as this value.
        """

        self.max_size = max_size
        """
        The maximum size of this variable stack before it overflows.
        Pushing to a full stack has no effect.
        """
        self.set_max_size(max_size)

    def __iter__(self):
        """Iteration occurs from head of stack downwards."""
        return iter(reversed(self.value))

    def __str__(self):
        return "[{}]".format(", ".join(str(v) for v in self.value))

    def __len__(self):
        return len(self.value)

    def __eq__(self, other):
        return len(self) == len(other) and \
               all(v1 == v2 for v1, v2 in
                   zip(reversed(self.value), reversed(other.value)))

    def copy(self) -> 'VariableStack':
        """
        Produce a copy of this stack, without deep copying
        the variables it contains.
        """
        new_stack = type(self)()
        new_stack.value = copy.copy(self.value)
        new_stack.empty_pops = self.empty_pops
        new_stack.max_size = self.max_size
        return new_stack

    def peek(self, n: int = 0) -> Variable:
        """Return the n'th element from the top without popping anything."""
        if n >= len(self):
            raise ValueError("Stack size is zero")
        return self.value[-(n + 1)]

    def push(self, var: Variable) -> None:
        """Push a variable to the stack."""
        if len(self.value) < self.max_size:
            self.value.append(var)

    def pop(self) -> Variable:
        """
        Pop a variable off our symbolic stack if one exists, otherwise
        generate a variable from past the bottom.
        """
        if len(self.value):
            return self.value.pop()
        else:
            raise ValueError("Stack size is zero")

    def push_many(self, vs: t.Iterable[Variable]) -> None:
        """
        Push a sequence of elements onto the stack.
        Low index elements are pushed first.
        """
        for v in vs:
            self.push(v)

    def pop_many(self, n: int) -> t.List[Variable]:
        """
        Pop and return n items from the stack.
        First-popped elements inhabit low indices.
        """
        return [self.pop() for _ in range(n)]

    def dup(self, n: int) -> None:
        """Place a copy of stack[n-1] on the top of the stack."""
        items = self.pop_many(n)
        duplicated = [items[-1]] + items
        self.push_many(reversed(duplicated))

    def swap(self, n: int) -> None:
        """Swap stack[0] with stack[n]."""
        items = self.pop_many(n)
        swapped = [items[-1]] + items[1:-1] + [items[0]]
        self.push_many(reversed(swapped))

    def set_max_size(self, n: int) -> None:
        """Set this stack's maximum capacity."""
        new_size = max(self.min_max_size, n)
        self.max_size = new_size
        self.value = self.value[-new_size:]