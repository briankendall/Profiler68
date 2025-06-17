#!/usr/bin/env python3

# This script is very crude! Don't expect it to successfully convert
# sophisticated GAS assembly files to MPW. It should at least work for
# profilerUtils.s.

# Note that the GAS assembly requires some extra annotations in order for the
# conversion to work. See profilerUtils.s for an example of what's required, but
# the gist of it is that you prefix lines with:
# *MPW:
# to have them only be included in the MPW version, for things like INCLUDE
# statements. Lines suffixed with:
# | NoMPW
# will not be included in the MPW script, and is used for the particular way A
# traps are handled for GAS assembly. (Again, see profilerUtils.s.) Finally, any
# label that should be a procedure for MPW must be suffixed with:
# | MPW PROC
#  and the procedure must have:
# *MPW:    ENDP
# to denote where it ends.

import os
import sys
import re
import xattr

procsToExport = set()

def convertLine(line, nextLine, procs, state):
    # Ignore lines marked as no MPW
    if '| NoMPW' in line:
        return None, False
    
    if line.startswith("#"):
        return None, False
    if '.altmacro' in line:
        return None, False
    if line.strip().startswith("|"):
        return line.replace("|", ";"), False
    
    # Uncomment lines marked for MPW
    if line.startswith('*MPW:'):
        return line[5:], False
    
    # Sections to segments
    if line.startswith('.text'):
        return '    SEG', False
    
    # Ignore this:
    if line.startswith('.align'):
        return None, False
    
    # Fix hex literals
    line = line.replace("0x", "$")

    # Strip % from registers and make them uppercase
    line = re.sub(r'%([dDaA])([0-7])', lambda m: m.group(1).upper() + m.group(2), line)
    line = line.replace('%pc', 'PC')
    line = line.replace('%PC', 'PC')
    line = line.replace('%SP', 'SP')
    line = line.replace('%sp', 'SP')

    # Handle global symbols
    match = re.match(r'\s*\.global\s+(.+)', line)
    if match is not None:
        symbol = match.group(1)
        
        if symbol not in procs:
            line = re.sub(r'\.global\s+(.+)', r'    EXPORT \1:DATA', line)
            return line, False
        else:
            # Stash away global procs for later
            procsToExport.add(symbol)
            return None, False
    
    # Handle imports
    line = re.sub(r'\.extern\b', '    IMPORT', line)

    # Symbols and labels      
    
    match = re.match(r'^\s*([^:]+):', line)
    if match is not None:
        # Handle a proc definition:
        if match.group(1) in procs:
            line = match.group(1) + " PROC"
            
            if match.group(1) in procsToExport:
                line += " EXPORT"
            
            return line, False
        
        # Handle a variable definition:
        if re.match('^\s*\.\w+ \d+', nextLine):
            line = re.sub(r'(\w+):', r'\1', line)
            
            nextLine = re.sub(r'\.byte\b',  'DC.B', nextLine)
            nextLine = re.sub(r'\.word\b',  'DC.W', nextLine)
            nextLine = re.sub(r'\.short\b',  'DC.W', nextLine)
            nextLine = re.sub(r'\.long\b',  'DC.L', nextLine)
            nextLine = re.sub(r'\.space\s+(\d+)', r'DS.B \1', nextLine)
            
            line += ' ' + nextLine
            return line, True
    
    # Special way of representing a traps:
    line = line.replace('TRAP ', '')


    # Macros and conditionals
    
    match = re.match(r'\.macro (\w+) ?(.*)', line)
    if match is not None:
        if len(match.group(2)) > 0:
            args = ', '.join(["&" + arg.strip() for arg in match.group(2).split(",")])
        else:
            args = ''
        line = f"    MACRO\r    {match.group(1)} {args}"
        state["inMacro"] = True
        return line, False
    
    if '.endm' in line:
        line = "    ENDM"
        state["inMacro"] = False
        state["vars"] = set()
        return line, False
        
    match = re.match(r'\s*.rept\s+(.+)', line)
    if match is not None:
        counterVar = f"&_rept_counter_{state['reptCount']}"
        count = match.group(1)
        state['reptCount'] += 1
        
        result = f"    LCLA {counterVar}\r    WHILE ({counterVar} < {count}) DO\r        {counterVar}: SETA {counterVar} + 1"
        
        return result, False
    
    if '.endr' in line:
        line = "    ENDWHILE"
        return line, False
    
    match = re.match(r'\s*.if\s+(.+)', line)
    if match is not None:
        conditional = match.group(1)
        conditional = conditional.replace("==", "=")
        conditional = conditional.replace("!=", "<>")
        line = f"    IF ({conditional}) THEN"
        return line, False
    
    line = re.sub(r'\.else\b',  'ELSE',  line, flags=re.IGNORECASE)
    line = re.sub(r'\.endif\b', 'ENDIF', line, flags=re.IGNORECASE)
    
    # Variables and constants
    
    match = re.match('(\s+)LOCAL\s+(.+)', line)
    if match is not None:
        vars = [var.strip() for var in match.group(2).split(",")]
        varNames = ["&" + var for var in vars]
        line = f"{match.group(1)}LCLA {', '.join(varNames)}"
        state["vars"].update(vars)
        
        return line, False
    
    if ".set" in line:
        # Fix modulo:
        line = line.replace(" % ", " MOD ")
        
        if state["inMacro"]:
            match = re.match(r"\s*\.set\s+(\w+)\s*,\s*(.*)", line)
            
            if match is None:
                raise Exception(f"Line no good! {line}")
            
            var = match.group(1)
            expr = match.group(2)
            
            result = ""
            
            if var not in state["vars"]:
                result += f"    LCLA &{var}\r"
                state["vars"].add(var)
            
            for otherVar in state["vars"]:
                expr = re.sub(r"(?:(?<=\W)|(?<=^))(?<!&)" + otherVar, "&" + otherVar, expr)  
        
            result += f"    &{var}: SETA {expr}"
            
            return result, False
        
        else:
            line = re.sub(r'\s*\.set\s*(\w+)\s*,\s*(\w+)', r'\1 EQU \2', line)
        
            return line, False
    
    # Fix local variable references
    line = re.sub(r"%(\w+)", r"&\1", line)
    
    # Make sure any other already declared locals are prefixed with &
    for otherVar in state["vars"]:
        line = re.sub(r"(?:(?<=\W)|(?<=^))(?<!&)" + otherVar, "&" + otherVar, line)  
    
    # Label qualifiers
    line = re.sub(r'(\d)([bf])\b', lambda m: m.group(1) + m.group(2).upper(), line)

    # Fix jump statements
    line = line.replace("jsr.l", "jsr")
    line = line.replace("jmp.l", "jmp")

    # Fix comments
    line = line.replace('|', ';')
    
    # Ensure it has indentation
    while line[0:4] != "    ":
        line = " " + line
    
    return line, False


