import json
import re
import disco.common.structures.opcodes as Opcodes

sig2name = None

def get_name_by_signature(signature):
    global sig2name
    if sig2name is None:
        with open("./unique_signatures.json","r") as f:
            _sig2name = json.load(f)
            sig2name = {s:v[0].split("(")[0] for s,v in _sig2name.items()}
    
    return sig2name.get(signature, signature)

def get_language(evm_ops):
    is_solidity = True
    for i in range(len(evm_ops) - 3):
        evm_op1, evm_op2, evm_op3, evm_op4 = evm_ops[i],evm_ops[i+1],evm_ops[i+2],evm_ops[i+3]
        if evm_op1.opcode == Opcodes.PUSH1 and evm_op1.value == 0x0 \
            and evm_op2.opcode == Opcodes.CALLDATALOAD \
                and evm_op3.opcode.is_push() \
                    and evm_op4.opcode == Opcodes.MSTORE:
                        is_solidity = False
                        break
    
    return "Solidity" if is_solidity else "Vyper"

class SolidityVersion:
    UNKNOWN = 0
    FROM_0_4_17_TO_0_5_8 = 1
    FROM_0_5_9_TO_0_5_11 = 2
    FROM_0_5_12_TO_0_5_15 = 3
    FROM_0_4_17_TO_0_5_8_EXPERIMENTAL = 4
    FROM_0_5_9_TO_0_5_11_EXPERIMENTAL = 5
    FROM_0_5_12_TO_0_5_15_EXPERIMENTAL = 6
    FROM_0_6_0_TO_0_6_1 = 7
    FROM_0_6_2_TO_LATEST = 8

