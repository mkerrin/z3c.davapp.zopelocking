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

from BTrees.OOBTree import OOBTree
import zope.component
import zope.interface
import zope.security.management
from zope.app.container.interfaces import IReadContainer
import z3c.dav.interfaces
import z3c.dav.locking

import interfaces
import indirecttokens
import properties

WEBDAV_LOCK_KEY = "z3c.dav.lockingutils.info"

class DAVLockmanager(object):
    """

      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking import utility, utils
      >>> from zope.locking.adapters import TokenBroker
      >>> from zope.traversing.browser.absoluteurl import absoluteURL

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

      >>> locktoken = adapter.lock(u'exclusive', u'write',
      ...    u'Michael', datetime.timedelta(seconds = 3600), '0')

      >>> adapter.islocked()
      True

      >>> activelock = adapter.getActivelock(locktoken)
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
      >>> len(activelock.locktoken)
      1
      >>> activelock.locktoken #doctest:+ELLIPSIS
      ['opaquelocktoken:...

      >>> util.get(file) == activelock.token
      True
      >>> zope.locking.interfaces.IExclusiveLock.providedBy(activelock.token)
      True

    Now refresh the timeout on the locktoken.

      >>> adapter.refreshlock(datetime.timedelta(seconds = 7200))
      >>> adapter.getActivelock(locktoken).timeout
      u'Second-7200'

    Unlock the resource.

      >>> adapter.unlock(locktoken)
      >>> util.get(file) is None
      True
      >>> adapter.islocked()
      False
      >>> adapter.getActivelock(locktoken) is None
      True

    We can't unlock the resource twice.

      >>> adapter.unlock(locktoken)
      Traceback (most recent call last):
      ...
      ConflictError: The context is not locked, so we can't unlock it.

    Shared locking support.

      >>> locktoken = adapter.lock(u'shared', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 3600), '0')

      >>> activelock = adapter.getActivelock(locktoken)
      >>> activelock.lockscope
      [u'shared']
      >>> len(activelock.locktoken)
      1
      >>> activelock.locktoken #doctest:+ELLIPSIS
      ['opaquelocktoken:...

      >>> util.get(file) == activelock.token
      True
      >>> zope.locking.interfaces.ISharedLock.providedBy(activelock.token)
      True

      >>> adapter.unlock(locktoken)

    Recursive lock suport.

      >>> demofolder = DemoFolder()
      >>> demofolder['demo'] = file

      >>> adapter = DAVLockmanager(demofolder)
      >>> locktoken = adapter.lock(u'exclusive', u'write',
      ...    u'MichaelK', datetime.timedelta(seconds = 3600), 'infinity')

      >>> demotoken = util.get(file)
      >>> interfaces.IIndirectToken.providedBy(demotoken)
      True

      >>> activelock = adapter.getActivelock(locktoken)
      >>> activelock.lockroot
      '/dummy/'
      >>> DAVLockmanager(file).getActivelock(locktoken).lockroot
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
      >>> activelock = adapter.getActivelock(locktoken)
      >>> len(activelock.locktoken)
      1

      >>> adapter.unlock(locktoken[0])

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

    def islockable(self):
        utility = zope.component.queryUtility(
            zope.locking.interfaces.ITokenUtility,
            context = self.context, default = None)
        return utility is not None

    def maybeRecursivelyLockIndirectly(self, utility,
                                       context, roottoken, depth):
        if depth == "infinity" and IReadContainer.providedBy(context):
            for subob in context.values():
                token = utility.get(subob)
                if token:
                    raise z3c.dav.interfaces.AlreadyLocked(
                        subob, message = u"Sub-object is already locked")
                indirecttoken = indirecttokens.IndirectToken(subob, roottoken)
                utility.register(indirecttoken)
                self.maybeRecursivelyLockIndirectly(
                    utility, subob, roottoken, depth)

    def register(self, utility, token):
        try:
            return utility.register(token)
        except zope.locking.interfaces.RegistrationError:
            raise z3c.dav.interfaces.AlreadyLocked(
                token.context, message = u"Context is locked")

    def lock(self, scope, type, owner, duration, depth):
        principal_id = getPrincipalId()
        utility = zope.component.getUtility(
            zope.locking.interfaces.ITokenUtility, context = self.context)

        locktoken = z3c.dav.locking.generateLocktoken()

        if scope == u"exclusive":
            roottoken = self.register(
                utility, zope.locking.tokens.ExclusiveLock(
                    self.context, principal_id, duration = duration))
            annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
        elif scope == u"shared":
            # A successful request for a new shared lock MUST result in the
            # generation of a unique lock associated with the requesting
            # principal. Thus if five principals have taken out shared write
            # locks on the same resource there will be five locks and five
            # lock tokens, one for each principal.
            roottoken = utility.get(self.context)
            if roottoken is None:
                roottoken = self.register(
                    utility, zope.locking.tokens.SharedLock(
                        self.context, (principal_id,), duration = duration))
                annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
                annots["principal_ids"] = [principal_id]
            else:
                roottoken.add((principal_id,))
                if WEBDAV_LOCK_KEY not in roottoken.annotations:
                    # Locked by an alternative application
                    annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
                    # Use OOBTree here
                    annots["principal_ids"] = [principal_id]
                else:
                    annots = roottoken.annotations[WEBDAV_LOCK_KEY]
                    annots["principal_ids"].append(principal_id)
        else:
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"Invalid lockscope supplied to the lock manager")

        annots[locktoken] = OOBTree()
        annots[locktoken].update({"owner": owner, "depth": depth})

        self.maybeRecursivelyLockIndirectly(
            utility, self.context, roottoken, depth)

        return locktoken

    def getActivelock(self, locktoken, request = None):
        if self.islocked():
            token = zope.locking.interfaces.ITokenBroker(self.context).get()
            return properties.DAVActiveLock(
                locktoken, token, self.context, request)
        return None

    def refreshlock(self, timeout):
        token = zope.locking.interfaces.ITokenBroker(self.context).get()
        token.duration = timeout

    def unlock(self, locktoken):
        utility = zope.component.getUtility(
            zope.locking.interfaces.ITokenUtility, context = self.context)
        token = utility.get(self.context)
        if token is None:
            raise z3c.dav.interfaces.ConflictError(
                self.context,
                message = "The context is not locked, so we can't unlock it.")

        if interfaces.IIndirectToken.providedBy(token):
            token = token.roottoken

        if zope.locking.interfaces.IExclusiveLock.providedBy(token):
            token.end()
        elif zope.locking.interfaces.ISharedLock.providedBy(token):
            principal_id = getPrincipalId()
            annots = token.annotations[WEBDAV_LOCK_KEY]
            del annots[locktoken]
            annots["principal_ids"].remove(principal_id)
            if principal_id not in annots["principal_ids"]:
                # will end token if no principals left
                token.remove((principal_id,))
        else:
            raise ValueError("Unknown lock token")

    def islocked(self):
        tokenBroker = zope.locking.interfaces.ITokenBroker(self.context)
        return tokenBroker.get() is not None


def getPrincipalId():
    principal_ids = [
        participation.principal.id
        for participation in
        zope.security.management.getInteraction().participations]

    if len(principal_ids) != 1:
        raise ValueError("There must be only one participant principal")
    principal_id = principal_ids[0]

    return principal_id
