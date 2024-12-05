import string

def pretty_bignum(num):
    if type(num) != int:
        return num

    if num == 0x19457468657265756D205369676E6564204D6573736167653A0A333200000000:
        return "'\\x19Ethereum Signed Message:\\n32'"  # common, todo correct parsing of RLP encoding
        # https://ethereum.stackexchange.com/questions/33349/unable-to-reproduce-keccak256-hello-world-hash-within-evm
        # https://github.com/ethereum/go-ethereum/issues/14794
        # found in EtherDelta
    s = ""  # todo: mask?
    orig_num = num
    while num > 0:
        ch = chr(num % 0x100)
        if ch not in (string.printable + string.whitespace) and num % 0x100 != 0:
            return orig_num
        if num % 0x100 != 0:
            s = ch + s
        num = num // 0x100

    return f"'{s}'"
