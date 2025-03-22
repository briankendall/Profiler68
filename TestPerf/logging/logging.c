
#include "logging.h"

#include <Devices.h>
#include <MacTCP.h>
#include <Types.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "mini-vmac/ClipOut.h"

#define PRINT_METHOD_NOT_DETERMINED 0
#define NO_PRINT 1
#define PRINT_USING_MINIVMAC 2
#define PRINT_USING_UDP 3

#if INCLUDE_LOGGING

static short _printMethod = PRINT_METHOD_NOT_DETERMINED;
static short MacTCPDriver;
static StreamPtr UDPSenderStream = 0;
static ip_addrbytes UDPAddress;
static short UDPPort;

static Boolean IsRunningInMinivmac()
{
    static short result = -1;
    
    if (result == -1) {
        result = MinivmacExtensionAvailable();
    }
    
    return result;
}

static Boolean OpenMacTCPDriver()
{
	OSErr err;
    err = OpenDriver("\p.ipp", &MacTCPDriver);
	
	return err == noErr;
}

static OSErr CreateUDPStream(udp_port udpPort, StreamPtr *theStream)
{
	UDPiopb udpBlock;
	unsigned long bfrSize;
	Ptr buff;
	OSErr err;
	
	bfrSize = 2048;
	buff = NewPtr(bfrSize);
	if (MemError()!=noErr)
		return MemError();
		
	udpBlock.ioCRefNum = MacTCPDriver;
	udpBlock.csCode = UDPCreate;
	udpBlock.csParam.create.rcvBuff = buff;
	udpBlock.csParam.create.rcvBuffLen = bfrSize;
	udpBlock.csParam.create.localPort = udpPort;
	udpBlock.csParam.create.notifyProc = NULL;
	udpBlock.csParam.create.userDataPtr = NULL;
    
	err = PBControlSync((ParmBlkPtr)&udpBlock);
    
	if (err!=noErr) {
		return err;
    }
	
	*theStream = udpBlock.udpStream;
}

static OSErr ReleaseUDPStream(StreamPtr theStream)
{
	UDPiopb udpBlock;
	OSErr err;

	udpBlock.ioCRefNum = MacTCPDriver;
	udpBlock.csCode = UDPRelease;
	udpBlock.udpStream = theStream;
	err = PBControlSync((ParmBlkPtr)&udpBlock);
    
	if (err!=noErr) {
		return err;
    }
	
	DisposePtr(udpBlock.csParam.create.rcvBuff);
	
	return MemError();
}

static OSErr NetSendUDP(StreamPtr sendStream, ip_addr sendAddr, udp_port sendPort, char *sendData, short dataLength)
{
	UDPiopb udpBlock;
	//EventRecord ev;
	struct wdsEntry theWDS[2];
	OSErr err;
	
	theWDS[0].length = dataLength;
	theWDS[0].ptr = sendData;
	theWDS[1].length = 0;
	theWDS[1].ptr = nil;

	udpBlock.udpStream = sendStream;
	udpBlock.ioCompletion = nil;
	udpBlock.ioCRefNum = MacTCPDriver;
	udpBlock.csCode = UDPWrite;
	udpBlock.csParam.send.reserved = 0;
	udpBlock.csParam.send.remoteHost = sendAddr;
	udpBlock.csParam.send.remotePort = sendPort;
	udpBlock.csParam.send.checkSum = true;
	udpBlock.csParam.send.wdsPtr = (Ptr)theWDS;
    
	err = PBControlSync((ParmBlkPtr)&udpBlock);
	return err;
}

void InitializeLogging()
{
	if (IsRunningInMinivmac()) {
		_printMethod = PRINT_USING_MINIVMAC;
		return;
	}
	
#ifndef NO_UDP_LOGGING
    {
        OSErr err;
        
        if (OpenMacTCPDriver()) {
            _printMethod = PRINT_USING_UDP;
            
            err = CreateUDPStream(12345, &UDPSenderStream);
            
            if (err != noErr) {
                // Insert your own error handling here. I recommend displaying
                // an error dialog.
            }
            
            UDPAddress.a.byte[0] = LOGGING_IP_1;
            UDPAddress.a.byte[1] = LOGGING_IP_2;
            UDPAddress.a.byte[2] = LOGGING_IP_3;
            UDPAddress.a.byte[3] = LOGGING_IP_4;
            UDPPort = 12345;
            
            return;
        }
    }
#endif
	
	_printMethod = NO_PRINT;
}

void DeinitializeLogging()
{
	OSErr err;
	
	if (_printMethod == PRINT_USING_UDP && UDPSenderStream) {
        err = ReleaseUDPStream(UDPSenderStream);
		
        if (err != noErr) {
            // Insert your own error handling here. I recommend displaying
            // an error dialog.
        }
	}
}

static void doPrint(char *text, int len)
{
    OSErr err;
    
    switch(_printMethod) {
        case PRINT_METHOD_NOT_DETERMINED:
            break;
        case NO_PRINT:
            break;
        case PRINT_USING_MINIVMAC:
            text -= 4;
            text[0] = 'O';
            text[1] = 'U';
            text[2] = 'T';
            text[3] = ':';
            
			err = SendToHostClipboard(text, len+4);
			
			if (noErr != err) {
                // Insert your own error handling here. I recommend displaying
                // an error dialog.
			}
			
            break;
        case PRINT_USING_UDP:
			err = NetSendUDP(UDPSenderStream, UDPAddress.a.addr, UDPPort, text, len);
			
			if (err!=noErr) {
                // Insert your own error handling here. I recommend displaying
                // an error dialog.
			}
			
            break;
    }
}

void printLog(const char *str, ...)
{
	char buffer[1030];
    // We might need those four earlier bytes:
    char *text = &buffer[4];
	va_list arg;
    short len;
    
    va_start(arg, str);
    vsnprintf(text, 1024, str, arg);
    va_end(arg);
    
    len = strlen(text);
    text[len++] = '\n';
    
    doPrint(text, len);
}

void printLogMinivMac(const char *str, ...)
{
	char buffer[1030];
    // We might need those four earlier bytes:
    char *text = &buffer[4];
	va_list arg;
    short len;
    
    if (_printMethod != PRINT_USING_MINIVMAC) {
        return;
    }
    
    va_start(arg, str);
    vsnprintf(text, 1024, str, arg);
    va_end(arg);
    
    len = strlen(text);
    text[len++] = '\n';
    
    doPrint(text, len);
}

#endif // INCLUDE_LOGGING
