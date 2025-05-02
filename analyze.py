#!/usr/bin/env python3

import sys
import os
from pprint import pprint
import bisect
from subprocess import check_output
import json
from dataclasses import dataclass
import argparse
import json
import re

llvmSymbolizer = None
readelfPath = None
functionNameMaxChars = 32
filenameMaxChars = 14
romMapsDir = os.path.join(os.path.dirname(__file__), "ROM Maps")

@dataclass
class CodeAddrData:
    type: str = None
    addr: int = None
    symbol: str = None
    file: str = None
    line: int = None
    source: str = None

@dataclass
class FunctionSample:
    count: int = 0
    symbol: str = ""
    line: str = ""
    file: str = ""
    filePath: str = ""
    source: str = ""

@dataclass
class CodeSegment:
    addrStart: int = 0
    addrEnd: int = 0
    sectionStart: int = 0
    sectionEnd: int = 0

samples = []
allAddrData = {}
codeSegments = {}
romBase = None
romSize = 0
romMap = None
inclusiveTally = {}
exclusiveTally = {}
functionSamples = {}
samplesOutPath = None


def readInt(f, size):
    val = f.read(size)
    
    if len(val) != size:
        raise Exception("Unexpected EOF")
    
    return int.from_bytes(val, "big")


def readPStr(f):
    length = readInt(f, 1)
    
    if length is None:
        raise Exception("Unexpected EOF")
    
    result = f.read(length).decode("mac_roman")
    
    if len(result) != length:
        raise Exception("Unexpected EOF")
    
    if (length + 1) % 2 == 1:
        f.read(1)
    
    return result


def macModelToROMMapFilename(model):
    # NB: You may need to tweak this function to get it to work with your Mac model
    # Currently only tested with: SE, SE/30, IIcx
    return model.replace(' ', '').replace('/', '').replace('Macintosh', 'Mac') + 'ROM.map'


def readMPWROMMap(model):
    global romMap, romSize
    
    result = {}
    
    with open(os.path.join(romMapsDir, macModelToROMMapFilename(model)), "r") as f:
        lines = f.readlines()
        inROMSegment = False
        
        for line in lines:
            words = line.rstrip().split()
            
            if line.startswith(' '):
                if line.startswith(' seg'):
                    inROMSegment = words[1].startswith('ROM')
                
                if  line.startswith(' size') and inROMSegment:
                    romSize = int(words[2], 16)
                
                continue
            
            if not inROMSegment or len(words) < 3:
                continue
            
            addr = int(words[2].split(',')[1], 16)
            result[addr] = words[0]
    
    romMap = (result, sorted(result.keys()))


def findKeyEqualToOrLessThan(m, sortedKeys, k):
    idx = bisect.bisect_right(sortedKeys, k) - 1
    
    if idx >= 0:
        return m[sortedKeys[idx]]
    
    return None


def findROMSymbol(romMap, addr):
    return findKeyEqualToOrLessThan(romMap[0], romMap[1], addr)


def readCodeSegments(binaryPath):
    data = check_output([readelfPath, "--wide", "--sections", binaryPath])
    sectionData = data.decode('utf-8')
    
    if len(codeSegments) == 1:
        codeSectionEntries = re.findall(r"^\s+\[[ 0-9]+]\s+\.text\s+PROGBITS\s+([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)",
                                        sectionData, re.MULTILINE)
        
        if len(codeSectionEntries) == 0:
            raise Exception("Did not find expected .text section in single-segment application")
        
        codeSections = {1: (".text", int(codeSectionEntries[0][0], 16), int(codeSectionEntries[0][1], 16))}
    else:
        codeSectionEntries = re.findall(r"^\s+\[[ 0-9]+]\s+(\.code(\d+))\s+PROGBITS\s+([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)",
                                        sectionData, re.MULTILINE)
        codeSections = {int(entry[1]): (entry[0], int(entry[2], 16), int(entry[3], 16)) for entry in codeSectionEntries}
    
    if len(codeSections) != len(codeSegments):
        raise Exception("Different number of code sections in binary and CODE segments in profile")
    
    for segmentId, (segmentName, offset, size) in codeSections.items():
        if segmentId not in codeSegments:
            raise Exception(f"Code section {segmentName} does not have corresponding CODE segment in profile")
    
        codeSegments[segmentId].sectionStart = offset
        codeSegments[segmentId].sectionEnd = offset + size


