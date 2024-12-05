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

"""evm_cfg.py: Classes for processing disasm output and building a CFG"""

from collections import defaultdict
from typing import *

import networkx as nx
import disco.common.structures.base.basic_cfg as basic_cfg
import disco.common.structures.evm_path as EVMPath
import disco.common.structures.opcodes as opcodes
import disco.common.structures.evm_stack as Stack
from disco.common.exceptions.StackHandlingExceptions import StackSizeOverflow

class EVMOp:
    """
    Represents a single EVM operation.
    """

    def __init__(self, pc: int, opcode: opcodes.OpCode, value: int = None, values: int=None):
        """
        Create a new EVMOp object from the given params which should correspond to
        disasm output.

        Args:
          pc: program counter of this operation
          opcode: VM operation code
          value: constant int value or default None in case of non-PUSH operations

        Each line of disasm output is structured as follows:

        PC <spaces> OPCODE <spaces> => CONSTANT

        where:
          - PC is the program counter
          - OPCODE is an object representing an EVM instruction code
          - CONSTANT is a hexadecimal value with 0x notational prefix
          - <spaces> is a variable number of spaces

        For instructions with no hard-coded constant data (i.e. non-PUSH
        instructions), the disasm output only includes PC and OPCODE; i.e.

        PC <spaces> OPCODE

        If None is passed to the value parameter, the instruction is assumed to
        contain no CONSTANT (as in the second example above).
        """

        self.pc = pc
        """Program counter of this operation"""

        self.opcode = opcode
        """VM operation code"""

        self.value = value
        """Constant int value or None"""

        # updates
        self.values = [] if values is None else values
        """Support for traceop"""

        self.block = None
        """EVMBasicBlock object to which this line belongs"""

    def __str__(self):
        if self.value is None:
            return "{0} {1}".format(hex(self.pc), self.opcode)
        else:
            return "{0} {1} {2}".format(hex(self.pc), self.opcode, hex(self.value))

    def __repr__(self):
        return "<{0} object {1}: {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        )
        
    @classmethod
    def convert_jump_to_throw(cls, op):
        """
        Given a jump, convert it to a throw, preserving the condition var if JUMPI.
        Otherwise, return the given operation unchanged.
        """
        if op.opcode not in [opcodes.JUMP, opcodes.JUMPI]:
            return op
        elif op.opcode == opcodes.JUMP:
            op.opcode = opcodes.THROW
            return op
        elif op.opcode == opcodes.JUMPI:
            op.opcode = opcodes.THROWI
            return op

class EVMBasicBlock(basic_cfg.BasicBlock):
    """
    Represents a single basic block in the control flow graph (CFG), including
    its parent and child nodes in the graph structure.
    """

    def __init__(self, entry: int = None, exit: int = None,
                 evm_ops: List['EVMOp'] = None):
        """
        Creates a new basic block containing operations between the
        specified entry and exit instruction counters (inclusive).

        Args:
          entry: block entry point program counter
          exit: block exit point program counter
          evm_ops: a sequence of operations that constitute this BasicBlock's code. Default empty.
        """
        super().__init__(entry, exit)

        self.evm_ops = evm_ops if evm_ops is not None else []
        """List of EVMOps contained within this EVMBasicBlock"""

        self.fallthrough = None
        """
        The block that this one falls through to on the false branch
        of a JUMPI, if it exists. This should already appear in self.succs;
        this just distinguishes which one is the false branch.
        """
        # TODO: maybe not vital, but this should interact properly with procedure cloning

    def __str__(self):
        """Returns a string representation of this block and all ops in it."""
        super_str = super().__str__()
        op_seq = "\n".join(str(op) for op in self.evm_ops)
        return "\n".join([super_str, self._STR_SEP, op_seq])

    def __hash__(self) -> int:
        return hash(self.ident())

    def __eq__(self, o: object) -> bool:
        return hash(self) == hash(o)

    def __len__(self) -> int:
        return len(self.evm_ops)

    def split(self, entry: int) -> 'EVMBasicBlock':
        """
        Splits current block into a new block, starting at the specified
        entry op index. Returns a new EVMBasicBlock with no preds or succs.

        Args:
          entry: unique index of EVMOp from which the block should be split. The
            EVMOp at this index will become the first EVMOp of the new BasicBlock.
        """
        # Create the new block.
        new = type(self)(entry, self.exit, self.evm_ops[entry - self.entry:])

        # Update the current node.
        self.exit = entry - 1
        self.evm_ops = self.evm_ops[:entry - self.entry]

        # Update the block pointer in each line object
        self.__update_evmop_refs()
        new.__update_evmop_refs()

        return new

    def __update_evmop_refs(self):
        # Update references back to parent block for each opcode
        # This needs to be done when a block is split
        for op in self.evm_ops:
            op.block = self
    
    def ident(self) -> str:
        """
        Returns this block's unique identifier, which is its entry value.

        Raises:
          ValueError if the block's entry is None.
        """
        if self.entry is None:
            raise ValueError("Can't compute ident() for block with unknown entry")
        # return hex(self.entry) + self.ident_suffix
        return hex(self.evm_ops[0].pc)
    
    @property
    def last_op(self) -> EVMOp:
        return self.evm_ops[-1]
    
    
    def __repr__(self) -> str:
        return "<{0} object {1}: {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.ident()
        )
        
