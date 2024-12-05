import math

SHA3_MAPPING_PATH = "./sha3_mappings.json"   

STATE_AFFECTED_INSTRUCTIONS = {
    "55":"SSTORE",
    "f0":"CREATE",
    "f5":"CREATE2",
    "f1":"CALL",
    "f2":"CALLCODE",
    "f4":"DELEGATECALL",
    "fa":"STATICCALL",
    "ff":"SELFDESTRUCT",
    "-1":"MISSING"
}

def style_transfer(content, style):
    """
        Given a style(one of plain, markdown, html), add a wrapper
    """
    if style == "plain":
        return content
    elif style == "markdown":
        return "`%s`" % content
    elif style == "html":
        return '<span class="gv">%s</span>' % content
    else:
        assert 0, "style_transfer: Unknown style:" + str(style)
        
def is_numberic(num:str) -> bool:
    """whether the num is numberic, `true` iff num starts with `0x`"""
    if num.startswith("0x"):
        return True
    else:
        return False
    
def numberic(num:str) -> int:
    """num is hex number and startswith 0x, return decimal number"""
    assert num.startswith("0x")
    return int(num,16)

def hex2str(num:str) -> str:
    """num is hex number and startswith 0x, strip the first `0x`"""
    assert num.startswith("0x")
    return num[2:]

def compute_offset(num:str) -> int:
    """Returns the log(num,2)
    
    Arguments:
        num: str, number in hex.
    """
    num_int = int(num,16)
    pow = int(math.log(num_int,2))
    if 2**pow == num_int:
        return pow//4
    else:
        return -1