def findCodeSegmentForGlobalAddr(globalAddr):
    for codeSegment in codeSegments.values():
        if globalAddr >= codeSegment.addrStart and globalAddr < codeSegment.addrEnd:
            return codeSegment
    
    return None


def processSampleGlobalAddr(globalAddr):
    if globalAddr in allAddrData:
        return True
    
    if globalAddr >= romBase:
        if globalAddr >= romBase + romSize:
            # Addr is past the ROM
            return False
        
        romAddr = globalAddr - romBase
        symbol = findROMSymbol(romMap, romAddr)
        
        allAddrData[globalAddr] = CodeAddrData(type='trap', addr=romAddr, symbol=symbol, file=None, line=None)
        
        return True
    
    codeSegment = findCodeSegmentForGlobalAddr(globalAddr)
    
    if codeSegment is None:
        # Addr not in any code segment
        return False

    addr = globalAddr - codeSegment.addrStart + codeSegment.sectionStart
    allAddrData[globalAddr] = CodeAddrData(type='func', addr=addr, symbol=None, file=None, line=None)
    
    return True


def determineFileAndLineNumbersUsingLLVM(binaryPath, addrsToProcess):
    localAddrs = [hex(allAddrData[globalAddr].addr) for globalAddr in addrsToProcess]
    
    if not os.path.exists(binaryPath):
        raise Exception(f"Can't find binary: {binaryPath}")
    
    jsonData = check_output([llvmSymbolizer, "--output-style=JSON", "--print-source-context-lines=1",
                             "-f", "-e", binaryPath] + localAddrs)
    processedAddrs = json.loads(jsonData)
    
    if len(processedAddrs) != len(addrsToProcess):
        raise Exception("Mis-matched data from addr2line")
    
    for i in range(len(addrsToProcess)):
        globalAddr = addrsToProcess[i]
        
        if len(processedAddrs[i]["Symbol"]) == 0:
            raise Exception(f"Code offset {localAddrs[i]} has no associated symbol")
        
        if len(processedAddrs[i]["Symbol"]) > 1:
            raise Exception(f"Code offset {localAddrs[i]} has more than one associated symbol. "
                            "Note: linking with -Wl,-gc-sections will cause this to happen.")
        
        data = processedAddrs[i]["Symbol"][0]
        addrData = allAddrData[globalAddr]
        addrData.symbol = data["FunctionName"]
        
        if len(data["FileName"]) > 0 and "Source" in data:
            addrData.file = data["FileName"]
            addrData.line = data["Line"]
            addrData.source = data["Source"]


def getSymbols(binaryPath):
    data = check_output([readelfPath, "--wide", "--symbols", binaryPath])
    symbolData = data.decode('utf-8')
    
    lines = symbolData.split('\n')
    symbolsByAddr = {}
    
    for line in lines:
        match = re.match(r'^\s+\d+:\s+([0-9A-Fa-f]+)\s+\d+\s+(\w+)\s+\w+\s+\w+\s+\w+\s+(.+)$', line)
        
        if match is None:
            continue
        
        addr = int(match.group(1), 16)
        
        if addr == 0:
            continue
        
        if addr not in symbolsByAddr:
            symbolsByAddr[addr] = {}
        
        type = match.group(2)
        
        if type not in symbolsByAddr[addr]:
            symbolsByAddr[addr][type] = []
        
        symbolsByAddr[addr][type].append(match.group(3))
        
        if type == "FUNC" and len(symbolsByAddr[addr][type]) > 1:
            raise Exception(f"readelf --symbols reports more than one function at same address?! addr: {addr}")
    
    return symbolsByAddr


