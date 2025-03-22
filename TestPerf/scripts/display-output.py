#!/usr/bin/env python3
# 
# Shows output from both the named pipe that receives all output from Mini vMac,
# and also listens on UDP port 12345 for output from a real mac.

import sys
import os
import errno
import socket
import selectors


def findProjectDir():
    dir = os.path.abspath('.')
    while(not os.path.exists(os.path.join(dir, "CMakeLists.txt")) and len(dir) > 1):
        dir = os.path.dirname(dir)
    
    if dir == '/':
        return None
    
    return dir


def sockRecv(sock, mask):
    data = sock.recv(4096)
    sys.stdout.write(data.decode('macroman')) # Macro Man! No wait... Mac Roman


def pipeRecv(pipe, mask):
    try:
        buffer = os.read(pipe, 1024)
    except OSError as err:
        if err.errno == errno.EAGAIN or err.errno == errno.EWOULDBLOCK:
            buffer = None
        else:
            raise  # something else has happened -- better reraise

    if buffer is not None and len(buffer) > 0:
        sys.stdout.write(buffer.decode('utf8'))


def main():
    projDir = findProjectDir()
    
    if projDir is None:
        raise Exception("Running script not in project directory")
    
    namedPipe = os.path.join(projDir, "build", "app_out")
    
    if '--no-sock' in sys.argv or '--no-socket' in sys.argv or '-s' in sys.argv:
        sock = None
    else:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('', 12345))
            sock.setblocking(False)
        except OSError:
            print("Not using socket")
            sock = None
        
    io = os.open(namedPipe, os.O_RDONLY | os.O_NONBLOCK)
    
    try:
        sel = selectors.DefaultSelector()
        
        if sock is not None:
            sel.register(sock, selectors.EVENT_READ, sockRecv)
        
        sel.register(io, selectors.EVENT_READ, pipeRecv)

        while True:
            try:
                events = sel.select()
                
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
            except KeyboardInterrupt:
                return
    
    finally:
        os.close(io)

if __name__ == "__main__":
    main()
