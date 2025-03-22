#ifndef CLIPOUT_H
#define CLIPOUT_H

#include <Types.h>

Boolean MinivmacExtensionAvailable();
OSErr SendToHostClipboard(const char *text, SInt16 length);

#endif