def convertFile(inPath, outPath):
    lines = []
    
    with open(inPath, 'r') as fin:
        for ln in fin:
            lines.append(ln.rstrip())
    
    # First process macro arguments so that we have the final form of labels:
    
    for i in range(len(lines)):
        lines[i] = re.sub(r'\\(\w+)\\\(\)', r'&\1.', lines[i])
        lines[i] = re.sub(r'\\(\w+)', r'&\1', lines[i])
    
    # We need to know which labels are procs ahead of time:
    procs = [re.findall(r'^\s*([^:]+):', line)[0] for line in lines if '| MPW PROC' in line]

    state = {
        "inMacro": False,
        "vars": set(),
        "reptCount": 0
    }
    
    with open(outPath, 'wb') as fout:
        skipNext = False
        
        for i, line in enumerate(lines):
            if skipNext:
                skipNext = False
                continue
            
            nextLine = lines[i+1] if i < len(lines)-1 else ""
            convertedLine, skipNext = convertLine(line, nextLine, procs, state)
            
            if convertedLine is None:
                continue
            
            bytes = convertedLine.encode('macroman') + b'\r'
            fout.write(bytes)
        
        # Finish off the file:
        fout.write("\r    END\r".encode('macroman'))
    
    # Need this for MPW to recognize and compile the file:
    xattr.setxattr(outPath, 'com.apple.FinderInfo',
                   b'TEXTMPS \x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Args: input.s output.a")
        sys.exit(1)
    
    convertFile(sys.argv[1], sys.argv[2])
    print(f"Converted {sys.argv[1]} → {sys.argv[2]}")
