#!/usr/bin/env python3

import sys
import os
from pprint import pprint
import bisect
from collections import namedtuple
from subprocess import check_output
import json
from dataclasses import dataclass
import argparse
import json

addr2linePath = "/opt/local/bin/llvm-addr2line-mp-19"
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

CodeSegment = namedtuple("CodeSegment", ["startAddr", "endAddr", "offset"])

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


def findROMSymbol(romMap, addr):
    sortedKeys = romMap[1]
    idx = bisect.bisect_right(sortedKeys, addr) - 1
    
    if idx >= 0:
        return romMap[0][sortedKeys[idx]]
    
    return None


def findCodeSegmentForGlobalAddr(globalAddr):
    # TODO: support multiple segments
    codeSegment = codeSegments[1]

    if not (globalAddr >= codeSegment.startAddr and globalAddr < codeSegment.endAddr):
        return None
    
    return codeSegment


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

    addr = globalAddr - codeSegment.startAddr + codeSegment.offset
    allAddrData[globalAddr] = CodeAddrData(type='func', addr=addr, symbol=None, file=None, line=None)
    
    return True


def determineFileAndLineNumbers(binaryPath, addrsToProcess):
    localAddrs = [hex(allAddrData[globalAddr].addr) for globalAddr in addrsToProcess]
    
    if not os.path.exists(binaryPath):
        raise Exception(f"Can't find binary: {binaryPath}")
    
    jsonData = check_output([addr2linePath, "--output-style=JSON", "--print-source-context-lines=1",
                             "-f", "-e", binaryPath] + localAddrs)
    processedAddrs = json.loads(jsonData)
    
    if len(processedAddrs) != len(addrsToProcess):
        raise Exception("Mis-matched data from addr2line")
    
    for i in range(len(addrsToProcess)):
        globalAddr = addrsToProcess[i]
        
        if len(processedAddrs[i]["Symbol"]) == 0:
            raise Exception(f"Code offset {localAddrs[i]} has no associated symbol")
        
        if len(processedAddrs[i]["Symbol"]) > 1:
            raise Exception(f"Code offset {localAddrs[i]} has more than one associated symbol")
        
        data = processedAddrs[i]["Symbol"][0]
        addrData = allAddrData[globalAddr]
        addrData.symbol = data["FunctionName"]
        
        if len(data["FileName"]) > 0 and "Source" in data:
            addrData.file = data["FileName"]
            addrData.line = data["Line"]
            addrData.source = data["Source"]


def addSampleToFunction(sample, symbol):
    addrData = allAddrData[sample]
    
    if addrData.type == 'trap' or addrData.file is None or addrData.line is None or addrData.source is None:
        return
    
    if symbol not in functionSamples:
        functionSamples[symbol] = {}
    
    key = (addrData.file, addrData.line)
    
    if key in functionSamples[symbol]:
        functionSamples[symbol][key].count += 1
    else:
        s = FunctionSample()
        s.line = addrData.line
        s.file = os.path.basename(addrData.file)[:filenameMaxChars]
        s.filePath = addrData.file
        s.symbol = symbol
        s.source = addrData.source
        functionSamples[symbol][key] = s


def countSamples():
    for sample in samples:
        symbol = allAddrData[sample[0]].symbol
        exclusiveTally[symbol] = exclusiveTally.get(symbol, 0) + 1
        addSampleToFunction(sample[0], symbol)
        
        for stackItem in sample:
            symbol = allAddrData[stackItem].symbol
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
        
        if codeCount != 1:
            raise Exception("Multi-segment apps not currently supported")
        
        for i in range(codeCount):
            codeId = readInt(f, 2)
            startAddr = readInt(f, 4)
            endAddr = readInt(f, 4)
            # print(f"Code segment: {startAddr:8x} - {endAddr:8x}")
            codeSegments[codeId] = CodeSegment(startAddr, endAddr, 0)
        
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

def process(profilePath, binaryPath):
    global allAddrData, samples

    rawSamples = readProfile(profilePath)
    
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

    print("Total samples: ", len(samples))
    print("Unusable samples: ", ignoredSamples)
    print("")
    
    determineFileAndLineNumbers(binaryPath, addrsToProcess)
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
    
    for symbol, lineDict in functionSamples.items():
        funcSamples = sorted(lineDict.values(), key=lambda x: x.line)
        totalSampleCount = sum([funcSample.count for funcSample in funcSamples])
        
        if totalSampleCount == 0:
            continue
        
        for funcSample in funcSamples:
            if funcSample.filePath not in fileAndLineData:
                fileAndLineData[funcSample.filePath] = {}
            
            percent = (funcSample.count * 10000 // totalSampleCount) / 100.0
            
            fileAndLineData[funcSample.filePath][funcSample.line] = {"count": funcSample.count, "percent": percent}        

    with open(samplesOutPath, "w") as f:
        f.write(json.dumps(fileAndLineData))
        

def parseArgs():
    parser = argparse.ArgumentParser(description="Profile parsing arguments")
    parser.add_argument("profile_path", help="Path to profile")
    parser.add_argument("binary_path", help="Path to ELF formatted binary (e.g. Project.code.bin.gdb)")
    parser.add_argument("-r", "--rom-maps-dir",
                        help="Path to ROM maps directory (default: same directory as this script)")
    parser.add_argument("-a", "--addr2line",
                        default=addr2linePath,
                        help=f"Path to llvm-addr2line (default: {addr2linePath})")
    parser.add_argument("--function-max-chars",
                        type=int,
                        default=functionNameMaxChars,
                        help=f"Maximum number of characters in function names (default: {functionNameMaxChars})")
    parser.add_argument("--filename-max-chars",
                        type=int,
                        default=filenameMaxChars,
                        help=f"Maximum number of characters in filenames (default: {filenameMaxChars})")
    parser.add_argument("--samples-path",
                        default=None,
                        help=f"Also write out samples as a json file")
    return parser.parse_args()


def main():
    global romMapsDir, addr2linePath, functionNameMaxChars, filenameMaxChars, samplesOutPath
    
    args = parseArgs()
    addr2linePath = args.addr2line
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
