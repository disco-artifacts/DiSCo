{
	// traces: {txHash:"",ops:[]},

    ops: [],

    nextStackToPeek: 0,

    tohex: function(dict) {
        const hexValues = [];
        const dictLength = Object.keys(dict).length;
      
        for (let i = 0; i < dictLength; i++) {
          const value = dict[i.toString()] || 0;
          hexValues.push(Number(value).toString(16).padStart(2, "0"));
        }
      
        return hexValues.join("");
    },

    serialize: function() {
        return this.ops
                    .map(({ pc, op, values }) => `${pc}-${op}-${values.map(v => `(${v})`).join("-")}`)
                    .join(" ");
    },

	step: function(log, db) { 
        opinfo = {
            pc: log.getPC().toString(16),
            // op: log.op.toNumber().toString(16),
            op: log.op.toString(),
            values: [],
        };
        
        if(this.nextStackToPeek > 0){
            for(let i=0;i<this.nextStackToPeek;i++){
                this.ops[this.ops.length - 1]["values"].push(log.stack.peek(i).toString(16));
            }
            this.nextStackToPeek = 0;
        }

        switch(log.op.toString()) {
        case "SLOAD":
            var key = log.stack.peek(0).valueOf().toString(16);
            opinfo["values"].push(key);
            this.nextStackToPeek = 1;
            break
        case "SSTORE":
            var key = log.stack.peek(0).valueOf();
            var value = log.stack.peek(1).valueOf();
            opinfo["values"] = [...opinfo["values"],key.toString(16),value.toString(16)];
            break
        case "SHA3": case "KECCAK256":
            var offset = log.stack.peek(0).valueOf();
            var length = log.stack.peek(1).valueOf();
            var sha3key = this.tohex(log.memory.slice(offset, offset + length));
            opinfo["values"] = [...opinfo["values"],offset.toString(16),length.toString(16),sha3key];
            break
        case "MLOAD":
            var offset = log.stack.peek(0).valueOf();
            opinfo["values"].push(offset.toString(16));
            this.nextStackToPeek = 1;
            break;
        case "MSTORE": case "MSTORE8":
            var offset = log.stack.peek(0).valueOf();
            var value = log.stack.peek(1).valueOf();
            opinfo["values"] = [...opinfo["values"],offset.toString(16),value.toString(16)];
            break
        case "CALL": case "CALLCODE":
            var gas = log.stack.peek(0).valueOf();
            var addr = log.stack.peek(1).valueOf();
            var value = log.stack.peek(2).valueOf();
            var argsOffset = log.stack.peek(3).valueOf();
            var argsLength = log.stack.peek(4).valueOf();
            var args = this.tohex(log.memory.slice(argsOffset, argsOffset + argsLength));
            opinfo["values"] = [...opinfo["values"],gas.toString(16),addr.toString(16),value.toString(16),argsOffset.toString(16),argsLength.toString(16),args];
            break
        case "DELEGATECALL": case "STATICCALL":
            var gas = log.stack.peek(0).valueOf();
            var addr = log.stack.peek(1).valueOf();
            var argsOffset = log.stack.peek(2).valueOf();
            var argsLength = log.stack.peek(3).valueOf();
            var args = this.tohex(log.memory.slice(argsOffset, argsOffset + argsLength));
            opinfo["values"] = [...opinfo["values"],gas.toString(16),addr.toString(16),argsOffset.toString(16),argsLength.toString(16),args];
            break
        case "CREATE": case "CREATE2":
            var value = log.stack.peek(0).valueOf();
            var offset = log.stack.peek(1).valueOf();
            var length = log.stack.peek(2).valueOf();
            var args = this.tohex(log.memory.slice(offset, offset + length));
            opinfo["values"] = [...opinfo["values"],value.toString(16),offset.toString(16),length.toString(16),args];
            break
        case "SELFDESTRUCT":
            var addr = log.stack.peek(0).valueOf();
            opinfo["values"].push(addr.toString(16));
            break
        }
        if(log.op.isPush()) {
            this.nextStackToPeek = 1;
        }
        this.ops.push(opinfo);
     },

	fault: function(log, db) { },

	result: function(ctx, db) { 
        return this.ops
        // return this.serialize()
        // return {
        //     "ops":this.ops,
        //     "txHash":ctx.txHash,
        // }
    }
}