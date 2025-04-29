#include <Errors.h>
#include <Files.h>
#include <Folders.h>
#include <Gestalt.h>
#include <Memory.h>
#include <Resources.h>
#include <Timer.h>
#include <stdio.h>
#include <string.h>

#ifdef LOGGING_AVAILABLE
    #include "logging.h"
#else
    #define printLog(...)
#endif

extern UInt32 profilerEndlessLoopAddr;
extern UInt32 profilerStackCrawlStopAddr;
extern short profilerPCOffset;
extern TMTask profilerTimerTask;
extern UInt32 profilerAppHeapStart;
extern UInt32 profilerAppHeapEnd;

static UInt16 *sampleData = NULL;
static UInt16 *currentSample = NULL;
static UInt32 sampleDataSizeWords = 0;
static UInt32 sampleCount = 0;
static UInt32 badSampleCount = 0;
static TimerUPP timerUPP = NULL;
static long timerUSec;
static Boolean timerEnabled = false;
static UInt16 errorCode = 0;

void ProfilerFindPCOffset();
void ProfilerTimerFunctionShim();
void ProfilerStackCrawl(UInt32 *buffer, UInt16 *outEntriesCount, UInt32 *endOfBuffer, UInt16 *error);

static void PrependPString(const Str255 src, Str255 dst)
{
    unsigned char srcLen = src[0];
    unsigned char dstLen = dst[0];
    
    if (srcLen + dstLen > 255) {
        srcLen = 255 - dstLen;
    }
    
    memmove(&dst[1 + srcLen], &dst[1], dstLen);
    memcpy(&dst[1], &src[1], srcLen);
    dst[0] = srcLen + dstLen;
}

static void AppendPString(Str255 dst, const Str255 src)
{
    unsigned char srcLen = src[0];
    unsigned char dstLen = dst[0];
    
    if (srcLen + dstLen > 255) {
        dstLen = 255 - srcLen;
    }
    
    memcpy(&dst[dstLen + 1], &src[1], srcLen);
    dst[0] = srcLen + dstLen;
}

void ProfilerTimerFunction(UInt8 *stackPointer)
{
    UInt32 returnAddr0;
    UInt16 count = 0;
    
    if (!timerEnabled) {
        return;
    }
    
    returnAddr0 = *(UInt32 *)(stackPointer + profilerPCOffset);
    
    if (returnAddr0 >= profilerAppHeapStart) {
        *(UInt32 *)(currentSample + 1) = returnAddr0;
        ProfilerStackCrawl((UInt32 *)(currentSample + 3), &count, (UInt32 *)(sampleData + sampleDataSizeWords - 1), &errorCode);
    } else {
        errorCode = 3;
    }
    
    if (errorCode != 0) {
        if (errorCode == 1) {
            // Ran out of buffer for samples, don't continue the timer
            return;
        }
        
        // Error code 2 means too many A6 frames, so probably a bad sample
        
        if (errorCode == 3) {
            // Got an invalid A6 address, so ignore this sample
            ++badSampleCount;
        }
        
        errorCode = 0;
        PrimeTime((QElemPtr)&profilerTimerTask, -timerUSec);
        
        return;
    }
    
    ++count;
    *currentSample = count;
    currentSample += 1 + count * 2;
    ++sampleCount;
    
    PrimeTime((QElemPtr)&profilerTimerTask, -timerUSec);
}

