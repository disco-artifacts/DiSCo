# BSD 3-Clause License
#
# Copyright (c) 2016, 2017, The University of Sydney. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""exporter.py: abstract classes for exporting decompiler state"""
import disco.common.structures.opcodes as Opcodes
import disco.common.structures.evm_cfg as cfg

class CFGDotExporter:
    """
    Generates a dot file for drawing a pretty picture of the given contract.

    Args:
      contract: the contract to be drawn.
    """

    def __init__(self, address, cfg: cfg.EVMGraph, functions):
        self.address = address
        self.graph = cfg
    
        self.functions = functions
    
    def export(self, out_filename: str = "cfg.dot"):
        """
        Export the CFG to a dot file.

        Certain blocks will have coloured outlines:
          Blue: ends in a STOP or RETURN operation;

        A node with a red fill indicates that its stack size is large.

        Args:
          out_filename: path to the file where dot output should be written.
                        If the file extension is a supported image format,
                        attempt to generate an image using the `dot` program,
                        if it is in the user's `$PATH`.
        """
        import networkx as nx

        graph = self.graph
        blocks = graph.blocks

        G = graph.nx_graph()

        # Colour-code the graph.
        normalEnds = {block.ident(): "blue" for block in blocks if block.last_op.opcode.normal_halts()}
        abnormalEnds = {block.ident(): "red" for block in blocks if block.last_op.opcode.abnormal_halts()}
        
        # if an exception, upgrage networkx
        nx.set_node_attributes(G, {**normalEnds,**abnormalEnds}, "color")

        # if condition, diamond
        # if has sload or sstore, bold

        bold_dict = {block.ident():"bold" if any(op.opcode in [Opcodes.SSTORE,
                                   Opcodes.CALL, Opcodes.CALLCODE, Opcodes.DELEGATECALL, Opcodes.STATICCALL,
                                   Opcodes.CREATE, Opcodes.CREATE2,
                                   Opcodes.SELFDESTRUCT] for op in block.evm_ops) else "solid"
                    for block in blocks}
        nx.set_node_attributes(G, bold_dict,  "style")

        # normalShape = {block.ident():"doublecircle" for block in blocks if any(ins.opcode in (Opcodes.SSTORE,Opcodes.SLOAD) for ins in block.evm_ops)}
        # shape_dict = {block.ident(): "diamond" if any(op.opcode == Opcodes.SLOAD or op.opcode == Opcodes.SSTORE for op in block.evm_ops) else "ellipse" 
        #             for block in blocks}

        # shape_dict = {block.ident(): "diamond" if any(op.opcode == Opcodes.JUMPI for op in block.evm_ops) else "ellipse" 
        #             for block in blocks}
        # nx.set_node_attributes(G, "shape", shape_dict)


        # Annotate each node with its basic block's internal data for later display
        # if rendered in html.
        nx.set_node_attributes(G, {block.ident(): block.ident()
                                         for block in blocks}, "id")

        block_strings = {}
        for block in blocks:
            block_string = str(block)
            block_strings[block.ident()] = block_string
        nx.set_node_attributes(G, block_strings, "tooltip")

        # Write non-dot files using pydot and Graphviz
        if "." in out_filename and not out_filename.endswith(".dot"):
            # HTML format
            pdG = nx.nx_pydot.to_pydot(G)
            extension = out_filename.split(".")[-1]

            # If we're producing an html file, write a temporary svg to build it from
            # and then delete it.
            if extension == "html":
                html = svg_to_html(self.address, pdG.create_svg().decode("utf-8"), functions=self.functions)
                if not out_filename.endswith(".html"):
                    out_filename += ".html"
                with open(out_filename, 'w') as page:
                    page.write(html)
            else:
                pdG.set_margin(0)
                pdG.write(out_filename, format=extension)

        # Otherwise, write a regular dot file using pydot
        else:
            try:
                if out_filename == "":
                    out_filename = "cfg.html"
                nx.nx_pydot.write_dot(G, out_filename)
            except:
                if out_filename == "":
                    out_filename = "cfg.dot"
                nx.nx_pydot.write_dot(G, out_filename)


