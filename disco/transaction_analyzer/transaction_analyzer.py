import os
import json
import logging

from disco.common.lifting.evm_path_parse import transform_from_evm_path
from disco.common.lifting.extractors.extract_semantic_units import extract_semantic_units
from disco.common.lifting.function_analyzer import analyze_functions
from disco.common.lifting.variables_analyzer import EVMVariableAnalyzer
from disco.common.structures.evm_path import EVMPath
from disco.transaction_analyzer.evm_trace_parser import EVMTraceParser
from disco.static_analyzer.evm_op_parse import blocks_from_ops
from disco.common.utils.web3_utils import generate_geth_traces_by_transaction_hash_json_rpc

logger = logging.getLogger(__name__)

def trace_to_evm_path(trace):
    """
    Convert execution trace to EVM path
    
    Args:
        trace: Raw execution trace from Geth
    Returns:
        EVMPath object or None if trace is invalid
    """
    if trace is None: 
        return None
        
    logger.info("Converting execution trace to EVM path...")
    _trace = remove_oov_instructions(trace)
    evm_ops = EVMTraceParser(_trace).parse()
    return EVMPath(blocks_from_ops(evm_ops), from_transaction=True)

def load_trace(trace_path):
    """
    Load execution trace from JSON file
    """
    if os.path.exists(trace_path):
        logger.info(f"Loading trace from {trace_path}")
        with open(trace_path,"r") as f:
            trace = json.load(f)
        return trace
    logger.warning(f"Trace file not found: {trace_path}")
    return None

def remove_oov_instructions(_trace):
    """
    Remove out-of-scope instructions from trace, keeping only depth 1 calls
    
    Verified by transactions:
    - 0x1a6206cd2075c95f73a82ca5b465cd1a543304968759779a8ae5e0b7ac7dc3e7 (0x2a0c0dbecc7e4d658f48e01e3fa353f44050c208)
    - 0xf07786df4ef348a56feaa636761557c54851aeab04e6554b2a62d4e070d7d48c (0x38Dc7c63c32c1e919D03F81D7e5b7e3CD3196E2d)
    """
    logger.info("Filtering trace to keep only depth 1 calls...")
    trace = []
    depth = 0
    may_switch = True
    
    for op in _trace:
        pc = int(op['pc'],16)
        opcode = op['op']
        
        # Track call depth
        if may_switch and pc == 0:
            depth += 1
        
        # Only keep instructions at depth 1
        if depth == 1:
            trace.append(op)
        
        # Handle call-type instructions
        if opcode in ['CALL','CALLCODE','DELEGATECALL','STATICCALL','CREATE','CREATE2']:
            may_switch = True
        else:
            if opcode in ['RETURN','STOP','REVERT','INVALID','SELFDESTRUCT']:
                depth -= 1
            may_switch = False
    
    return trace

# Path to custom trace collection script
customize_trace_path = "./common/static/customize_tracer.js"

def prepare_trace_from_tx_hash(tx_hash, address, working_dir:str="./"):
    """
    Get execution trace for a transaction using Geth's debug_traceTransaction
    """
    logger.info(f"Fetching trace for transaction {tx_hash}")
    return generate_geth_traces_by_transaction_hash_json_rpc([tx_hash], tracer=customize_trace_path)

def transaction_analyzer(transaction_hash, working_dir:str="./"):
    """
    Analyze a specific transaction by examining its execution trace
    
    Args:
        transaction_hash: Hash of the transaction to analyze
        working_dir: Directory containing analysis files
        loop_upper_bound: Maximum number of loop iterations to analyze
    """
    logger.info(f"Starting analysis of transaction {transaction_hash}")
    
    # Get and parse transaction trace
    trace = prepare_trace_from_tx_hash(transaction_hash)
    evm_path = trace_to_evm_path(trace)
    if evm_path:
        evm_path.transaction_hash = transaction_hash

    # Load previously saved analyzer state
    logger.info("Loading EVM analyzer state...")
    try:
        with open(f"{working_dir}/evm_analyzer.json","r") as f:
            dumped_evm_analyzer = json.load(f)
        evm_analyzer = EVMVariableAnalyzer.load(dumped_evm_analyzer)
    except Exception as e:
        logger.error(f"Failed to load EVM analyzer: {str(e)}")
        return

    # Analyze transaction if it completed successfully
    if len(evm_path.blocks) > 0 and evm_path.blocks[-1].last_op.opcode.name in ["RETURN","STOP"]:
        logger.info("Analyzing transaction execution path...")
                
        # Transform to TAC representation
        tac_path, _ = transform_from_evm_path(evm_path, debug=False)

        # Extract semantic units if state was modified
        evm_analyzer.reset_path_sensitive_args()
        if tac_path.has_state_affected_instructions:
            try:
                logger.info("Extracting semantic units from transaction...")
                semantic_units, opts = extract_semantic_units(evm_analyzer, tac_path)

                # Write semantic units to output
                with open(f"{working_dir}/transaction_semantic_units.json", "a") as f:
                    for su in semantic_units:
                        f.write(f"{json.dumps(su.dump())}\n")

            except Exception as e:
                logger.error(f"Error extracting semantic units: {str(e)}")
    else:
        logger.warning("Transaction did not complete successfully - skipping analysis")

if __name__ == "__main__":
    transaction_analyzer(transaction_hash="0xf4aa381185578a86cf3b490601a9521808018b72b6127b9514c9b0a35399c4d0")