static Boolean CalculatePCOffset()
{
    UInt32 loopAddr;
    
    // This technique for calculating the offset on the stack that contains the
    // stored PC is the same as used by Apple's PerformLib: We start a timer,
    // create a single instruction that is an endless loop (i.e. bra.s
    // endlessloop) and then at interrupt time look for it in the stack. Because
    // the CCR is stored directly before the PC, we also set the low byte of the
    // CCR to 0x1F so that we can be sure we've found the right spot (i.e. 0x1F
    // followed by the address of the bra.s instruction). And then we increment
    // that point on the stack by 2 so that when the interrupt finishes,
    // execution returns to the instruction right after the endless loop, thus
    // breaking it. A bit silly, I know, but if it's good enough for Apple, it's
    // good enough for me. And it actually works!
    
    memset(&profilerTimerTask, 0, sizeof(profilerTimerTask));
    timerUPP = NewTimerProc(ProfilerFindPCOffset);
    profilerTimerTask.tmAddr = timerUPP;
    InsTime((QElemPtr)&profilerTimerTask);
    
    asm volatile (
        "lea endless_loop, %%a0 \n"
        "move.l %%a0, %0 \n"
        : "=d" (loopAddr)
        :
        : "a0"
    );
    profilerEndlessLoopAddr = loopAddr;
    profilerPCOffset = -100;
    
    PrimeTime((QElemPtr)&profilerTimerTask, 1);
    
    asm volatile (
        "move.w #0x1f, %%ccr \n"
        "endless_loop: \n"
        "bra.s endless_loop \n"
        ::: "cc"
    );
    
    RmvTime((QElemPtr)&profilerTimerTask);
    profilerTimerTask.tmAddr = NULL;
    DisposeRoutineDescriptor(timerUPP);
    timerUPP = NULL;
    
    if (profilerPCOffset < 0) {
        printLog("Error: failed to find PC offset");
        return false;
    }
    
    return true;
}

OSErr InitProfiler(int sizeWords, long samplesPerSecond)
{
    THz applZone;
    
    // This should be the address of the function above main, which we don't
    // want to crawl into when doing a stack crawl. If InitProfiler() is not
    // called in main, then the stack crawls will stop at whatever function
    // called the function that called InitProfiler.
    asm volatile (
        "move.l %%a6, %%a0 \n"
        "move.l (%%a0), %%a0 \n"
        "move.l 4(%%a0), %0 \n"
        : "=d" (profilerStackCrawlStopAddr)
        :
        : "a0"
    );
    // Note: the above should be the equivalent of:
    // profilerStackCrawlStopAddr = (UInt32)__builtin_return_address(1);

    // Determine the range of addresses that our A6 frames should be within
    // (i.e. the start of the heap to A5)
    applZone = ApplicationZone();
    profilerAppHeapStart = (UInt32)&applZone->heapData;
    asm volatile (
        "move.l %%a5, %0 \n"
        : "=d" (profilerAppHeapEnd)
    );
    
    if (!CalculatePCOffset()) {
        return 30001;
    }
    
    sampleDataSizeWords = sizeWords;
    sampleData = (UInt16 *)NewPtr(sampleDataSizeWords * 2);
    
    if (!sampleData) {
        printLog("Error: failed to allocate profiler sample buffer");
        return MemError();
    }
    
    currentSample = sampleData;
    sampleCount = 0;
    badSampleCount = 0;
    errorCode = 0;
    
    memset(&profilerTimerTask, 0, sizeof(profilerTimerTask));
    timerUPP = NewTimerProc(ProfilerTimerFunctionShim);
    profilerTimerTask.tmAddr = timerUPP;
    InsTime((QElemPtr)&profilerTimerTask);
    timerUSec = 1000000L / samplesPerSecond;
    
    return noErr;
}

void DisposeProfiler()
{
    if (sampleData) {
        DisposePtr((Ptr)sampleData);
        sampleData = NULL;
    }
    
    if (profilerTimerTask.tmAddr) {
        RmvTime((QElemPtr)&profilerTimerTask);
    }
    
    if (timerUPP) {
        DisposeRoutineDescriptor(timerUPP);
    }
}

void StartProfiler()
{
    timerEnabled = true;
    PrimeTime((QElemPtr)&profilerTimerTask, -timerUSec);
}

void StopProfiler()
{
    profilerTimerTask.tmAddr = NULL;
    timerEnabled = false;
    
    switch(errorCode) {
        case 1:
            printLog("Error: profiler sample data was filled up. Only captured %d samples.", sampleCount);
            break;
        default:
            printLog("Profiler captured %d samples.", sampleCount);
            printLog("(# of bad samples: %d)", badSampleCount);
            break;
    }
}

