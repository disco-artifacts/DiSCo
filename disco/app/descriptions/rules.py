OPTIMIZABLE_PHRASE = {
    r"the money transferred to contract equals to (.*)":"sending %s ether to contract", # callvalue == xxxx 
    r"the money transferred to contract is not smaller than (.*)":"sending at least %s ether to contract", # callvalue >= xx
    r"the money transferred to contract is greater than (.*)":"sending at least %s ether to contract", # callvalue >= xx
    r"current time is not greater than (.*)":"before %s", # timestamp <= xxx 
    r"current time is smaller than (.*)":"before %s", # timestamp < xxx 
    r"current time is greater than (.*)":"after %s", # timestamp > xxx 
    r"current time is not smaller than (.*)":"after %s", # timestamp >= xxx 
}

PROPERTY_DESCRIPTIONS = {
    # no operator
    "TIMESTAMP": "current time",
    "CALLVALUE": "the ether just received (i.e., msg.value)",
    "CALLER":"caller",
    "CREATE":"the contract just created",
    "ADDRESS":"the address of this contract",
    "NUMBER":"the current block's number"
}

OP_DESCRIPTIONS = {
    # binary op
    "AND": "%s and %s",
    "OR": "%s or %s",
    # "XOR": "%s does not equal to %s",
    "XOR": "%s != %s",
    "ADD": "(%s+%s)",
    "SUB": "(%s-%s)",
    "DIV": "(%s/%s)",
    "MUL": "(%s*%s)",
    "GT": "%s > %s",
    "LT": "%s < %s",
    "SGT": "%s > %s",
    "SLT": "%s < %s",
    "EQ": "%s == %s",

    "ISZERO": "%s == 0",
    "BALANCE":"the balance of %s" 
}

INDEX_MAPPING = {
    1:"first",
    2:"second",
    3:"third",
    4:"fourth",
    5:"fifth",
    6:"sixth"
}