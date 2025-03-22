#ifndef PROFILER_H
#define PROFILER_H

#include <Types.h>

// Custom failure code for InitProfiler:
#define kPCOffsetNotFound 30001

OSErr InitProfiler(int maxSamples, long samplesPerSecond);
void DisposeProfiler();
void StartProfiler();
void StopProfiler();
void SaveProfilingData(const char *path);
void SaveProfilingDataToDesktop(StringPtr fileName);

#endif // PROFILER_H
