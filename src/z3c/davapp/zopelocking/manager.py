##############################################################################
#
# Copyright (c) 2007 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""
Implementation of the z3c.dav.interfaces.IDAVLockmanager needed to adapt
the zope.locking utiltity to integrate it into z3c.dav.
"""

import time
import random
from BTrees.OOBTree import OOBTree
import zope.component
import zope.interface
from zope.security.proxy import removeSecurityProxy
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.app.container.interfaces import IReadContainer
import z3c.dav.interfaces

import interfaces
import indirecttokens
import properties

WEBDAV_LOCK_KEY = "z3c.dav.lockingutils.info"

_randGen = random.Random(time.time())

class DAVLockmanager(object):
    """

      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking import utility, utils
      >>> from zope.locking.adapters import TokenBroker

      >>> file = Demo()

    Before we register a ITokenUtility utility make sure that the DAVLockmanager
    is not lockable.

      >>> adapter = DAVLockmanager(file)
      >>> adapter.islockable()
      False

    Now create and register a ITokenUtility utility.

      >>> util = utility.TokenUtility()
      >>> zope.component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    TokenBroker, (zope.interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)

      >>> import datetime
      >>> import pytz
      >>> def hackNow():
      ...     return datetime.datetime(2006, 7, 25, 23, 49, 51)
      >>> oldNow = utils.now
      >>> utils.now = hackNow

    Test the DAVLockmanager implements the descired interface.

      >>> adapter = DAVLockmanager(file)
      >>> verifyObject(z3c.dav.interfaces.IDAVLockmanager, adapter)
      True

    The adapter should also be lockable.

      >>> adapter.islockable()
      True

    Lock with an exclusive lock token.

      >>> roottoken = adapter.lock(u'exclusive', u'write',
      ...    u'Michael', datetime.timedelta(seconds = 3600), '0')
      >>> util.get(file) == roottoken
      True
      >>> zope.locking.interfaces.IExclusiveLock.providedBy(roottoken)
      True

      >>> adapter.islocked()
      True

      >>> activelock = adapter.getActivelock()
      >>> activelock.lockscope
      [u'exclusive']
      >>> activelock.locktype
      [u'write']
      >>> activelock.depth
      '0'
      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.lockroot
      '/dummy'
      >>> activelock.owner
      u'Michael'

      >>> adapter.refreshlock(datetime.timedelta(seconds = 7200))
      >>> adapter.getActivelock().timeout
      u'Second-7200'

      >>> adapter.unlock()
      >>> util.get(file) is None
      True
      >>> adapter.islocked()
      False
      >>> adapter.getActivelock() is None
      True

    Shared locking support.

      >>> roottoken = adapter.lock(u'shared', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 3600), '0')
      >>> util.get(file) == roottoken
      True
      >>> zope.locking.interfaces.ISharedLock.providedBy(roottoken)
      True

      >>> activelock = adapter.getActivelock()
      >>> activelock.lockscope
      [u'shared']
      >>> activelock.locktoken #doctest:+ELLIPSIS
      ['opaquelocktoken:...

      >>> adapter.unlock()

    Recursive lock suport.

      >>> demofolder = DemoFolder()
      >>> demofolder['demo'] = file

      >>> adapter = DAVLockmanager(demofolder)
      >>> roottoken = adapter.lock(u'exclusive', u'write', u'MichaelK',
      ...    datetime.timedelta(seconds = 3600), 'infinity')

      >>> demotoken = util.get(file)
      >>> interfaces.IIndirectToken.providedBy(demotoken)
      True

      >>> activelock = adapter.getActivelock()
      >>> activelock.lockroot
      '/dummy/'
      >>> DAVLockmanager(file).getActivelock().lockroot
      '/dummy/'
      >>> absoluteURL(file, None)
      '/dummy/dummy'
      >>> activelock.lockscope
      [u'exclusive']

    Already locked support.

      >>> adapter.lock(u'exclusive', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 100), 'infinity') #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked...
      >>> adapter.islocked()
      True

      >>> adapter.unlock()

    Some error conditions.

      >>> adapter.lock(u'notexclusive', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 100), 'infinity') # doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      UnprocessableError: ...

    Cleanup

      >>> zope.component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    TokenBroker, (zope.interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)
      True
      >>> utils.now = oldNow

    """
    zope.interface.implements(z3c.dav.interfaces.IDAVLockmanager)
    zope.component.adapts(zope.interface.Interface)

    def __init__(self, context):
        self.context = self.__parent__ = context

    def generateLocktoken(self):
        return "opaquelocktoken:%s-%s-00105A989226:%.03f" % \
               (_randGen.random(), _randGen.random(), time.time())

    def islockable(self):
        utility = zope.component.queryUtility(
            zope.locking.interfaces.ITokenUtility,
            context = self.context, default = None)
        return utility is not None

    def lock(self, scope, type, owner, duration, depth,
             roottoken = None, context = None):
        if context is None:
            context = self.context

        tokenBroker = zope.locking.interfaces.ITokenBroker(context)
        if tokenBroker.get():
            raise z3c.dav.interfaces.AlreadyLocked(
                context, message = u"Context or subitem is already locked.")

        if roottoken is None:
            if scope == u"exclusive":
                roottoken = tokenBroker.lock(duration = duration)
            elif scope == u"shared":
                roottoken = tokenBroker.lockShared(duration = duration)
            else:
                raise z3c.dav.interfaces.UnprocessableError(
                    self.context,
                    message = u"Invalid lockscope supplied to the lock manager")

            annots = roottoken.annotations.get(WEBDAV_LOCK_KEY, None)
            if annots is None:
                annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
            annots["owner"] = owner
            annots["token"] = self.generateLocktoken()
            annots["depth"] = depth
        else:
            indirecttoken = indirecttokens.IndirectToken(context, roottoken)
            ## XXX - using removeSecurityProxy - is this right, has
            ## it seems wrong
            removeSecurityProxy(roottoken).utility.register(indirecttoken)

        if depth == "infinity" and IReadContainer.providedBy(context):
            for subob in context.values():
                self.lock(scope, type, owner, duration, depth,
                          roottoken, subob)

        return roottoken

    def getActivelock(self, request = None):
        if self.islocked():
            token = zope.locking.interfaces.ITokenBroker(self.context).get()
            return properties.DAVActiveLockAdapter(
                token, self.context, request)
        return None

    def refreshlock(self, timeout):
        token = zope.locking.interfaces.ITokenBroker(self.context).get()
        token.duration = timeout

    def unlock(self):
        tokenBroker = zope.locking.interfaces.ITokenBroker(self.context)
        token = tokenBroker.get()
        token.end()

    def islocked(self):
        tokenBroker = zope.locking.interfaces.ITokenBroker(self.context)
        return tokenBroker.get() is not None
