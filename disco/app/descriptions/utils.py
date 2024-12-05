import re
import string

from web3 import Web3

return_pattern = r'RETURN@0x[0-9a-fA-F]+'
from disco.app.descriptions.rules import OPTIMIZABLE_PHRASE


def optimize_phrase(s:str):
    for key, value in OPTIMIZABLE_PHRASE.items():
        if not s.startswith(key[:5]): 
            continue
        obj = re.search(key, s, re.IGNORECASE)
        if obj is None: 
            continue
        if r"%s" in value:        
            return value % obj.group(1)
        else:
            return value
    return s

def anti_capitalize(s:str):
    if len(s) > 1:
        if s[1].isupper():
            return s[0].upper() + s[1:]
        else:
            return s[0].lower() + s[1:]
    else:
        return s
    
def to_checksum_address(address):
    return Web3.to_checksum_address(address)
    
def find_return_pcs(args):
    matches = re.findall(return_pattern, args)

    return ["0x"+match.split('0x')[1] for match in matches]

def pretty_bignum(num):
    if type(num) != int:
        return num

    if num == 0x19457468657265756D205369676E6564204D6573736167653A0A333200000000:
        return "'\\x19Ethereum Signed Message:\\n32'"  # common, todo correct parsing of RLP encoding
        # https://ethereum.stackexchange.com/questions/33349/unable-to-reproduce-keccak256-hello-world-hash-within-evm
        # https://github.com/ethereum/go-ethereum/issues/14794
        # found in EtherDelta
    if num == 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:
        return "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    s = ""  # todo: mask?
    orig_num = num
    string_or_bytes = chr(num % 0x100) not in string.hexdigits and ord(chr(num % 0x100)) > 0
    if string_or_bytes:
        while num > 0:
            ch = chr(num % 0x100)
            if num % 0x100 != 0:
                s = ch + s
            num = num // 0x100
        if ord(s[-1])//2 == len(s[:-1]):
            return f"{s[:-1]}"
        else:
            return orig_num
    else:
        return f"{orig_num}"

if __name__ == "__main__":
    print(to_checksum_address("0x1"))