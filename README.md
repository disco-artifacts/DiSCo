This work is pending a "Double-Anonymous" submission, so we are unable to disclose further details to maintain the submission rules.

---
![](https://img.shields.io/badge/language-python-brightgreen.svg?style=plastic) 
![](https://img.shields.io/badge/version-v0.1-brightgreen.svg?style=plastic)

## Installation

### Prerequisites
- Python 3.7+
- Access to an Ethereum node (for transaction analysis)
- GraphViz (for visualization)

### Setup
1. Clone the repository:
```bash
git clone https://github.com/disco-artifacts/DiSCo.git
cd disco
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage Guide

### 1. Static Analysis
Analyze the contract's bytecode to extract semantic units:

> TL;DR [extract_semantic_units.py](./disco/common/lifting/extractors/extract_semantic_units.py) for extracting `semantic units` (aka. conditional behaviors)

```bash
python disco static_analysis --address <contract_address>
```

Parameters:
- `--address`: The Ethereum address of the contract to analyze
- `--working-dir` (optional): Working directory for output files (default: "./")

Output:
- Control Flow Graph (CFG) visualization
- Semantic units extracted from static analysis
- State variable information

### 2. Transaction Analysis (Optional)
To analyze the contract's constructor and other transactions.

> TL;DR [transaction_analyzer.py](./disco/transaction_analyzer/transaction_analyzer.py) for analyzing constructor

#### 2.1 Configure Ethereum Node
Set your Ethereum node endpoint in the [configuration](./disco/common/utils/web3_utils.py):
```bash
ENDPOINT_URI="XX"
```

#### 2.2 Analyze Transactions
```bash
python disco transaction_analysis --tx <transaction_hash>
```

Parameters:
- `--tx`: Transaction hash to analyze
- `--working-dir` (optional): Working directory for output files

Output:
- Transaction execution trace
- Additional semantic units in this transaction

### 3. Graph Construction
Build a semantic graph representation of the contract:

```bash
python disco build_graph --address <contract_address>
```

Parameters:
- `--address`: Contract address
- `--visualization` (optional): Generate visual representation of the graph
- `--force-recon` (optional): Force reconstruction of existing graph

Output:
- JSON representation of the semantic graph
- Graph visualization (if enabled)

### 4. Description Generation
Generate natural language descriptions of contracts:

```bash
python disco description_generation --address <contract_address>
```

Output:
- Natural language descriptions of contract functions

### 5. Source Code Generation
Generate decompiled source code:

```bash
python disco code_generation --address <contract_address>
```

Output:
- Decompiled Solidity source code
- Function signatures and documentation

## Project Structure
```
disco/
├── app/                    # Main application logic (e.g., graph construction and NL generation)
├── common/                 # Shared utilities and structures
├── static_analyzer/        # Static analysis components
├── solver/                 # Satisfiability analysis components
├── transaction_analyzer/   # Transaction analysis components
└── requirements.txt        # Project dependencies
```

## References & Acknowledgements

This project builds upon several excellent open-source projects:

1. [Ethereum-etl](https://github.com/blockchain-etl/ethereum-etl)
   - Python scripts for ETL (extract, transform and load) jobs for Ethereum data
   - Used for blockchain data extraction

2. [Vandal](https://github.com/usyd-blockchain/vandal)
   - Static program analysis framework for Ethereum smart contracts
   - Provides foundational analysis techniques

3. [OpenHGNN](https://github.com/BUPT-GAMMA/OpenHGNN)
   - Open Source Toolkit for Heterogeneous Graph Neural Networks
   - Used for graph-based analysis

4. [DGL](https://github.com/dmlc/dgl)
   - Deep Graph Library
   - Provides graph neural network capabilities
