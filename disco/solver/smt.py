# -*- coding:utf-8 -*-

import z3
from functools import partial

from disco.common.structures.tac_tree import OpTree

_UNI_VAR_TYPE = partial(z3.Int, ctx=None)
_UNI_CONST_TYPE = partial(z3.Int, ctx=None)

def _IS_UNI_VAR_TYPE(x): return isinstance(x, z3.z3.BitVecRef)


two_power = dict(zip(map(lambda x: 1 << x, (i for i in range(1, 257))), list(
    i for i in range(1, 257))))

USE_UNSIGNED = True

def universe_func(arg1, arg2, operator: str):
    """
        In z3, `Boolean` and `BitVec` are different types and cannot mix up when calculated. 
    """
    _table = {
        "AND": (lambda x, y: x & y, z3.And),
        "OR": (lambda x, y: x | y, z3.Or),
    }
    if isinstance(arg1, z3.z3.BitVecRef) or isinstance(arg2, z3.z3.BitVecRef):
        return _table[operator][0](arg1, arg2)
    elif isinstance(arg1, int) and isinstance(arg2, int):
        return _table[operator][0](arg1, arg2)
    else:
        return _table[operator][1](arg1, arg2)


def _div(x, y, sdiv=False):
    return ((x / y) if (not USE_UNSIGNED or sdiv) else z3.UDiv(x, y))


def _mul(x, y):
    if isinstance(y, int):
        if y in two_power:
            return (x << two_power[y])
    return x * y


def _is_if_expr(a: z3.z3.ExprRef):
    if _IS_UNI_VAR_TYPE(a):
        if (a.num_args() == 3 and repr(a).startswith("If") and isinstance(a.arg(0), z3.z3.BoolRef) and
                z3.eq(a.arg(1), _UNI_CONST_TYPE(1)) and z3.eq(a.arg(2), _UNI_CONST_TYPE(0))):
            return True
    return False


def _not(arg, return_ref: str = "value"):
    """
        calculate the NOT expression of an smt
        @param return_ref: "value" ==> return a value expression, e.g. If(a==0, 1, 0)
                            "bool" ==> return a bool expression, e.g. a==0 
    """
    if return_ref == "value":
        if isinstance(arg, z3.z3.BoolRef):
            return z3.Not(arg)
        elif _is_if_expr(arg):
            return z3.Not(arg.arg(0))
        else:
            return arg == 0
    elif return_ref == "bool":
        if isinstance(arg, z3.z3.BoolRef):
            return z3.Not(arg)
        elif _is_if_expr(arg):
            return z3.Not(arg.arg(0))
        else:
            return arg == 0
    else:
        assert 0

def smt_repr(smt):
    """
        remove the blank chars in str(`smt`)
    """
    ret = repr(smt)
    return ret.strip().replace(' ', '').replace('\n', '').replace('\t', '')

def safe_str(obj):
    """
        convert obj into a safe expression that could be used as z3 var name
    """
    if _IS_UNI_VAR_TYPE(obj):
        obj = z3.simplify(obj)
    ret = str(obj)
    return ret.replace(' ', '_').replace("\n", '_')

# Here, we only need to consider some part of operations
SMT_FUNC_TABLE = {
    "ADD": lambda x, y: x + y,
    "SUB": lambda x, y: x - y,
    "MOD": lambda x, y: (x % y),
    "DIV": lambda x, y: _div(x, y),
    "SDIV": lambda x, y: _div(x, y, sdiv=True),
    "MUL": lambda x, y: _mul(x, y),
    "GT": lambda x, y: x > y if not USE_UNSIGNED else z3.UGT(x, y),
    "SGT": lambda x, y: x > y,
    "LT": lambda x, y: x < y if not USE_UNSIGNED else z3.ULT(x, y),
    "SLT": lambda x, y: x < y,
    "EQ": lambda x, y: x == y,
    "ISZERO": _not,
    "NOT": _not
}


def smt_one_node(name: str, use_unsigned=False, *args):
    """
        given node name, return a value, i.e. an instance of `z3.z3.ArithRef` or `z3.z3.BitVecRef`
        @param `name` the current node name 
        @param `use_unsigned` boolean, if true, then will use (z3.UDiv, z3.ULT, z3.UGT) instead of (/, <, >)
        @param `replace_target` a List of (tuple of (old, new)), replacement will happened before create a var
        TODO: for now the `SMT_EXT_TABLE` is still naive. Expand this table when encounter new opcodes
    """
    global USE_UNSIGNED
    USE_UNSIGNED = use_unsigned
    if name in SMT_FUNC_TABLE:
        return SMT_FUNC_TABLE[name](*args), 0
    else:
        return _UNI_VAR_TYPE(f"{str(name)}_{'_'.join(str(arg) for arg in args)}"), 0
    
def smt_from_tree(tree:OpTree, target_name = None, use_unsigned = False, force_regen=True):
    if not force_regen and tree._smt is not None:
        return tree._smt
    
    if tree.alias_evm_variable:
        # if hasattr(tree.alias_evm_variable,'type'):# EVM State
        #     _var_name = tree.alias_evm_variable.details()
        # else:
        #     _var_name = str(tree.alias_evm_variable)

        _var_name = tree.details(with_counts=True, with_keys=True)
        tree._smt = (_UNI_VAR_TYPE(_var_name), 0 if tree.alias_evm_variable == target_name else 1)
    
    else:
        is_numeric, numeric_value = tree._is_numeric()
        if is_numeric:
            tree._smt = (numeric_value, 0)
                
        else:
            var_cnt = 0
            sons_smts = []
            for son in tree.sons:
                son_smt, _cnt = smt_from_tree(son, target_name, use_unsigned, force_regen)
                var_cnt += _cnt 
                sons_smts.append(son_smt)
            sons_smts = tuple(sons_smts)

            s, _cnt = smt_one_node(tree.name, use_unsigned, *sons_smts)
            tree._smt = (s, var_cnt + _cnt)
    
    return tree._smt