OSErr SaveProfilingData_(FILE *f)
{
    OSErr err;
    short realCount, outCount, index, id;
    ResType unusedType;
    Str255 stringBuffer = {0};
    UInt32 startAddr, endAddr;
    long machineTypeCode;
    UInt32 ROMBase;
    
    err = Gestalt(gestaltMachineType, &machineTypeCode);
    
    if (err != noErr) {
        printLog("Error: couldn't determine the system's machine type");
        return err;
    }
    
    GetIndString(stringBuffer, kMachineNameStrID, machineTypeCode);
    
    if (stringBuffer[0] == 0) {
        printLog("Error: couldn't get the name of the system's machine type");
        return err;
    }
    
    fwrite(stringBuffer, sizeof(unsigned char),
           ((stringBuffer[0] + 2) / 2) * 2, // Keep it word aligned
           f);
    
    ROMBase = *(UInt32 *)0x2AE;
    fwrite(&ROMBase, 4, 1, f);
    
    realCount = CountResources('CODE');
    outCount = (GetResource('CODE', 0) != NULL) ? (realCount - 1) : realCount;
    fwrite(&outCount, sizeof(short), 1, f);
    
    for(index = 1; index <= realCount; ++index) {
        Handle codeResource = GetIndResource('CODE', index);
        
        if (!codeResource) {
            printLog("Error: failed to write profiling data, couldn't get handle to CODE resource and index %d", index);
            return ResError();
        }
        
        GetResInfo(codeResource, &id, &unusedType, stringBuffer);
        
        if (ResError() != noErr) {
            printLog("Error: failed to write profiling data, couldn't get ID of CODE resource");
            return ResError();
        }
        
        if (id == 0) {
            continue;
        }
        
        fwrite(&id, sizeof(short), 1, f);
        
        startAddr = (UInt32)(*codeResource);
        startAddr = (UInt32)StripAddress((void *)startAddr);
        endAddr = startAddr + GetResourceSizeOnDisk(codeResource);
        startAddr += 4;
        
        fwrite(&startAddr, sizeof(UInt32), 1, f);
        fwrite(&endAddr, sizeof(UInt32), 1, f);
    }
    
    fwrite(sampleData, sizeof(UInt16), currentSample - sampleData, f);
    
    return noErr;
}

// Makes it so you can pass &pstr[1] into places that expect a C string. Limits
// string length to 254 characters, which I personally can live with.
static void MakeCStringCompatible(Str255 pstr)
{
    if (pstr[0] == 255) {
        pstr[255] = 0;
        pstr[0] = 254;
    } else {
        pstr[pstr[0] + 1] = 0;
    }
}

OSErr SaveProfilingData(Str255 path)
{
    FILE *f;
    OSErr err;
    
    MakeCStringCompatible(path);
    f = fopen((const char *)&path[1], "wb");
    
    if (!f) {
        printLog("Error: failed to write profiling data to: %s", path);
        return fnOpnErr;
    }
    
    err = SaveProfilingData_(f);
    fclose(f);
    
    return err;
}

static OSErr GetDirectoryFullPath(short vRefNum, long dirID, Str255 outFullPath)
{
    CInfoPBRec pb;
    Str255 dirName;
    OSErr err;
    outFullPath[0] = 0;

    pb.dirInfo.ioVRefNum  = vRefNum;
    pb.dirInfo.ioNamePtr  = dirName;
    pb.dirInfo.ioDrParID  = dirID;
    pb.dirInfo.ioFDirIndex = -1;

    do {
        pb.dirInfo.ioDrDirID = pb.dirInfo.ioDrParID;
        err = PBGetCatInfoSync(&pb);
        
        if (err != noErr) {
            return err;
        }
        
        if (dirName[dirName[0]] != ':') {
            dirName[dirName[0]+1] = ':';
            dirName[0]++;
        }
        
        PrependPString(dirName, outFullPath);
        
    } while (pb.dirInfo.ioDrDirID != fsRtDirID);
    
    return noErr;
}

OSErr SaveProfilingDataToDesktop(StringPtr fileName)
{
    short vRefNum;
    long dirId;
    OSErr err = noErr;
    Str255 filePath = {0};
    
    err = FindFolder(kOnSystemDisk, kDesktopFolderType, kCreateFolder, &vRefNum, &dirId);
    
    if (err != noErr) {
        printLog("Failed to find volume for Desktop Folder");
        return err;
    }
    
    err = GetDirectoryFullPath(vRefNum, dirId, filePath);
    
    if (err != noErr) {
        printLog("Failed to get a full path for the Desktop folder");
        return err;
    }
    
    AppendPString(filePath, fileName);
    SaveProfilingData(filePath);
    
    return noErr;
}
