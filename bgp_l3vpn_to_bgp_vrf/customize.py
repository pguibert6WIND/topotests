#!/usr/bin/env python

#
# Part of NetDEF Topology Tests
#
# Copyright (c) 2017 by
# Network Device Education Foundation, Inc. ("NetDEF")
#
# Permission to use, copy, modify, and/or distribute this software
# for any purpose with or without fee is hereby granted, provided
# that the above copyright notice and this permission notice appear
# in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND NETDEF DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL NETDEF BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#

"""
customize.py: Simple FRR/Quagga MPLS L3VPN test topology

                  |
             +----+----+
             |   ce1   |
             | 99.0.0.1|                              CE Router
             +----+----+
       192.168.1. | .2  ce1-eth0
                  | .1  r1-eth4
             +---------+
             |    r1   |
             | 1.1.1.1 |                              PE Router
             +----+----+
                  | .1  r1-eth0
                  |
            ~~~~~~~~~~~~~
          ~~     sw0     ~~
          ~~ 10.0.1.0/24 ~~
            ~~~~~~~~~~~~~
                  |10.0.1.0/24
                  |
                  | .2  r2-eth0
             +----+----+
             |    r2   |
             | 2.2.2.2 |                              P router
             +--+---+--+
    r2-eth2  .2 |   | .2  r2-eth1
         ______/     \______
        /                   \
  ~~~~~~~~~~~~~        ~~~~~~~~~~~~~
~~     sw2     ~~    ~~     sw1     ~~
~~ 10.0.3.0/24 ~~    ~~ 10.0.2.0/24 ~~
  ~~~~~~~~~~~~~        ~~~~~~~~~~~~~
        |                 /    |
         \      _________/     |
          \    /                \
r3-eth1 .3 |  | .3  r3-eth0      | .4 r4-eth0
      +----+--+---+         +----+----+
      |     r3    |         |    r4   | r4-eth5
      |  3.3.3.3  |         | 4.4.4.4 |-------+       PE Routers
      +-----------+         +---------+       |
192.168.1.1 |r3.eth4 192.168.1.1 | r4-eth4    |192.168.2.1
         .2 |       ceX-eth0  .2 |            |         .2
      +-----+-----+         +----+-----+ +----+-----+
      |    ce2    |         |   ce3    | |   ce4    |
      | 99.0.0.2  |         | 99.0.0.3 | | 99.0.0.4 | CE Routers
      +-----+-----+         +----+-----+ +----+-----+
            |                    |            |

"""

import os
import re
import sys
import pytest
import platform

# pylint: disable=C0413
# Import topogen and topotest helpers
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.topolog import logger

# Required to instantiate the topology builder class.
from mininet.topo import Topo

import shutil
CWD = os.path.dirname(os.path.realpath(__file__))
# test name based on directory
TEST = os.path.basename(CWD)
CustomizeVrfWithNetns = True

InitSuccess = False

class ThisTestTopo(Topo):
    "Test topology builder"
    def build(self, *_args, **_opts):
        "Build function"
        tgen = get_topogen(self)

        # This function only purpose is to define allocation and relationship
        # between routers, switches and hosts.
        #
        # Create P/PE routers
        #check for mpls
        tgen.add_router('r1')
        if tgen.hasmpls != True:
            logger.info('MPLS not available, tests will be skipped')
            return
        for routern in range(2, 5):
            tgen.add_router('r{}'.format(routern))
        # Create CE routers
        for routern in range(1, 5):
            tgen.add_router('ce{}'.format(routern))

        #CE/PE links
        tgen.add_link(tgen.gears['ce1'], tgen.gears['r1'], 'ce1-eth0', 'r1-eth4')
        tgen.add_link(tgen.gears['ce2'], tgen.gears['r3'], 'ce2-eth0', 'r3-eth4')
        tgen.add_link(tgen.gears['ce3'], tgen.gears['r4'], 'ce3-eth0', 'r4-eth4')
        tgen.add_link(tgen.gears['ce4'], tgen.gears['r4'], 'ce4-eth0', 'r4-eth5')

        # Create a switch with just one router connected to it to simulate a
        # empty network.
        switch = {}
        switch[0] = tgen.add_switch('sw0')
        switch[0].add_link(tgen.gears['r1'], nodeif='r1-eth0')
        switch[0].add_link(tgen.gears['r2'], nodeif='r2-eth0')

        switch[1] = tgen.add_switch('sw1')
        switch[1].add_link(tgen.gears['r2'], nodeif='r2-eth1')
        switch[1].add_link(tgen.gears['r3'], nodeif='r3-eth0')
        switch[1].add_link(tgen.gears['r4'], nodeif='r4-eth0')

        switch[1] = tgen.add_switch('sw2')
        switch[1].add_link(tgen.gears['r2'], nodeif='r2-eth2')
        switch[1].add_link(tgen.gears['r3'], nodeif='r3-eth1')

class CustCmd():
    def __init__(self):
        self.resetCounts()

    def doCmd(self, tgen, rtr, cmd, checkstr = None):
        output = tgen.net[rtr].cmd(cmd).strip()
        if len(output):
            self.output += 1
            if checkstr != None:
                ret = re.search(checkstr, output)
                if ret == None:
                    self.nomatch += 1
                else:
                    self.match += 1
                return ret
            logger.info('command: {} {}'.format(rtr, cmd))
            logger.info('output: ' + output)
        self.none += 1
        return None

    def resetCounts(self):
        self.match = 0
        self.nomatch = 0
        self.output = 0
        self.none = 0

    def getMatch(self):
        return self.match

    def getNoMatch(self):
        return self.nomatch

    def getOutput(self):
        return self.output

    def getNone(self):
        return self.none

