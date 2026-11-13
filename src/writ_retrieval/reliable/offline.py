#!/usr/bin/env python3
"""Run local Python validation with kernel-enforced network denial (Linux x86_64).

No privilege escalation: no_new_privs plus an inherited seccomp filter prevents
network socket creation/connection before any third-party import; anonymous
AF_UNIX socketpairs remain available for local asyncio wakeups.
This is a network boundary only, not a general untrusted-code sandbox.
"""
import ctypes
import errno
import os
import platform
import runpy
import sys


def deny_network():
    if sys.platform!='linux' or platform.machine()!='x86_64': raise RuntimeError('offline runner requires Linux x86_64; unsupported architectures fail closed')
    class Filter(ctypes.Structure):
        _fields_=[('code',ctypes.c_ushort),('jt',ctypes.c_ubyte),('jf',ctypes.c_ubyte),('k',ctypes.c_uint32)]
    class Program(ctypes.Structure):
        _fields_=[('length',ctypes.c_ushort),('filters',ctypes.POINTER(Filter))]
    # Check audit architecture, load syscall number, reject x32, then block
    # network socket/connect/accept/bind/listen and alternate descriptor paths.
    instructions=[(0x20,0,0,4),(0x15,1,0,0xC000003E),(0x06,0,0,0x80000000),
                  (0x20,0,0,0),(0x35,0,1,0x40000000),(0x06,0,0,0x00050000|errno.EPERM)]
    # asyncio needs only anonymous AF_UNIX pairs. No external Unix connections
    # are allowed, and no inherited Internet socket can be reused.
    instructions.extend([(0x15,0,4,53),(0x20,0,0,16),(0x15,0,1,1),
                         (0x06,0,0,0x7FFF0000),(0x06,0,0,0x00050000|errno.EPERM)])
    for syscall in (41,42,43,49,50,53,288,425,426,438):
        instructions.extend([(0x15,0,1,syscall),(0x06,0,0,0x00050000|errno.EPERM)])
    instructions.append((0x06,0,0,0x7FFF0000))
    filters=(Filter*len(instructions))(*(Filter(*i) for i in instructions));program=Program(len(filters),filters)
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(38,1,0,0,0) or libc.prctl(22,2,ctypes.byref(program),0,0):
        raise OSError(ctypes.get_errno(),'could not install offline network filter')
    # Do not let a dependency reuse an inherited non-stdio socket.
    os.closerange(3,os.sysconf('SC_OPEN_MAX'))


def main():
    args=sys.argv[1:]
    if len(args)<2 or args[0] not in {'-m','-c'}: raise SystemExit('usage: offline_run.py -m MODULE [args...] | -c CODE')
    deny_network()
    # Match python -m/-c import semantics rather than the wrapper script directory.
    sys.path.insert(0,os.getcwd())
    if args[0]=='-m':
        sys.argv=[args[1],*args[2:]];runpy.run_module(args[1],run_name='__main__',alter_sys=True)
    else:
        sys.argv=['-c',*args[2:]];exec(compile(args[1],'<offline>','exec'),{'__name__':'__main__'})


if __name__=='__main__': main()