def getAddrToLineEntries(binaryPath):
    symbols = getSymbols(binaryPath)
    
    data = check_output([readelfPath, "--wide", "--debug-dump=decodedline", binaryPath])
    lineData = data.decode('utf-8')
    lines = lineData.split('\n')
    filenamesToPath = {}
    addrsData = {}
    
    currentCU = None
    currentFile = None
    startingBlock = True
    invalidBlock = False
    currentFunc = None
    
    for i, line in enumerate(lines):
        # Is the line specifying a code unit with a file?
        match = re.match(r"^CU: (.*):$", line)
        
        if match is not None:
            currentCU = match.group(1)
            startingBlock = True
            filenamesToPath[os.path.basename(match.group(1))] = match.group(1)
            continue
        
        # Is it specifying another file within a code unit?
        match = re.match(r"^(/.*):$", line)
        
        if match is not None:
            currentFile = match.group(1)
            filenamesToPath[os.path.basename(match.group(1))] = match.group(1)
            continue
        
        # Is it an entry specifying an address / line number association?
        match = re.match(r"^(.+?)\s+(\d+|-)\s+(?:0x)?([0-9a-fA-F]+)\s*(?:\s+\d+)?(?:\s+x)?$", line)
        
        if match is None:
            continue
        
        filename = match.group(1)
        addr = int(match.group(3), 16)
        
        if match.group(2) == "-":
            # End of code block / function
            startingBlock = True
            
            if not invalidBlock:
                addrsData[addr] = [filename, None, None]
            
            continue
        
        lineNumber = int(match.group(2))
        
        if startingBlock:
            # Starting a code block
            # If its address is 0, then we know it was removed due to linker garbage collection
            startingBlock = False
            invalidBlock = (addr == 0)
            
            if invalidBlock:
                currentFunc = None
            else:
                if addr not in symbols:
                    raise Exception(f"Started block with address not listed in symbol table?? addr: {addr}")
                
                currentFunc = symbols[addr]["FUNC"][0] if "FUNC" in symbols[addr] else None
        
        if invalidBlock:
            continue
        
        addrsData[addr] = [filename, lineNumber, currentFunc]
    
    # Convert filenames to full paths now that we know them all:
    for addrData in addrsData.values():
        addrData[0] = filenamesToPath[addrData[0]]
    
    return addrsData


def determineFileAndLineNumbersUsingReadelf(binaryPath, addrsToProcess):
    def getSourceLine(path, lineNumber):
        if path not in sourceData:
            if not os.path.exists(path):
                sourceData[path] = []
            else:
                with open(path, "r") as f:
                    sourceData[path] = f.readlines()
    
        lines = sourceData[path]
        
        if lineNumber <= 0 or lineNumber > len(lines):
            return ""
        else:
            return lines[lineNumber-1]
    
    addrsData = getAddrToLineEntries(binaryPath)
    
    addrsDataSortedKeys = sorted(addrsData.keys())
    unknownSymbolCount = 0
    sourceData = {}
    
    for i in range(len(addrsToProcess)):
        globalAddr = addrsToProcess[i]
        addrData = allAddrData[globalAddr]
        data = findKeyEqualToOrLessThan(addrsData, addrsDataSortedKeys, addrData.addr)
        
        if data is None:
            unknownSymbolCount += 1
            data = ("NOFILE", 0, f"UNKNOWN_SYMBOL_{unknownSymbolCount}")
        
        addrData.file = data[0]
        addrData.line = data[1]
        addrData.symbol = data[2]
        
        if addrData.file is not None and addrData.line is not None:
            addrData.source = f"{addrData.line} >: " + getSourceLine(addrData.file, addrData.line)
        else:
            addrData.source = None


def addSampleToFunction(sample, symbol):
    addrData = allAddrData[sample]
    
    if addrData.type == 'trap' or addrData.file is None or addrData.line is None:
        return
    
    if symbol not in functionSamples:
        functionSamples[symbol] = {}
    
    key = (addrData.file, addrData.line)
    
    if key in functionSamples[symbol]:
        functionSamples[symbol][key].count += 1
    else:
        s = FunctionSample()
        s.count = 1
        s.line = addrData.line
        s.file = os.path.basename(addrData.file)[:filenameMaxChars]
        s.filePath = addrData.file
        s.symbol = symbol
        s.source = addrData.source
        functionSamples[symbol][key] = s


def countSamples():
    for sample in samples:
        addrData = allAddrData[sample[0]]
        symbol = allAddrData[sample[0]].symbol
        exclusiveTally[symbol] = exclusiveTally.get(symbol, 0) + 1
        inclusiveTally[symbol] = inclusiveTally.get(symbol, 0) + 1
        addSampleToFunction(sample[0], symbol)
        
        for stackItem in sample[1:]:
            symbol = allAddrData[stackItem].symbol
            
            if symbol is None:
                continue
            
            inclusiveTally[symbol] = inclusiveTally.get(symbol, 0) + 1
            addSampleToFunction(stackItem, symbol)


