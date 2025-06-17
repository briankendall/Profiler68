*MPW: INCLUDE 'Traps.a'
*MPW: INCLUDE 'Timer.a'
*MPW: INCLUDE 'Memory.a'
.set _PrimeTime, 0xA05A         | NoMPW
.set _StripAddress, 0xA055      | NoMPW
.set _Debugger, 0xA9FF          | NoMPW

.macro TRAP name                | NoMPW
    .short \name                | NoMPW
.endm                           | NoMPW

.text
.extern ProfilerTimerFunction
.global ProfilerFindPCOffset
.global ProfilerTimerFunctionShim
.global ProfilerStackCrawl
.global profilerEndlessLoopAddr
.global profilerPCOffset
.global profilerStackCrawlStopAddr
.global profilerTimerTask
.global profilerAppHeapStart
.global profilerAppHeapEnd
.align 2
profilerEndlessLoopAddr:
    .long 0
profilerPCOffset:
    .short 0
profilerStackCrawlStopAddr:
    .long 0
profilerTimerTask:
    .space 24
profilerAppHeapStart:
    .long 0
profilerAppHeapEnd:
    .long 0



ProfilerFindPCOffset:       | MPW PROC
    | d0: address to check in stack (used so we can easily run it through StripAddress)
    | d1: target address
    | d2: counter
    | a1: address of SP at start of function
    | a0: used for whatevs
    
    lea profilerEndlessLoopAddr(%pc), %a0
    move.l (%a0), %d0
    cmpi.l #0, %d0
    bne.b ready
    
    | We're not ready to check the stack, so just prime the timer and return:
    lea profilerTimerTask(%pc), %a0
    move.l #1, %d0
    TRAP _PrimeTime
    rts
    
ready:
    TRAP _StripAddress
    move.l %d0, %d1
    
    move.l %sp, %a1
    clr.l %d2
    
loop_search_stack:
    
    move.w (%a1, %d2.w), %d0
    andi.w #0xFF, %d0
    cmpi.w #0x1F, %d0
    bne.b noMatch
    
    move.l (2, %a1, %d2.w), %d0
    TRAP _StripAddress
    cmp.l %d1, %d0
    bne.b noMatch
    
    | We got the offset, increment it by 2 to end the loop!
    addq.w #2, %d2
    
    move.l (%a1, %d2.w), %d0
    addq.l #2, %d0
    move.l %d0, (%a1, %d2)
    
    
    lea profilerPCOffset(%pc), %a0
    move.w %d2, (%a0)
    rts
    
noMatch:
    addq.w #2, %d2
    cmpi.w #0x100, %d2
    blt.b loop_search_stack
    
    | Loop is over without finding anything:
    
    lea profilerPCOffset(%pc), %a0
    move.w (%a0), %d0
    addq.w #1, (%a0)
    tst.w (%a0)
    beq.s end_loop_search_stack
    
    | Prime the timer to try again in 1 ms
    lea profilerTimerTask(%pc), %a0
    move.l #1, %d0
    TRAP _PrimeTime
    rts

end_loop_search_stack:
    | We've tried too many times, so we break out of the endless loop
    | by replacing it with NOP and write -1 to profilerPCOffset to
    | indicate an error
    lea profilerPCOffset(%pc), %a0
    move.l #-1, (%a0)
    
    move.l %d1, %a1
    move.w #0x4E71, (%a1)
    
finished:
    rts
*MPW:    ENDP


ProfilerTimerFunctionShim:       | MPW PROC
    move.l %sp, -(%sp)
    jsr ProfilerTimerFunction
    addq.l #4, %sp
    rts
*MPW:    ENDP



ProfilerStackCrawl:              | MPW PROC
    | d0: Used for whatever
    | d1: Stack crawl stop address
    | d2: Safe address range start
    | d3: Safe address range end
    | a0: Current A6 frame
    | a1: Output buffer address (and temporary storage at beginning)
    | a2: Output counter address
    | a3: End of buffer address
    .set Buffer, 8
    .set Counter, 12
    .set EndOfBuffer, 16
    .set ErrorPtr, 20
    
    | Store old a6 before calling link
    move.l (%a6), %a0
    
    link %a6, #0
    movem.l %d3/%a2-%a3, -(%sp)
    
    lea profilerAppHeapStart(%pc), %a1
    move.l (%a1), %d2             | Safe addr start
    lea profilerAppHeapEnd(%pc), %a1
    move.l (%a1), %d3             | Safe addr end
    
    lea profilerStackCrawlStopAddr(%pc), %a1
    move.l (%a1), %d1             | Stop addr 
    
    move.l ErrorPtr(%a6), %a1
    clr.w (%a1)                   | Clear error indicator
    
    move.l Buffer(%a6), %a1       | Output buffer
    move.l Counter(%a6), %a2      | Output counter
    move.l EndOfBuffer(%a6), %a3  | End of buffer
    
    clr.w (%a2)
    
loop_stack_crawl:
    move.l %a0, %d0
    TRAP _StripAddress
    move.l %d0, %a0
    
    | Hit null frame?
    tst.l %d0
    beq.s end_loop_stack_crawl
    
    | Below safe address range?
    cmp.l %d2, %d0
    bcs.s bad_a6 
    | Above safe address range?
    cmp.l %d3, %d0
    bcc.s bad_a6
    
    | Hit stop addr?
    cmp.l 4(%a0), %d1
    beq.s end_loop_stack_crawl
    
    | Hit end of buffer?
    cmp.l %a3, %a1
    bhs.s out_of_buffer
    
    | Too many frames?
    cmpi.w #48, (%a2)
    bcc.s too_many_frames
    
    move.l 4(%a0), (%a1)+
  
    addq.w #1, (%a2)
  
    move.l (%a0), %a0
    bra.s loop_stack_crawl
    
bad_a6:
    move.l ErrorPtr(%a6), %a0    | Set error indicator: hit bad A6 frame
    move.w #3, (%a0)
    bra.s end_loop_stack_crawl
    
too_many_frames:
    move.l ErrorPtr(%a6), %a0    | Set error indicator: traversed too many frames
    move.w #2, (%a0)
    bra.s end_loop_stack_crawl
    
out_of_buffer:
    move.l ErrorPtr(%a6), %a0    | Set error indicator: ran out of buffer
    move.w #1, (%a0)
  
end_loop_stack_crawl:
    movem.l (%sp)+, %d3/%a2-%a3
    unlk %a6
    rts
*MPW:    ENDP