cc = CustCmd()

def ltemplatePreRouterStartHook():
    krel = platform.release()
    tgen = get_topogen()
    logger.info('pre router-start hook, kernel=' + krel)
    #check for mpls
    if tgen.hasmpls != True:
        logger.info('MPLS not available, skipping setup')
        return
    #collect/log info on iproute2
    cc.doCmd(tgen, 'r2', 'apt-cache policy iproute2')
    cc.doCmd(tgen, 'r2', 'yum info iproute2')
    cc.doCmd(tgen, 'r2', 'yum info iproute')

    cc.resetCounts()
    #configure r2 mpls interfaces
    intfs = ['lo', 'r2-eth0', 'r2-eth1', 'r2-eth2']
    for intf in intfs:
<<<<<<< HEAD
        cc.doCmd(tgen, 'r2', 'echo 1 > /proc/sys/net/mpls/conf/{}/input'.format(intf))

    #configure cust1 VRFs & MPLS
    rtrs = ['r1', 'r3', 'r4']
    vrfs = ['r1-cust1', 'r3-cust1', 'r4-cust1']
    if CustomizeVrfWithNetns == True:
        cmds = ['ip netns add {}']
    else:
        cmds = ['ip link add {} type vrf table 10',
                'ip ru add oif {} table 10',
                'ip ru add iif {} table 10',
                'ip link set dev {} up']
    rtrs_vrf = zip(rtrs, vrfs)
    for rtr_vrf in rtrs_vrf:
        # enable MPLS before VRF configuration
        # this avoids having to handle VRF differences between NS and vrf-lite
        intfs = [rtr_vrf[1], 'lo', rtr_vrf[0]+'-eth0', rtr_vrf[0]+'-eth4']
        for intf in intfs:
            cc.doCmd(tgen, rtr_vrf[0], 'echo 1 > /proc/sys/net/mpls/conf/{}/input'.format(intf))
        logger.info('setup {} vrf {}, {}-eth4. enabled mpls input.'.format(rtr_vrf[0], rtr_vrf[1], rtr_vrf[0]))
        router = tgen.gears[rtr_vrf[0]]
        for cmd in cmds:

            cc.doCmd(tgen, rtr_vrf[0], cmd.format(rtr_vrf[1]))
        if CustomizeVrfWithNetns == True:
            cc.doCmd(tgen, rtr_vrf[0], 'ip link set dev {}-eth4 netns {}'.format(rtr_vrf[0], rtr_vrf[1]))
            cc.doCmd(tgen, rtr_vrf[0], 'ip netns exec {} ifconfig {}-eth4 up'.format(rtr_vrf[1], rtr_vrf[0]))
        else:
            cc.doCmd(tgen, rtr_vrf[0], 'ip link set dev {}-eth4 master {}'.format(rtr_vrf[0], rtr_vrf[1]))
    #configure r4-cust2 VRFs & MPLS
    rtrs = ['r4']
    if CustomizeVrfWithNetns == True:
        cmds = ['ip netns add r4-cust2']
    else:
        cmds = ['ip link add r4-cust2 type vrf table 20',
                'ip ru add oif r4-cust2 table 20',
                'ip ru add iif r4-cust2 table 20',
                'ip link set dev r4-cust2 up']
    for rtr in rtrs:
        # enable MPLS before VRF configuration
        # this avoids having to handle VRF differences between NS and vrf-lite
        intfs = ['r4-cust2', rtr+'-eth5']
        for intf in intfs:
            cc.doCmd(tgen, rtr, 'echo 1 > /proc/sys/net/mpls/conf/{}/input'.format(intf))
        logger.info('setup {0} vrf r4-cust2, {0}-eth5. enabled mpls input.'.format(rtr))
        for cmd in cmds:
            cc.doCmd(tgen, rtr, cmd)
        if CustomizeVrfWithNetns == True:
            cc.doCmd(tgen, rtr, 'ip link set dev {}-eth5 netns r4-cust2'.format(rtr))
            cc.doCmd(tgen, rtr, 'ip netns exec r4-cust2 ifconfig {}-eth5 up'.format(rtr))
        else:
            cc.doCmd(tgen, rtr, 'ip link set dev {}-eth5 master r4-cust2'.format(rtr))
    global InitSuccess
    if cc.getOutput():
        InitSuccess = False
        logger.info('VRF config failed ({}), tests will be skipped'.format(cc.getOutput()))
    else:
        InitSuccess = True
        logger.info('VRF config successful!')
    return;

def ltemplatePostRouterStartHook():
    logger.info('post router-start hook')
    return;

def versionCheck(vstr, rname='r1', compstr='<',cli=False, kernel='4.9'):
    tgen = get_topogen()

    router = tgen.gears[rname]

    if tgen.hasmpls != True:
        ret = 'MPLS not initialized'
        return ret

    if InitSuccess != True:
        ret = 'Test not successfully initialized'
        return ret

    ret = True
    try:
        if router.has_version(compstr, vstr):
            ret = False
            logger.debug('version check failed, version {} {}'.format(compstr, vstr))
    except:
        ret = True
    if ret == False:
        ret = 'Skipping tests on old version ({}{})'.format(compstr, vstr)
        logger.info(ret)
    elif kernel != None:
        krel = platform.release()
        if topotest.version_cmp(krel, kernel) < 0:
            ret = 'Skipping tests on old version ({} < {})'.format(krel, kernel)
            logger.info(ret)
    if cli:
        logger.info('calling mininet CLI')
        tgen.mininet_cli()
        logger.info('exited mininet CLI')
    return ret
