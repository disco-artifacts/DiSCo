from typing import *
from disco.common.structures.evm_variable import EVMState

import disco.solver.smt as smt
import z3
from disco.common.structures.tac_tree import OpTree

class Checker:
    def __init__(self) -> None:
        self.infeasible_path_pres = set()
        self.tree_smt_mapping = dict()

class PathChecker(Checker):
    def __init__(self) -> None:
        """
            This class is a collection of functions that used for checking feasibility
        """
        super().__init__()

        self.reset()
    
    def add_constraint(self, condTree:OpTree):
        smt_tree = smt.smt_from_tree(condTree)[0]
        self.push_to_solver(smt_tree)
        self.after_add_constraints = True
        
    def add_sstore(self, key: EVMState, value: OpTree):
        new_var = smt._UNI_VAR_TYPE(f"{key.details(with_counts=True, with_keys=True)}")
        self.push_to_solver(new_var == smt.smt_from_tree(value)[0])

    def check(self, current_path_pres:str=""):
        sat = 1
        if current_path_pres in self.infeasible_path_pres:
            sat = -1
        else:
            r = self.solver.check().r
            if r == -1:
                self.infeasible_path_pres.add(current_path_pres)
                return -1
            else:
                return 1

        return sat

    def reset(self):
        # setup solver
        self.solver = z3.Solver()
        self.pushed_exp = set()
        self.solver.set("timeout", 1000)

        self.after_add_constraints = False

        # initial background knowledge
        self.push_background_knowledge()

    def push_type_constraint(self, type_name:str, var_name:str):
        if self.type_might_unsigned(type_name):
            if type_name == "address":
                self.push_to_solver(smt._UNI_VAR_TYPE(var_name) > 0)
            else:
                self.push_to_solver(smt._UNI_VAR_TYPE(var_name) >= 0)

    def push_to_solver(self, constraint: z3.ExprRef):
        e = self.bool_ref_wrapper(constraint)
        r = smt.smt_repr(e)
        if r not in self.pushed_exp:
            self.pushed_exp.add(r)
            self.solver.add(e)

    def push_background_knowledge(self):
        # pass
        # self.push_to_solver(smt._UNI_VAR_TYPE("CALLER") != 0)
        self.push_to_solver(smt._UNI_VAR_TYPE("TIMESTAMP") > 0)

    @staticmethod
    def type_might_unsigned(type_name:str):
        """
            ~~ The following type name might be unsigned: 
                1. Anything starts with "uint"
                2. address
                3. bytes?
                4. user_define_enum ~~
            Only `int` is signed 
        """
        if type_name.startswith("int"):
            return False
        return True

    @staticmethod
    def bool_ref_wrapper(a:z3.ExprRef):
        """
            Given a z3 expression, return the BoolRef of the expression
        """
        if smt._is_if_expr(a):
            # IF(BOOL_EXPR, 1, 0)  ===> BOOL_EXPR
            return a.arg(0)
        if not isinstance(a, z3.z3.BoolRef):
            return a != 0
        else:
            return a