def readProfile(profilePath):
    global codeSegments, romBase, romMap
    rawSamples = []
    
    with open(profilePath, "rb") as f:
        model = readPStr(f)
        readMPWROMMap(model)
        romBase = readInt(f, 4)
        # print(f"romBase: {romBase:8x}")
        
        codeCount = readInt(f, 2)
        
        for i in range(codeCount):
            codeId = readInt(f, 2)
            addrStart = readInt(f, 4)
            addrEnd = readInt(f, 4)
            # print(f"Code segment {codeId}: {addrStart:8x} - {addrEnd:8x}")
            codeSegments[codeId] = CodeSegment(addrStart, addrEnd, 0)
        
        # Obnoxious pattern for checking if we're at EOF:
        while f.read(1):
            f.seek(-1, 1)
            
            sampleSize = readInt(f, 2)
            sample = []
            
            for i in range(sampleSize):
                val = readInt(f, 4)
                val -= 2 # account for this being the return addr, not the addr being executed
                sample.append(val)
            
            rawSamples.append(tuple(sample))
    
    return rawSamples


def sampleHasValidSymbols(sample):
    return all(map(lambda addr: allAddrData[addr].symbol is not None, sample))


def process(profilePath, binaryPath):
    global allAddrData, samples

    rawSamples = readProfile(profilePath)
    readCodeSegments(binaryPath)
    
    ignoredSamples = 0
    samples = []
    
    for sample in rawSamples:
        usable = len(sample) > 0
        
        for i, globalAddr in enumerate(sample):
            if not processSampleGlobalAddr(globalAddr):
                usable = False
                break
        
        if usable:
            samples.append(sample)
        else:
            ignoredSamples += 1

    addrsToProcess = [key for key, val in allAddrData.items() if val.type == 'func']

    print("Total samples: ", len(rawSamples))
    print("")
    
    if llvmSymbolizer is not None:
        determineFileAndLineNumbersUsingLLVM(binaryPath, addrsToProcess)
    else:
        determineFileAndLineNumbersUsingReadelf(binaryPath, addrsToProcess)
    
    samples = list(filter(sampleHasValidSymbols, samples))
    print("Usable samples: ", len(samples))
    print("Unusable samples: ", len(rawSamples) - len(samples))
    
    countSamples()
    
    printResults()
    
    if samplesOutPath is not None:
        writeSamplesAsJSON()


