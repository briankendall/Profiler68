//
// TestPerf.c
//
// Adapted from TestPerf.c, from MPW 3.5.
//

#include <Dialogs.h>
#include <Fonts.h>
#include <Gestalt.h>
#include <QuickDraw.h>
#include <Resources.h>
#include <Sound.h>
#include <Timer.h>
#include <Traps.h>
#include <stdio.h>
#include <string.h>

#include "logging.h"
#include "profiler.h"

void	W500A();
void	W100();
void	W1500();
void	Waste();
void	W500B();
void	ROMW500A();
void	ROMW100();
void	ROMW1500();
void	ROMWaste();
void	ROMW500B();

int main(void)
{
    const short repeatCount = 4;
	short repeats;
    UInt32 startTime, endTime;
    OSErr err;
    
    InitializeLogging();
    printLog("Starting TestPerf\n");
    
    err = InitProfiler(256 * 512, 1000);
    
    if (err != noErr) {
        printLog("Error: InitProfiler failed! Error code: %d", err);
        return;
    }
    
    startTime = TickCount();
    StartProfiler();

	for (repeats = repeatCount; repeats; repeats--) {
		/* waste some time in user code/MUL4 */
		Waste();
		W100();
		W500A();
		W500B();
		W1500();
		/* waste some time in ROM calls: */
		ROMWaste();
		ROMW100();
		ROMW500A();
		ROMW500B();
		ROMW1500();
	};
    
    StopProfiler();
    endTime = TickCount();
    
    SaveProfilingDataToDesktop("\pTestPerf profile.dat");
    
    DisposeProfiler();
    printLog("All done! Time taken: %0.2f seconds\n", (endTime - startTime) / 60.0f);
    
	return 0;
}

void W500A(void)
{
	short	i;
	int		junk;
	int		junk1;
	int		junk2;

	for (i = 1; i <= 500; i++) {
		junk = 1;
		junk1 = junk * 5;
		junk2 = (junk + junk1) * 5;
	};
}; 
		
void W100(void)
{
	short	i;
	int		junk;
	int		junk1;
	int		junk2;

	for (i = 1; i <= 100; i++) {
		junk = 1;
		junk1 = junk * 5;
		junk2 = (junk + junk1) * 5;
	};
}; 

void W1500(void)
{
	short	i;
	int		junk;
	int		junk1;
	int		junk2;

	for (i = 1; i <= 1500; i++) {
		junk = 1;
		junk1 = junk * 5;
		junk2 = (junk + junk1) * 5;
	};
}; 


void Waste(void)
{
	short	i;
	int		junk;
	int		junk1;
	int		junk2;

	for (i = 1; i <= 1; i++) {
		junk = 1;
		junk1 = junk * 5;
		junk2 = (junk + junk1) * 5;
	};
}; 

void W500B(void)
{
	short	i;
	int		junk;
	int		junk1;
	int		junk2;

	for (i = 1; i <= 500; i++) {
		junk = 1;
		junk1 = junk * 5;
		junk2 = (junk + junk1) * 5;
	};
}; 

void ROMW500A(void)
{
	short	i;
	Rect	junk;
	Rect	junk1;
	Rect	junk2;
	Boolean	dontCare;
		
	for (i = 1; i <= 500; i++) {
		SetRect(&junk, 100, 200, 300, 400);
		SetRect(&junk1, 200, 300, 400, 500);
		dontCare = SectRect(&junk, &junk1, &junk2);
	};
};
		
void ROMW100(void)
{
	short	i;
	Rect	junk;
	Rect	junk1;
	Rect	junk2;
	Boolean	dontCare;
		
	for (i = 1; i <= 100; i++) {
		SetRect(&junk, 100, 200, 300, 400);
		SetRect(&junk1, 200, 300, 400, 500);
		dontCare = SectRect(&junk, &junk1, &junk2);
	};
};
		
void ROMW1500(void)
{
	short	i;
	Rect	junk;
	Rect	junk1;
	Rect	junk2;
	Boolean	dontCare;
		
	for (i = 1; i <= 1500; i++) {
		SetRect(&junk, 100, 200, 300, 400);
		SetRect(&junk1, 200, 300, 400, 500);
		dontCare = SectRect(&junk, &junk1, &junk2);
	};
};
		
void ROMWaste(void)
{
	short	i;
	Rect	junk;
	Rect	junk1;
	Rect	junk2;
	Boolean	dontCare;
		
	for (i = 1; i <= 1; i++) {
		SetRect(&junk, 100, 200, 300, 400);
		SetRect(&junk1, 200, 300, 400, 500);
		dontCare = SectRect(&junk, &junk1, &junk2);
	};
};
		
void ROMW500B(void)
{
	short	i;
	Rect	junk;
	Rect	junk1;
	Rect	junk2;
	Boolean	dontCare;
		
	for (i = 1; i <= 500; i++) {
		SetRect(&junk, 100, 200, 300, 400);
		SetRect(&junk1, 200, 300, 400, 500);
		dontCare = SectRect(&junk, &junk1, &junk2);
	};
};
