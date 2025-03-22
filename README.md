## Profiler68

This is a sampling profiler that can be used with 68k Retro68 projects. It requires the Revised Timer Manager, so that means it needs at least System 6.0.3. Currently it's tested in System 7.1.

It uses a timer to sample the currently executing instruction and then perform a stack crawl, and then saves all the samples to a file. You can then use the included Python script to analyze the results and see where time is going.

Currently samples are written in sequence to a buffer in memory, so a lot of samples can fill the buffer up quickly. Be sure to make it big enough for your needs.

It includes a sample project, adapted from TestPerf from MPW 3.5, that demonstrates how to use the profiler. To build it, you need Retro68. The project is set up using my [Retro68 project template](https://github.com/briankendall/macintosh-dev-template) so look at the instructions there for how to build it and automatically run it in an emulated mac.

##### Possible future work:

- Make it so that this can be compiled with a classic Mac compiler like MPW, Think C, or CodeWarrior. That would mainly require rewriting the assembly code to fit their syntax.
- Use a more intelligent way of storing samples in memory while the profiler is running, so that less memory is required. (Someone want to figure out how to implement a fast C hashmap that's safe to use at interrupt time? That means no memory allocations! 😱)
- Make a PPC-compatible version