def svg_to_html(title: str, svg: str, functions = None) -> str:
    """
    Produces an interactive html page from an svg image of a CFG.

    Args:
        svg: the string of the SVG to process

    Returns:
        HTML string of interactive web page source for the given CFG.
    """

    lines = svg.split("\n")
    page = []
    page.append(
      f"""
      <html>
      <title>{title}</title>
      """
    )
    
    page.append("""
              <body>
              <style>
              .node
              {
                transition: all 0.05s ease-out;
              }
              .node:hover
              {
                stroke-width: 1.5;
                cursor:pointer
              }
              .node:hover
              ellipse
              {
                fill: #EEE;
              }
              textarea#infobox {
                position: fixed;
                display: block;
                top: 0;
                right: 0;
              }

              .dropbutton {
                padding: 10px;
                border: none;
              }
              .dropbutton:hover, .dropbutton:focus {
                background-color: #777777;
              }
              .dropdown {
                margin-right: 5px;
                position: fixed;
                top: 5px;
                right: 0px;
              }
              .dropdown-content {
                background-color: white;
                display: none;
                position: absolute;
                width: 70px;
                box-shadow: 0px 5px 10px 0px rgba(0,0,0,0.2);
                z-index: 1;
              }
              .dropdown-content a {
                color: black;
                padding: 8px 10px;
                text-decoration: none;
                font-size: 10px;
                display: block;
              }

              .dropdown-content a:hover { background-color: #f1f1f1; }

              .show { display:block; }
              </style>
              """)

    for line in lines[3:]:
        page.append(line)

    page.append("""<textarea id="infobox" disabled=true rows=40 cols=80></textarea>""")

    # Create a dropdown list of functions if there are any.
    if functions is not None:
        page.append("""
              <div class="dropdown">
                <button onclick="showDropdown()" class="dropbutton">Functions</button>
               <div id="func-list" class="dropdown-content">""")

        for i, f in enumerate(functions):
            p = "public" if f._has_state_affected_instructions else "private"
            name = f.function_name
            page.append(
                '<a id=f_{0} href="javascript:highlightFunction({0})">{1} {2}</a>'.format(i, p, name))
        page.append("</div></div>")

    page.append("""<script>""")

    if functions is not None:
        func_map = {i: [b.ident() for b in f.blocks]
                    for i, f in enumerate(functions)}
        page.append("var func_map = {};".format(func_map))
        page.append("var highlight = new Array({}).fill(0);".format(len(func_map)))

    page.append("""
               // Set info textbox contents to the title of the given element, with line endings replaced suitably.
               function setInfoContents(element){
                   document.getElementById('infobox').value = element.getAttribute('xlink:title').replace(/\\\\n/g, '\\n');
               }

               // Make all node anchor tags in the svg clickable.
               for (var el of Array.from(document.querySelectorAll(".node a"))) {
                   el.setAttribute("onclick", "setInfoContents(this);");
               }

               const svg = document.querySelector('svg')
               const NS = "http://www.w3.org/2000/svg";
               const defs = document.createElementNS( NS, "defs" );

               // IIFE add filter to svg to allow shadows to be added to nodes within it
               (function(){
                 defs.innerHTML = makeShadowFilter()
                 svg.insertBefore(defs,svg.children[0])
               })()

               function colorToID(color){
                 return color.replace(/[^a-zA-Z0-9]/g,'_')
               }

               function makeShadowFilter({color = 'black',x = 0,y = 0, blur = 3} = {}){
                 return `
                 <filter id="filter_${colorToID(color)}" x="-40%" y="-40%" width="250%" height="250%">
                   <feGaussianBlur in="SourceAlpha" stdDeviation="${blur}"/>
                   <feOffset dx="${x}" dy="${y}" result="offsetblur"/>
                   <feFlood flood-color="${color}"/>
                   <feComposite in2="offsetblur" operator="in"/>
                   <feMerge>
                     <feMergeNode/>
                     <feMergeNode in="SourceGraphic"/>
                   </feMerge>
                 </filter>
                 `
               }

               // Shadow toggle functions, with filter caching
               function addShadow(el, {color = 'black', x = 0, y = 0, blur = 3}){
                 const id = colorToID(color);
                 if(!defs.querySelector(`#filter_${id}`)){
                   const d = document.createElementNS(NS, 'div');
                   d.innerHTML = makeShadowFilter({color, x, y, blur});
                   defs.appendChild(d.children[0]);
                 }
                 el.style.filter = `url(#filter_${id})`
               }

               function removeShadow(el){
                 el.style.filter = ''
               }

               function hash(n) {
                 var str = n + "rainbows" + n + "please" + n;
                 var hash = 0;
                 for (var i = 0; i < str.length; i++) {
                   hash = (((hash << 5) - hash) + str.charCodeAt(i)) | 0;
                 }
                 return hash > 0 ? hash : -hash;
               };

               function getColor(n, sat="80%", light="50%") {
                 const hue = hash(n) % 360;
                 return `hsl(${hue}, ${sat}, ${light})`;
               }

               // Add shadows to function body nodes, and highlight functions in the dropdown list
               function highlightFunction(i) {
                 for (var n of Array.from(document.querySelectorAll(".node ellipse"))) {
                   removeShadow(n);
                 }

                 highlight[i] = !highlight[i];
                 const entry = document.querySelector(`.dropdown-content a[id='f_${i}']`)
                 if (entry.style.backgroundColor) {
                   entry.style.backgroundColor = null;
                 } else {
                   entry.style.backgroundColor = getColor(i, "60%", "90%");
                 }

                 for (var j = 0; j < highlight.length; j++) {
                   if (highlight[j]) {
                     const col = getColor(j);
                     for (var id of func_map[j]) {
                       var n = document.querySelector(`.node[id='${id}'] ellipse`);
                       addShadow(n, {color:`${col}`});
                     }
                   }
                 }
               }

               // Show the dropdown elements when it's clicked.
               function showDropdown() {
                 document.getElementById("func-list").classList.toggle("show");
               }
               window.onclick = function(event) {
                 if (!event.target.matches('.dropbutton')) {
                   var items = Array.from(document.getElementsByClassName("dropdown-content"));
                   for (var item of items) {
                     item.classList.remove('show');
                   }
                 }
               }
              </script>
              </html>
              </body>
              """)

    return "\n".join(page)
