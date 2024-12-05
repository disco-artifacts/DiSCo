import json
import logging
import time
from typing import *

from disco.common.exceptions.MemoryHandlingExceptions import MemoryHandlingException
from disco.common.lifting.evm_path_parse import transform_from_evm_path
from disco.common.lifting.extractors.extract_semantic_units import extract_semantic_units
from disco.common.lifting.extractors.extract_state_variables import extract_state_variables
from disco.common.lifting.function_analyzer import analyze_functions
from disco.common.lifting.variables_analyzer import EVMVariableAnalyzer
from disco.common.structures.evm_path import EVMPath
from disco.common.utils.contract_utils import get_language
from disco.common.visualization.cfg_visualizer import CFGDotExporter
from disco.static_analyzer.evm_op_parse import build_cfg_from_ops, get_evm_ops_from_bytecode

logger = logging.getLogger(__name__)

def prepare_input_files(address:str, working_dir:str="./") -> Tuple[str, str]:
    """
    Read bytecode from hex file for the given contract address
    """
    logger.info(f"Reading bytecode from {working_dir}/{address}.hex")
    bytecode = ""
    with open(f"{working_dir}/{address}.hex", "r") as f:
        bytecode = f.read().strip()
    return bytecode

def static_analyzer(address, working_dir="./", loop_uncover_times:int=5):
    """
    Main function to perform static analysis on smart contract bytecode
    
    Args:
        address: Contract address
        working_dir: Directory containing input files and where output will be saved
        loop_uncover_times: Number of times to unroll loops during analysis
    """
    logger.info(f"Started static analysis at {time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))}")
    logger.info(f"Analyzing contract at address: {address}")

    # Get bytecode and parse EVM operations
    bytecode = prepare_input_files(address=address, working_dir=working_dir)
    evm_ops = get_evm_ops_from_bytecode(bytecode)
    language = get_language(evm_ops)
    logger.info(f"Contract language detected: {language}")

    # Build Control Flow Graph (CFG)
    logger.info("Building Control Flow Graph...")
    cfg = build_cfg_from_ops(evm_ops, loop_uncover_times=loop_uncover_times)

    # Transform EVM paths to Three-Address Code (TAC) paths
    logger.info("Transforming EVM paths to TAC paths...")
    tac_paths = []
    for evm_path in sorted(cfg.evm_paths, key=lambda x:len(x.blocks), reverse=False):
        try:
            _tac_paths, _ = transform_from_evm_path(evm_path, cfg=cfg)
            if _tac_paths is not None and len(_tac_paths) > 0:
                tac_paths.extend([tac_path for tac_path in _tac_paths if not tac_path.illegal])
        except (IndexError, MemoryHandlingException, Exception) as e:
            logger.debug(f"Error during path transformation: {str(e)}")
            continue

    logger.info("Updating CFG with new paths...")
    for tac_path in tac_paths:
        evm_path = EVMPath(tac_path.blocks)
        if not evm_path in cfg.evm_paths:
            cfg.evm_paths.append(evm_path)

    cfg.updatefalls()
    block_exits = cfg.resolveExitblock(cfg.evm_paths, loop_uncover_times+1)
    
    # Analyze functions in the contract
    logger.info("Analyzing contract functions...")
    functions = analyze_functions(tac_paths)
    
    # Initialize variable analyzer
    evm_analyzer = EVMVariableAnalyzer(language=language)
    
    # Extract state variables
    logger.info("Extracting state variables...")
    for tac_path in tac_paths:
        if not tac_path.has_state_affected_instructions:
            try:
                extract_state_variables(evm_analyzer, tac_path)
            except Exception as e:
                logger.debug(f"Error during state variable extraction: {str(e)}")
                continue

    # Extract semantic units
    logger.info("Extracting semantic units...")
    path_semantic_units = []
    dumped_sus = set()
    with open(f"{working_dir}/semantic_units.json","w") as f:
        for tac_path in sorted(tac_paths, key=lambda x:len(x.tac_blocks), reverse=False):
            evm_analyzer.reset_path_sensitive_args()
            if tac_path.has_state_affected_instructions:
                try:
                    semantic_units, _ = extract_semantic_units(evm_analyzer, tac_path, check_feasibility=True, exit_blocks=block_exits)
                    
                    path_semantic_units.append(semantic_units)
                    for su in semantic_units:
                        if su not in dumped_sus:
                            f.write(f"{json.dumps(su.dump())}\n")
                            dumped_sus.add(su)
                except Exception as e:
                    logger.debug(f"Error during semantic unit extraction: {str(e)}")
                    continue

    # Generate and export CFG visualization
    logger.info(f"Exporting CFG visualization to {working_dir}/cfg.html")
    CFGDotExporter(address, cfg, functions.values()).export(f"{working_dir}/cfg.html")
    
    logger.info("Static analysis completed successfully")
    
if __name__ == "__main__":
    static_analyzer(address="0xc6e5e9c6f4f3d1667df6086e91637cc7c64a13eb")