def printResults():
    def printSymbol(symbol, count):
        percent = ((count * 10000) // len(samples)) / 100.0
        print(f"    {symbol[:functionNameMaxChars]:{functionNameMaxChars}} - {count:8}   {percent:6}%")
    
    print("--------------------------------------------")
    print("Functions by inclusive samples:")
    print("--------------------------------------------\n")
    
    funcList = sorted([(count, symbol) for symbol, count in inclusiveTally.items()], reverse=True)
    
    for count, symbol in funcList:
        printSymbol(symbol, count)
    
    print("\n\n--------------------------------------------")
    print("Functions by exclusive samples:")
    print("--------------------------------------------\n")
    
    funcList = sorted([(count, symbol) for symbol, count in exclusiveTally.items()], reverse=True)
    
    for count, symbol in funcList:
        printSymbol(symbol, count)
    
    print("\n\n--------------------------------------------")
    print("Samples by function and line:")
    print("--------------------------------------------")
    
    for symbol, lineDict in functionSamples.items():
        funcSamples = sorted(lineDict.values(), key=lambda x: x.line)
        totalSampleCount = sum([funcSample.count for funcSample in funcSamples])
        
        if totalSampleCount == 0:
            continue
        
        print(f"\n=== {symbol + ' ':=<40}")
        
        for funcSample in funcSamples:
            percent = (funcSample.count * 10000 // totalSampleCount) / 100.0
            print(f"  count:{funcSample.count:6} {percent:6}%  {funcSample.file:>{filenameMaxChars}}  {funcSample.source.strip()}")
        
    print("")
    
    print("\n\n--------------------------------------------")
    print("All stack traces:")
    print("--------------------------------------------")
    
    stackTraces = {}
    
    for sample in samples:
        sampleSymbols = tuple(reversed([allAddrData[globalAddr].symbol for globalAddr in sample]))
        
        if sampleSymbols not in stackTraces:
            stackTraces[sampleSymbols] = 1
        else:
            stackTraces[sampleSymbols] += 1
    
    sortedStackTraces = sorted([(count, sampleSymbols) for sampleSymbols, count in stackTraces.items()], reverse=True)
    
    for count, sampleSymbols in sortedStackTraces:
        print(f"\n({count} times:)")
        for i, sampleSymbol in enumerate(sampleSymbols):
            spaces = ' ' * (i+1) * 2
            print(f"{spaces}{sampleSymbol}")


def writeSamplesAsJSON():
    fileAndLineData = {}
    totalSampleCount = len(samples)
    
    for symbol, lineDict in functionSamples.items():
        funcSamples = sorted(lineDict.values(), key=lambda x: x.line)
        # totalSampleCount = sum([funcSample.count for funcSample in funcSamples])
        
        # if totalSampleCount == 0:
        #     continue
        
        for funcSample in funcSamples:
            if funcSample.filePath not in fileAndLineData:
                fileAndLineData[funcSample.filePath] = {}
            
            percent = (funcSample.count * 10000 // totalSampleCount) / 100.0
            
            fileAndLineData[funcSample.filePath][funcSample.line] = {"count": funcSample.count, "percent": percent}        

    with open(samplesOutPath, "w") as f:
        f.write(json.dumps(fileAndLineData))
        

def parseArgs():
    defaultLLVMSymbolizerPath = "/opt/local/bin/llvm-symbolizer-mp-19"
    llvmSymbolizerPath = None
    
    # Bending over backwards a bit to do this custom bit of behavior with --llvm-symbolizer:
    class CustomHelpFormatter(argparse.HelpFormatter):
        def _format_action_invocation(self, action):
            if len(action.option_strings) != 1 or action.option_strings[0] != '--llvm-symbolizer':
                return super()._format_action_invocation(action)
            
            return '--llvm-symbolizer[=PATH]'
    
    for i, arg in enumerate(sys.argv[:]):
        if arg.startswith("--llvm-symbolizer="):
            llvmSymbolizerPath = arg[len("--llvm-symbolizer="):]
            del sys.argv[i]
    
    parser = argparse.ArgumentParser(formatter_class=CustomHelpFormatter)
    parser.add_argument("profile_path", help="Path to profile")
    parser.add_argument("binary_path", help="Path to ELF formatted binary (e.g. Project.code.bin.gdb)")
    parser.add_argument("-r", "--rom-maps-dir", metavar="PATH",
                        help="Path to ROM maps directory (default: same directory as this script)")
    parser.add_argument("-t", "--retro68-toolchain",  metavar="PATH",
                        help="Specify the path to Retro68's toolchain directory.")
    parser.add_argument("--llvm-symbolizer", action="store_true",
                        help=f"Use llvm-symbolizer for symbolication instead of Retro68's elftools, and optionally "
                        f"specify the path to llvm-symbolizer (defaulting to {defaultLLVMSymbolizerPath})")
    parser.add_argument("--function-max-chars",
                        type=int, metavar="COUNT",
                        default=functionNameMaxChars,
                        help=f"Maximum number of characters in function names (default: {functionNameMaxChars})")
    parser.add_argument("--filename-max-chars",
                        type=int, metavar="COUNT",
                        default=filenameMaxChars,
                        help=f"Maximum number of characters in filenames (default: {filenameMaxChars})")
    parser.add_argument("--samples-path",
                        default=None, metavar="PATH",
                        help=f"Write out samples as a json file")
    args = parser.parse_args()
    
    if args.llvm_symbolizer == True or llvmSymbolizerPath is not None:
        args.llvm_symbolizer = llvmSymbolizerPath or defaultLLVMSymbolizerPath
    else:
        args.llvm_symbolizer = None
    
    return args


def main():
    global romMapsDir, llvmSymbolizer, readelfPath, functionNameMaxChars, filenameMaxChars, samplesOutPath
    
    args = parseArgs()
    
    llvmSymbolizer = args.llvm_symbolizer
    
    if args.retro68_toolchain is not None:
        readelfPath = os.path.join(args.retro68_toolchain, "bin", "m68k-apple-macos-readelf")
    elif "RETRO68_TOOLCHAIN" in os.environ:
        readelfPath = os.path.join(os.environ["RETRO68_TOOLCHAIN"], "bin", "m68k-apple-macos-readelf")
    else:
        sys.stderr.write("Error: need to specify path to Retro68's toolchain directory, either using\n"
                         "--retro68-toolchain or RETRO68_TOOLCHAIN environment variable\n")
        sys.exit(1)
    
    functionNameMaxChars = args.function_max_chars
    filenameMaxChars = args.filename_max_chars
    profilePath = args.profile_path
    binaryPath = args.binary_path
    
    if args.rom_maps_dir:
        romMapsDir = args.rom_maps_dir
    
    if args.samples_path:
        samplesOutPath = args.samples_path
    
    process(profilePath, binaryPath)


if __name__ == "__main__":
    main()