# reference: https://github.com/SeUniVr/EtherSolve/blob/768feac5b3b80b8a8268d52f943276d4b3add304/Core/src/main/java/parseTree/Contract.java#L72
def removeCompilationInfo(binary:str):
    version = SolidityVersion.UNKNOWN
    coreCode = ""
    metadata = ""
    remaining = ""
    ################################
    #      version solc-0.4.17     #
    ################################
    # 0xa1 
    # 0x65 'b' 'z' 'z' 'r' '0' 0x58 0x20 <32 bytes swarm hash> 
    # 0x00 0x29
    binary = binary.replace("0x","")
    # a165627a7a7230582014da8fca79564ff19e90c408efeb401e6eae54cc036aad052fb737ce95eb31130029
    if re.match("^[0-9a-f]*a165627a7a72305820[0-9a-f]{64}0029[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_4_17_TO_0_5_8
        coreCode, metadata, *remaining = re.split("(a165627a7a72305820[0-9a-f]{64}0029)", binary, maxsplit=3)

    ################################
    #      Experimental option     #
    ################################
    # Experimental option in Solidity due to ABIEncoderV2
    # example: a265627a7a723058201e1bfc77d507025cf70760b0848f01673dd1fb26af9d47b555da548df16224066c6578706572696d656e74616cf50037
    # 0xa2
    # 0x65 'b' 'z' 'z' 'r' '0' 0x58 0x20 <32 bytes swarm hash>
    # 0x6c 'e' 'x' 'p' 'e' 'r' 'i' 'm' 'e' 'n' 't' 'a' 'l' 0xf5
    # 0x00 0x37
    elif re.match("^[0-9a-f]*a265627a7a72305820[0-9a-f]{64}6c6578706572696d656e74616cf50037[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_4_17_TO_0_5_8_EXPERIMENTAL
        coreCode, metadata, *remaining = re.split("(a265627a7a72305820[0-9a-f]{64}6c6578706572696d656e74616cf50037)", binary, maxsplit=3)

    ################################
    #      version solc-0.5.9      #
    ################################
    # 0xa2
    # 0x65 'b' 'z' 'z' 'r' '0' 0x58 0x20 <32 bytes swarm hash>
    # 0x64 's' 'o' 'l' 'c' 0x43 <3 byte version encoding>
    # 0x00 0x32
    elif re.match("^[0-9a-f]*a265627a7a72305820[0-9a-f]{64}64736f6c6343[0-9a-f]{6}0032[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_5_9_TO_0_5_11
        coreCode, metadata, *remaining = re.split("(a265627a7a72305820[0-9a-f]{64}64736f6c6343[0-9a-f]{6}0032)", binary, maxsplit=3)
    
    ################################
    #      Experimental option     #
    ################################
    # Experimental option in Solidity due to ABIEncoderV2
    # example: a365627a7a7230582022316da6de015a68fad6ca8a732898f553832e95b48e9f39b85fe694b2264db26c6578706572696d656e74616cf564736f6c634300050a0040
    # 0xa3
    # 0x65 'b' 'z' 'z' 'r' '0' 0x58 0x20 <32 bytes swarm hash>
    # 0x6c 'e' 'x' 'p' 'e' 'r' 'i' 'm' 'e' 'n' 't' 'a' 'l' 0xf5
    # 0x64 's' 'o' 'l' 'c' 0x43 <3 byte version encoding>
    # 0x00 0x40
    elif re.match("^[0-9a-f]*a365627a7a72305820[0-9a-f]{64}6c6578706572696d656e74616cf564736f6c6343[0-9a-f]{6}0040[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_5_9_TO_0_5_11_EXPERIMENTAL
        coreCode, metadata, *remaining = re.split("(a365627a7a72305820[0-9a-f]{64}6c6578706572696d656e74616cf564736f6c6343[0-9a-f]{6}0040)", binary, maxsplit=3)

    ################################
    #      version solc-0.5.12     #
    ################################
    # 0xa2 
    # 0x65 'b' 'z' 'z' 'r' '1' 0x58 0x20 <32 bytes swarm hash> 
    # 0x64 's' 'o' 'l' 'c' 0x43 <3 byte version encoding> 
    # 0x00 0x32
    elif re.match("^[0-9a-f]*a265627a7a72315820[0-9a-f]{64}64736f6c6343[0-9a-f]{6}0032[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_5_12_TO_0_5_15
        coreCode, metadata, *remaining = re.split("(a265627a7a72315820[0-9a-f]{64}64736f6c6343[0-9a-f]{6}0032)", binary, maxsplit=3)
    
    ################################
    #      Experimental option     #
    ################################
    # Experimental option in Solidity due to ABIEncoderV2
    # example: a365627a7a7231582076f04f08ed9ab2d9078ead8a728e5e444700aed42abb0cd3bd94a1ae5612d38f6c6578706572696d656e74616cf564736f6c63430005110040
    # 0xa3
    # 0x65 'b' 'z' 'z' 'r' '1' 0x58 0x20 <32 bytes swarm hash>
    # 0x6c 'e' 'x' 'p' 'e' 'r' 'i' 'm' 'e' 'n' 't' 'a' 'l' 0xf5
    # 0x64 's' 'o' 'l' 'c' 0x43 <3 byte version encoding>
    # 0x00 0x40
    elif re.match("^[0-9a-f]*a365627a7a72315820[0-9a-f]{64}6c6578706572696d656e74616cf564736f6c6343[0-9a-f]{6}0040[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_5_12_TO_0_5_15_EXPERIMENTAL
        coreCode, metadata, *remaining = re.split("(a365627a7a72315820[0-9a-f]{64}6c6578706572696d656e74616cf564736f6c6343[0-9a-f]{6}0040)", binary, maxsplit=3)
    
    ################################
    #      version solc-0.6.0      #
    ################################
    # 0xa2 
    # 0x64 'i' 'p' 'f' 's' 0x58 0x22 <34 bytes IPFS hash> 
    # 0x64 's' 'o' 'l' 'c' 0x43 <3 byte version encoding> 
    # 0x00 0x32
    elif re.match("^[0-9a-f]*a264697066735822[0-9a-f]{68}64736f6c6343[0-9a-f]{6}0032[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_6_0_TO_0_6_1
        coreCode, metadata, *remaining = re.split("(a264697066735822[0-9a-f]{68}64736f6c6343[0-9a-f]{6}0032)", binary, maxsplit=3)
    
    ################################
    #      version solc-0.6.2      #
    ################################
    # 0xa2 
    # 0x64 'i' 'p' 'f' 's' 0x58 0x22 <34 bytes IPFS hash> 
    # 0x64 's' 'o' 'l' 'c' 0x43 <3 byte version encoding> 
    # 0x00 0x33
    elif re.match("^[0-9a-f]*a264697066735822[0-9a-f]{68}64736f6c6343[0-9a-f]{6}0033[0-9a-f]*$",binary):
        version = SolidityVersion.FROM_0_6_2_TO_LATEST
        coreCode, metadata, *remaining = re.split("(a264697066735822[0-9a-f]{68}64736f6c6343[0-9a-f]{6}0033)", binary, maxsplit=3)

    else:
        version = SolidityVersion.UNKNOWN
        coreCode = binary
        metadata = ""
        remaining = ""
    remaining = "".join(remaining) if len(remaining) > 0 else remaining

    return version, coreCode, metadata, remaining