class EVMGraph(basic_cfg.ControlFlowGraph):
    """
    A control flow graph holding EVMBasicBlocks and edges between them.
    """
    LOOP_DEPTH:int = 256
    """The upper bound of path blocks"""
    LOOP_UNCOVER_TIMES:int = 16
    """The upper bound of duplicated edges in a path"""
    BLOCK_LIMIT:int = 200000
    """The upper bound of block count for one time analysis"""
    PATH_LIMIT:int = float("inf")
    """PATH count limit for one time analysis"""

    def __init__(self, evm_blocks:Iterable[EVMBasicBlock], evm_paths:Iterable[EVMPath.EVMPath]=None):
        """
        Construct a EVM control flow graph from a given sequence of EVMBasicBlocks.

        Args:
            evm_blocks: an iterable of EVMBasicBlocks in the EVMGraph.
        """
        super().__init__()
        self.blocks:List[EVMBasicBlock] = evm_blocks
        self.mapping = {}
        """Mapping from block ident(str) to block"""

        self.last_block = None
        for b in self.blocks:
            b.cfg = self
            self.mapping[b.ident()] = b
            if self.last_block is None or b.evm_ops[0].pc > self.last_block.evm_ops[0].pc:
                self.last_block = b
        
        self.root = next((b for b in self.blocks if b.entry == 0), None)
        """
        The root block of this CFG.
        The entry point will always be at index 0, if it exists.
        """
        self.evm_paths:List[EVMPath.EVMPath] = [] if evm_paths is None else evm_paths
        
        self.jump_dests = {block.ident():block for block in evm_blocks if block.evm_ops and len(block.evm_ops) > 0 and block.evm_ops[0].opcode == opcodes.JUMPDEST}

    def resolveStaticEdges(self):
        """Resolve some block edges"""
        for block in self.blocks:
            last_op:EVMOp = block.last_op
            # JUMP
            if last_op.opcode == opcodes.JUMP and len(block) > 1:
                second_last_op = block.evm_ops[-2]
                if second_last_op.opcode.is_push():
                    dest = second_last_op.value
                    dest_block = self.mapping.get(hex(dest), None) if dest is not None else None
                    # the destination should start with `JUMPDEST`
                    if dest_block is not None and dest_block.evm_ops[0].opcode == opcodes.JUMPDEST:
                        self.add_edge(block, dest_block)
                    # else:
                    #     block.evm_ops[-1] = EVMOp.convert_jump_to_throw(last_op)

            # JUMPI
            elif last_op.opcode == opcodes.JUMPI and len(block) > 1:
                if hex(last_op.pc + 1) in self.mapping:
                    fallthrough = self.mapping[hex(last_op.pc + 1)]
                    self.add_edge(block, fallthrough)
                    block.fallthrough = fallthrough
                
                second_last_op = block.evm_ops[-2]
                if second_last_op.opcode.is_push():
                    dest = second_last_op.value
                    dest_block = self.mapping.get(hex(dest), None) if dest is not None else None
                    # the destination should start with `JUMPDEST`
                    if dest_block is not None and dest_block.evm_ops[0].opcode == opcodes.JUMPDEST:
                        self.add_edge(block, dest_block)
                    # else:
                    #     block.evm_ops[-1] = EVMOp.convert_jump_to_throw(last_op)

            # Other delimiters
            elif last_op.opcode.possibly_halts() or last_op.opcode in (opcodes.JUMP, opcodes.JUMPI):
                continue
            # Exclude the last block which has no sequent
            elif block == self.last_block:
                continue
            # Else
            else:
                # common operation, add the next
                offset = 1
                if last_op.opcode.is_push():
                    offset += last_op.opcode.code - opcodes.PUSH1.code + 1
                if hex(last_op.pc + offset) in self.mapping:
                    fallthrough = self.mapping[hex(last_op.pc + offset)]
                    self.add_edge(block, fallthrough)
                    block.fallthrough = fallthrough
    
    def resolveDynamicEdges(self, loop_uncover_times:int=LOOP_UNCOVER_TIMES, block_limit:int=BLOCK_LIMIT, loop_depth:int=LOOP_DEPTH, path_limit=PATH_LIMIT):
        blockCount = 0
        visited:Set[Tuple[str, str, Stack.EVMStack]] = set()
        current = self.root
        stack = Stack.EVMStack()

        dfs_depth = 0
        queue:List[Tuple[EVMPath.EVMPath,int]] = list()

        # stack is after-exec current state
        path = EVMPath.EVMPath(blocks=[current],stacks=[stack])
        queue.append((path, dfs_depth))

        stackOversize = 0
        blockLimitExceed = 0
        loopdepthExceed = 0
        executionError = 0

        while len(queue) > 0:
            # pop the last element
            # current, stack, dfs_depth, path = queue.pop()
            # path, dfs_depth = queue.pop()
            path, dfs_depth = queue.pop(0)

            current = path.blocks[-1]

            stack = path.stacks[-1]

            # except the last one
            try:
                for op in current.evm_ops[:-1]:
                    stack.executeEVMOp(op)
            except StackSizeOverflow as e:
                # raise e
                stackOversize += 1
                continue
            except Exception as e:
                # raise e
                executionError += 1
                continue

            last_op = current.last_op
            dest = None

            if last_op.opcode == opcodes.JUMP:
                dest = stack.peek()
                dest_block = self.mapping.get(hex(dest), None) if dest is not None else None
                if dest_block is not None and dest_block.evm_ops[0].opcode == opcodes.JUMPDEST:
                    self.add_edge(current, dest_block)
            
            blockCount += 1

            if blockCount >= block_limit:
                blockLimitExceed += 1
                break
                        
            # execute the last opcode
            try:
                stack.executeEVMOp(last_op)
            except StackSizeOverflow as e:
                stackOversize += 1
                continue
            except Exception as e:
                # raise e
                executionError += 1
                continue

            if len([b for b in current.succs if not b.last_op.opcode.abnormal_halts()]) == 0:
                self.evm_paths.append(path)

            if dfs_depth < loop_depth:
                if not last_op.opcode == opcodes.JUMP:
                    for suc in current.succs:
                        if not suc.last_op.opcode.abnormal_halts():
                            edge = (current.ident(), suc.ident(), stack)
                            if not edge in visited:
                                visited.add(edge)
                                path_copy = path.copy()
                                allowed = path_copy.add_element(suc, stack.copy(), loop_uncover_times)
                                if allowed:
                                    queue.append((path_copy, dfs_depth+1))

                elif dest is not None:
                    edge = (current.ident(), hex(dest), stack)
                    if not edge in visited:
                        visited.add(edge)
                        nextdest = self.mapping.get(hex(dest), None)
                        if nextdest is not None:
                            path_copy = path.copy()
                            allowed = path_copy.add_element(nextdest, stack.copy(), loop_uncover_times)
                            if allowed:
                                queue.append((path_copy, dfs_depth+1))
            else:
                loopdepthExceed += 1

    def updatefalls(self):
        for block in self.blocks:
            for suc in block.succs:
                if suc.has_invalid:
                    block.fallto_invalid = True
                    block.next_invalid_block = suc
                
                if suc.has_revert:
                    block.fallto_revert = True
                    block.next_revert_block = suc

    def resolveExitblock(self, evm_paths, upper_bound:int=-1):
        exit_blocks_wait_list = defaultdict(set)
        exit_blocks = dict()
        for evm_path in sorted(evm_paths, key=lambda x:len(x.blocks), reverse=False):
            for idx, evm_block in enumerate(evm_path):
                if evm_block.last_op.opcode == opcodes.JUMPI:
                    if evm_block.fallto_revert or evm_block.fallto_revert:
                        exit_blocks[evm_block.ident()] = "stay"
                        continue
                    succ = ""
                    for block in evm_path.blocks[idx+1:min(idx+20,len(evm_path.blocks))]:
                        if block.ident() == evm_block.ident():
                            exit_blocks[evm_block.ident()] = evm_block.ident()
                            break
                        succ += block.ident() + "->"
                    succ = succ.rstrip("->")
                    exit_blocks_wait_list[evm_block.ident()].add(succ)

        for jump_ident in exit_blocks_wait_list:
            set_exits = [set(lst.split("->")) for lst in exit_blocks_wait_list[jump_ident]]
            if len(set_exits) < 2: continue
            intersections = set.intersection(*set_exits)
            if len(intersections) > 0:
                for intersection in list(exit_blocks_wait_list[jump_ident])[0].split("->"):
                    if intersection in intersections: break
            elif len(intersections) == 1:
                intersection = intersections[0]
            else:
                continue
            exit_blocks[jump_ident] = intersection

        return exit_blocks
                    
    def edge_list(self) -> Iterable[Tuple[EVMBasicBlock, EVMBasicBlock]]:
        """
        Returns:
          a list of the CFG's edges, with each edge in the form
          `(pred, succ)` where pred and succ are object references.
        """
        return [(p, s) for p in self.blocks for s in p.succs]

    def __iter__(self):
        for block in self.blocks:
            yield block

    def nx_graph(self) -> nx.DiGraph:
        """
        Return a networkx representation of this CFG.
        Nodes are labelled by their corresponding block's identifier.
        """
        g = nx.DiGraph()
        g.add_nodes_from(b.ident() for b in self.blocks)
        g.add_edges_from((p.ident(), s.ident()) for p, s in self.edge_list())
        return g