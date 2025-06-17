## Profiler68

This is a sampling profiler that can be used with 68k Retro68 projects. It requires the Revised Timer Manager, so that means it needs at least System 6.0.3. Currently it's tested in System 7.1.

This repo includes a sample project, adapted from TestPerf from MPW 3.5, that demonstrates how to use the profiler. To build it, you need Retro68. The project is set up using my [Retro68 project template](https://github.com/briankendall/macintosh-dev-template) so look at the instructions there for how to build it and automatically run it in an emulated mac.

The profiler uses a timer to sample the currently executing instruction and then perform a stack crawl, and then saves all the samples to a file. You can then use the included Python script `analyze.py` to analyze the results and see where time is going. Run it with `--help` to see its arguments. It needs to know where Retro68's toolchain folder is, which you can specify either with its `-t` / `--retro68-toolchain` argument, or setting the `RETRO68_TOOLCHAIN` environment variable.

Samples are written into a hash table using a block of memory provided at initialization, when calling `InitProfiler`. If the entire block of memory gets filled up then the profiler will stop, so be sure to give it enough memory.

### Usage notes:

There are a few compiler flags you need to use for profiler builds:

- `-g -gdwarf-4`: Enables debugging, so that the profiler's samples can be symbolicated.
- `-ffixed-a6 -fno-omit-frame-pointer`: This ensures that each function call have a frame pointer and that register A6 is not overwritten, allowing the profiler to perform a stack crawl when taking samples. If you omit these then the stack traces it reports will not be accurate, though there is likely to be a performance cost to compiling with both of these.

#### Sample output
Here's what the output looks like when profiling TestPerf:
<details>
  
```
--------------------------------------------
Functions by inclusive samples:
--------------------------------------------

    main                             -     1317    100.0%
    SECTRECT                         -      986    74.86%
    ROMW1500                         -      587    44.57%
    RSECT                            -      284    21.56%
    ROMW500A                         -      196    14.88%
    ROMW500B                         -      194    14.73%
    W1500                            -      125     9.49%
    SETRECT                          -       45     3.41%
    ROMW100                          -       39     2.96%
    W500B                            -       38     2.88%
    W500A                            -       36     2.73%
    INITCRTABLE                      -       30     2.27%
    VBLINT                           -       27     2.05%
    W100                             -        4      0.3%
    INSETRECT                        -        3     0.22%
    FRRECT                           -        3     0.22%


--------------------------------------------
Functions by exclusive samples:
--------------------------------------------

    SECTRECT                         -      691    52.46%
    RSECT                            -      284    21.56%
    W1500                            -      125     9.49%
    SETRECT                          -       45     3.41%
    W500B                            -       38     2.88%
    W500A                            -       36     2.73%
    INITCRTABLE                      -       30     2.27%
    VBLINT                           -       27     2.05%
    ROMW1500                         -       21     1.59%
    ROMW500B                         -        5     0.37%
    W100                             -        4      0.3%
    ROMW500A                         -        3     0.22%
    INSETRECT                        -        3     0.22%
    FRRECT                           -        3     0.22%
    ROMW100                          -        2     0.15%


--------------------------------------------
Samples by function and line:
--------------------------------------------

=== W500A ==================================
  count:    13  19.11%          main.c  85 >: 	for (i = 1; i <= 500; i++) {
  count:     7  10.29%          main.c  86 >: 		junk = 1;
  count:    25  36.76%          main.c  87 >: 		junk1 = junk * 5;
  count:    23  33.82%          main.c  88 >: 		junk2 = (junk + junk1) * 5;

=== main ===================================
  count:     3   0.22%          main.c  55 >: 		W100();
  count:    36   2.75%          main.c  56 >: 		W500A();
  count:    39   2.97%          main.c  57 >: 		W500B();
  count:   127    9.7%          main.c  58 >: 		W1500();
  count:    44   3.36%          main.c  61 >: 		ROMW100();
  count:   212  16.19%          main.c  62 >: 		ROMW500A();
  count:   208  15.88%          main.c  63 >: 		ROMW500B();
  count:   640  48.89%          main.c  64 >: 		ROMW1500();

=== W500B ==================================
  count:    21  29.16%          main.c  142 >: 	for (i = 1; i <= 500; i++) {
  count:     3   4.16%          main.c  143 >: 		junk = 1;
  count:    23  31.94%          main.c  144 >: 		junk1 = junk * 5;
  count:    25  34.72%          main.c  145 >: 		junk2 = (junk + junk1) * 5;

=== W1500 ==================================
  count:    61  24.79%          main.c  113 >: 	for (i = 1; i <= 1500; i++) {
  count:    27  10.97%          main.c  114 >: 		junk = 1;
  count:    83  33.73%          main.c  115 >: 		junk1 = junk * 5;
  count:    75  30.48%          main.c  116 >: 		junk2 = (junk + junk1) * 5;

=== ROMW100 ================================
  count:     1   2.56%          main.c  172 >: 	for (i = 1; i <= 100; i++) {
  count:    38  97.43%          main.c  175 >: 		dontCare = SectRect(&junk, &junk1, &junk2);

=== ROMW500A ===============================
  count:     1    0.5%          main.c  158 >: 		SetRect(&junk, 100, 200, 300, 400);
  count:   196  99.49%          main.c  160 >: 		dontCare = SectRect(&junk, &junk1, &junk2);

=== ROMW500B ===============================
  count:     1    0.5%          main.c  218 >: 		SetRect(&junk, 100, 200, 300, 400);
  count:   196  99.49%          main.c  220 >: 		dontCare = SectRect(&junk, &junk1, &junk2);

=== ROMW1500 ===============================
  count:     3   0.49%          main.c  187 >: 	for (i = 1; i <= 1500; i++) {
  count:     1   0.16%          main.c  188 >: 		SetRect(&junk, 100, 200, 300, 400);
  count:     5   0.82%          main.c  189 >: 		SetRect(&junk1, 200, 300, 400, 500);
  count:   595   98.5%          main.c  190 >: 		dontCare = SectRect(&junk, &junk1, &junk2);

=== W100 ===================================
  count:     3   60.0%          main.c  99 >: 	for (i = 1; i <= 100; i++) {
  count:     1   20.0%          main.c  101 >: 		junk1 = junk * 5;
  count:     1   20.0%          main.c  102 >: 		junk2 = (junk + junk1) * 5;



--------------------------------------------
All stack traces:
--------------------------------------------

(393 times:)
  main
    ROMW1500
      SECTRECT

(167 times:)
  main
    ROMW1500
      SECTRECT
        RSECT

(138 times:)
  main
    ROMW500A
      SECTRECT

(134 times:)
  main
    ROMW500B
      SECTRECT

(125 times:)
  main
    W1500

(53 times:)
  main
    ROMW500A
      SECTRECT
        RSECT

(51 times:)
  main
    ROMW500B
      SECTRECT
        RSECT

(45 times:)
  main
    SETRECT

(38 times:)
  main
    W500B

(36 times:)
  main
    W500A

(27 times:)
  main
    INITCRTABLE

(24 times:)
  main
    ROMW100
      SECTRECT

(21 times:)
  main
    ROMW1500

(18 times:)
  main
    VBLINT

(13 times:)
  main
    ROMW100
      SECTRECT
        RSECT

(5 times:)
  main
    ROMW500B

(4 times:)
  main
    W100

(4 times:)
  main
    ROMW500B
      SECTRECT
        VBLINT

(4 times:)
  main
    ROMW1500
      SECTRECT
        VBLINT

(3 times:)
  main
    ROMW500A

(3 times:)
  main
    INSETRECT

(3 times:)
  main
    FRRECT

(2 times:)
  main
    SECTRECT

(2 times:)
  main
    ROMW100

(1 times:)
  main
    ROMW500A
      SECTRECT
        VBLINT

(1 times:)
  main
    ROMW500A
      SECTRECT
        INITCRTABLE

(1 times:)
  main
    ROMW1500
      SECTRECT
        INITCRTABLE

(1 times:)
  main
    ROMW1500
      INITCRTABLE
```

</details>

#### Possible future work:

- Make it so that this can be compiled with a classic Mac compiler like MPW, Think C, or CodeWarrior. That would mainly require rewriting the assembly code to fit their syntax.
- Make a PPC-compatible version
